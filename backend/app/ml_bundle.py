from __future__ import annotations

import hashlib
import json
import math
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from pydantic import ValidationError

from app.schemas import CatalogGameSchema

BUNDLE_FORMAT_VERSION = 1
BUNDLE_ALGORITHM = "tfidf-tag-content-baseline"
BUNDLE_MODEL_VERSION = "gamesense-steam-store-tfidf-tag-v1"
FEATURE_VERSION = "gamesense-tfidf-tags-v1"
REQUIRED_BUNDLE_FILES = ("manifest.json", "catalog.json", "model.json", "evaluation.json")


class BundleError(RuntimeError):
    """Raised when a content bundle cannot be safely built or loaded."""


@dataclass(frozen=True)
class LoadedContentBundle:
    manifest: dict[str, Any]
    catalog: list[CatalogGameSchema]
    vocabulary: dict[str, int]
    idf: list[float]
    item_vectors: dict[str, dict[int, float]]
    evaluation: dict[str, Any]
    path: Path | None = None

    @property
    def source_id(self) -> str:
        return str(self.manifest.get("source", {}).get("sourceId", "unknown-source"))

    @property
    def data_snapshot(self) -> str:
        return str(self.manifest.get("dataSnapshot", self.manifest.get("bundleId", "unknown-snapshot")))

    @property
    def model_version(self) -> str:
        return str(self.manifest.get("modelVersion", BUNDLE_MODEL_VERSION))

    @property
    def algorithm(self) -> str:
        return str(self.manifest.get("algorithm", BUNDLE_ALGORITHM))

    @property
    def disclosure(self) -> str:
        source = self.manifest.get("source", {})
        attribution = source.get("attribution", {})
        limitations = self.manifest.get("limitations", [])
        pieces = [
            "Recommendations use a local content bundle built from the attached Kaggle Steam Store Games (Clean dataset) snapshot.",
            "This is a historical May-2019-era Steam/SteamSpy-derived catalog and is not live Steam trending or personalization.",
        ]
        if attribution.get("text"):
            pieces.append(f"Attribution: {attribution['text']}")
        if limitations:
            pieces.append("Limitations: " + " ".join(str(item) for item in limitations[:3]))
        return " ".join(pieces)

    def catalog_scores(self) -> dict[str, float]:
        scores: dict[str, float] = {}
        for game in self.catalog:
            score = game.metadata.get("contentBundleScore")
            if isinstance(score, (int, float)):
                scores[game.slug] = float(score)
        return scores


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _json_bytes(data: Any) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _tokenize(value: str | None) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", (value or "").lower())


def _norm_terms(values: Iterable[str]) -> list[str]:
    return [value.strip().lower() for value in values if value and value.strip()]


def _game_document(game: CatalogGameSchema) -> list[str]:
    tokens = [*_tokenize(game.title), *_tokenize(game.description)]
    for term in [*game.genres, *game.tags]:
        # Repeating taxonomy terms gives the sparse baseline practical, explainable signal
        # without changing the non-tuned nature of the model.
        term_tokens = _tokenize(term)
        tokens.extend(term_tokens)
        tokens.extend(term_tokens)
    return tokens


def _select_vocabulary(documents: Sequence[list[str]], *, max_features: int, min_df: int) -> tuple[dict[str, int], list[float], dict[str, int]]:
    doc_freq: dict[str, int] = {}
    for tokens in documents:
        for token in set(tokens):
            doc_freq[token] = doc_freq.get(token, 0) + 1

    eligible = [(token, df) for token, df in doc_freq.items() if df >= min_df]
    eligible.sort(key=lambda item: (-item[1], item[0]))
    selected = eligible[:max_features]
    selected.sort(key=lambda item: item[0])
    vocabulary = {token: index for index, (token, _) in enumerate(selected)}
    total_docs = len(documents)
    idf = [math.log((1 + total_docs) / (1 + df)) + 1 for _, df in selected]
    return vocabulary, idf, doc_freq


def _vectorize_tokens(
    tokens: Sequence[str],
    *,
    vocabulary: Mapping[str, int],
    idf: Sequence[float],
    max_terms: int | None = None,
) -> tuple[list[int], list[float]]:
    counts: dict[int, int] = {}
    for token in tokens:
        index = vocabulary.get(token)
        if index is not None:
            counts[index] = counts.get(index, 0) + 1
    weighted = [(index, count * idf[index]) for index, count in counts.items()]
    weighted.sort(key=lambda item: (-item[1], item[0]))
    if max_terms is not None:
        weighted = weighted[:max_terms]
    norm = math.sqrt(sum(weight * weight for _, weight in weighted))
    if norm <= 0:
        return [], []
    normalized = [(index, weight / norm) for index, weight in weighted]
    normalized.sort(key=lambda item: item[0])
    return [index for index, _ in normalized], [round(weight, 10) for _, weight in normalized]


def _as_catalog_game(record: CatalogGameSchema | Mapping[str, Any]) -> CatalogGameSchema:
    if isinstance(record, CatalogGameSchema):
        return record
    return CatalogGameSchema.model_validate(record)


def _normalize_manifest_source(source_manifest: Mapping[str, Any]) -> dict[str, Any]:
    attribution = source_manifest.get("attribution", {}) if isinstance(source_manifest, Mapping) else {}
    license_terms = source_manifest.get("licenseAndTerms", {}) if isinstance(source_manifest, Mapping) else {}
    retrieval = source_manifest.get("retrieval", {}) if isinstance(source_manifest, Mapping) else {}
    return {
        "sourceId": source_manifest.get("sourceId"),
        "name": source_manifest.get("name"),
        "origin": source_manifest.get("provenance", {}).get("origin"),
        "licenseName": license_terms.get("licenseName"),
        "termsUrl": license_terms.get("termsUrl"),
        "uncertainties": license_terms.get("uncertainties", []),
        "attribution": {
            "required": attribution.get("required", False),
            "text": attribution.get("text", ""),
        },
        "retrievalVersion": retrieval.get("version"),
        "retrievedAt": retrieval.get("retrievedAt"),
        "allowedUses": source_manifest.get("allowedUses", {}),
        "review": source_manifest.get("review", {}),
    }


def build_tfidf_content_bundle(
    *,
    games: Sequence[CatalogGameSchema | Mapping[str, Any]],
    source_manifest: Mapping[str, Any],
    output_path: Path,
    source_file_hashes: Mapping[str, str] | None = None,
    generated_at: str | None = None,
    max_features: int = 12000,
    max_item_terms: int = 128,
    min_df: int = 1,
    evaluation_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Fit a portable sparse TF-IDF/tag bundle and write it as JSON files in a zip.

    The operation fits vocabulary, IDF weights, and item feature vectors from the provided
    normalized catalog. It does not fine-tune a neural model or learn from user behavior.
    """

    catalog = [_as_catalog_game(game) for game in games]
    active_catalog = [game for game in catalog if game.isActive]
    if not active_catalog:
        raise BundleError("cannot build a content bundle without active catalog games")
    slugs = [game.slug for game in active_catalog]
    if len(slugs) != len(set(slugs)):
        raise BundleError("catalog slugs must be unique before bundle export")

    documents = [_game_document(game) for game in active_catalog]
    vocabulary, idf, doc_freq = _select_vocabulary(documents, max_features=max_features, min_df=min_df)
    if not vocabulary:
        raise BundleError("no TF-IDF vocabulary could be fitted from the catalog")

    item_vectors = []
    for row_index, (game, tokens) in enumerate(zip(active_catalog, documents)):
        indices, values = _vectorize_tokens(tokens, vocabulary=vocabulary, idf=idf, max_terms=max_item_terms)
        item_vectors.append(
            {
                "rowIndex": row_index,
                "slug": game.slug,
                "sourceGameId": game.sourceGameId,
                "indices": indices,
                "values": values,
            }
        )

    id_mapping = [
        {"rowIndex": index, "slug": game.slug, "sourceGameId": game.sourceGameId, "title": game.title}
        for index, game in enumerate(active_catalog)
    ]
    catalog_json = {
        "catalogFormatVersion": 1,
        "sourceId": source_manifest.get("sourceId"),
        "items": [game.model_dump(by_alias=True) for game in active_catalog],
        "idMapping": id_mapping,
    }
    tokens_by_index = [token for token, _ in sorted(vocabulary.items(), key=lambda item: item[1])]
    model_json = {
        "modelFormatVersion": 1,
        "featureVersion": FEATURE_VERSION,
        "fittedNotTrained": True,
        "vocabulary": vocabulary,
        "tokensByIndex": tokens_by_index,
        "idf": [round(value, 10) for value in idf],
        "itemVectors": item_vectors,
        "parameters": {
            "maxFeatures": max_features,
            "maxItemTerms": max_item_terms,
            "minDf": min_df,
            "tokenPattern": r"[a-z0-9]+(?:-[a-z0-9]+)?",
            "taxonomyTermRepeat": 2,
        },
        "fitSummary": {
            "catalogItems": len(active_catalog),
            "vocabularySize": len(vocabulary),
            "documentFrequencyMin": min(doc_freq.values()) if doc_freq else 0,
            "documentFrequencyMax": max(doc_freq.values()) if doc_freq else 0,
        },
    }
    evaluation_json = {
        "evaluationFormatVersion": 1,
        "generatedAt": generated_at or _utc_now(),
        "summary": dict(evaluation_summary or {}),
        "sanityChecks": {
            "activeCatalogItems": len(active_catalog),
            "uniqueSlugs": len(set(slugs)),
            "seedExclusionSupported": True,
            "idMappingAligned": True,
        },
        "claims": {
            "personalization": False,
            "fineTuning": False,
            "liveTrending": False,
            "realCatalogQualityVerifiedByUser": False,
        },
    }

    payloads = {
        "catalog.json": _json_bytes(catalog_json),
        "model.json": _json_bytes(model_json),
        "evaluation.json": _json_bytes(evaluation_json),
    }
    file_checksums = {name: sha256_bytes(payload) for name, payload in payloads.items()}
    bundle_id = f"{source_manifest.get('sourceId', 'content')}-{BUNDLE_MODEL_VERSION}"
    manifest_json = {
        "bundleFormatVersion": BUNDLE_FORMAT_VERSION,
        "bundleId": bundle_id,
        "algorithm": BUNDLE_ALGORITHM,
        "modelVersion": BUNDLE_MODEL_VERSION,
        "featureVersion": FEATURE_VERSION,
        "dataSnapshot": f"{source_manifest.get('sourceId', 'content')}-local-snapshot",
        "generatedAt": generated_at or _utc_now(),
        "source": _normalize_manifest_source(source_manifest),
        "rowCount": len(active_catalog),
        "files": {
            "catalog": "catalog.json",
            "model": "model.json",
            "evaluation": "evaluation.json",
        },
        "checksums": {
            "files": file_checksums,
            "sourceFiles": dict(source_file_hashes or {}),
        },
        "limitations": [
            "Historical Kaggle snapshot gathered around May 2019; not a live Steam catalog.",
            "Kaggle lists CC BY 4.0, but underlying Steam/SteamSpy terms uncertainty remains disclosed and accepted only for the local notebook/app demo scope.",
            "Sparse TF-IDF/tag features are fitted from catalog metadata; no neural fine-tuning, personalization, or accuracy tuning is included.",
        ],
    }
    payloads["manifest.json"] = _json_bytes(manifest_json)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in REQUIRED_BUNDLE_FILES:
            archive.writestr(name, payloads[name])

    manifest_json["bundleSha256"] = sha256_file(output_path)
    return manifest_json


def _read_zip_json(archive: zipfile.ZipFile, name: str) -> Any:
    try:
        with archive.open(name) as handle:
            return json.loads(handle.read().decode("utf-8"))
    except KeyError as exc:
        raise BundleError(f"content bundle is missing required file {name}") from exc
    except json.JSONDecodeError as exc:
        raise BundleError(f"content bundle file {name} is not valid JSON: {exc}") from exc


def _zip_member_bytes(archive: zipfile.ZipFile, name: str) -> bytes:
    try:
        with archive.open(name) as handle:
            return handle.read()
    except KeyError as exc:
        raise BundleError(f"content bundle is missing required file {name}") from exc


def load_content_bundle(path: Path) -> LoadedContentBundle:
    if not path.exists():
        raise BundleError(f"content bundle does not exist: {path}")

    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        missing = set(REQUIRED_BUNDLE_FILES).difference(names)
        if missing:
            raise BundleError(f"content bundle missing files: {sorted(missing)}")
        for name in names:
            if name.startswith("/") or ".." in Path(name).parts:
                raise BundleError(f"content bundle contains unsafe member path: {name}")

        manifest = _read_zip_json(archive, "manifest.json")
        if manifest.get("bundleFormatVersion") != BUNDLE_FORMAT_VERSION:
            raise BundleError("unsupported content bundle format version")
        expected = manifest.get("checksums", {}).get("files", {})
        for logical_name in ("catalog.json", "model.json", "evaluation.json"):
            actual_hash = sha256_bytes(_zip_member_bytes(archive, logical_name))
            if expected.get(logical_name) != actual_hash:
                raise BundleError(f"content bundle checksum mismatch for {logical_name}")

        catalog_json = _read_zip_json(archive, "catalog.json")
        model_json = _read_zip_json(archive, "model.json")
        evaluation_json = _read_zip_json(archive, "evaluation.json")

    try:
        catalog = [CatalogGameSchema.model_validate(item) for item in catalog_json.get("items", [])]
    except ValidationError as exc:
        raise BundleError(f"content bundle catalog failed schema validation: {exc}") from exc
    if not catalog:
        raise BundleError("content bundle catalog is empty")
    slugs = [game.slug for game in catalog]
    if len(slugs) != len(set(slugs)):
        raise BundleError("content bundle catalog contains duplicate slugs")

    id_mapping = catalog_json.get("idMapping", [])
    if len(id_mapping) != len(catalog):
        raise BundleError("content bundle id mapping length does not match catalog length")
    for index, (mapping, game) in enumerate(zip(id_mapping, catalog)):
        if mapping.get("rowIndex") != index or mapping.get("slug") != game.slug or mapping.get("sourceGameId") != game.sourceGameId:
            raise BundleError("content bundle id mapping is not aligned with catalog rows")

    vocabulary = model_json.get("vocabulary", {})
    idf = model_json.get("idf", [])
    if not isinstance(vocabulary, dict) or not isinstance(idf, list) or len(vocabulary) != len(idf):
        raise BundleError("content bundle TF-IDF vocabulary and IDF weights are inconsistent")
    vocab_indices = sorted(vocabulary.values())
    if vocab_indices != list(range(len(vocab_indices))):
        raise BundleError("content bundle vocabulary indices must be contiguous from zero")

    item_vectors: dict[str, dict[int, float]] = {}
    vectors = model_json.get("itemVectors", [])
    if len(vectors) != len(catalog):
        raise BundleError("content bundle item vector length does not match catalog length")
    for index, (vector, game) in enumerate(zip(vectors, catalog)):
        if vector.get("rowIndex") != index or vector.get("slug") != game.slug:
            raise BundleError("content bundle item vectors are not aligned with catalog rows")
        indices = vector.get("indices", [])
        values = vector.get("values", [])
        if len(indices) != len(values):
            raise BundleError(f"content bundle vector length mismatch for {game.slug}")
        sparse: dict[int, float] = {}
        for raw_index, raw_value in zip(indices, values):
            feature_index = int(raw_index)
            if feature_index < 0 or feature_index >= len(idf):
                raise BundleError(f"content bundle vector index out of bounds for {game.slug}")
            sparse[feature_index] = float(raw_value)
        item_vectors[game.slug] = sparse

    return LoadedContentBundle(
        manifest=manifest,
        catalog=catalog,
        vocabulary={str(token): int(index) for token, index in vocabulary.items()},
        idf=[float(value) for value in idf],
        item_vectors=item_vectors,
        evaluation=evaluation_json,
        path=path,
    )
