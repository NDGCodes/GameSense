from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from pydantic import ValidationError

from app.schemas import CatalogGameSchema, CatalogSourceSchema

PIPELINE_VERSION = "gamesense-ml-pipeline-v1"
SOURCE_MANIFEST_SCHEMA_VERSION = 1


class PipelineError(RuntimeError):
    """Raised when a pipeline command cannot safely continue."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(data: Any) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PipelineError(f"{path} is not valid JSON: {exc}") from exc


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def resolve_repo_path(repo_root: Path, uri: str | None) -> Path:
    if not uri:
        raise PipelineError("manifest retrieval.uri is required for local pipeline commands")
    path = Path(uri)
    if path.is_absolute():
        raise PipelineError("manifest retrieval.uri must be a repository-relative path")
    resolved = (repo_root / path).resolve()
    repo_resolved = repo_root.resolve()
    if repo_resolved not in [resolved, *resolved.parents]:
        raise PipelineError("manifest retrieval.uri resolves outside the repository")
    return resolved


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", value.strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-._")
    if not slug:
        raise PipelineError(f"cannot create a slug from {value!r}")
    return slug


def load_source_manifest(path: Path) -> CatalogSourceSchema:
    raw = load_json(path)
    try:
        return CatalogSourceSchema.model_validate(raw)
    except ValidationError as exc:
        raise PipelineError(f"source manifest failed canonical schema validation: {exc}") from exc


def source_check(manifest_path: Path, repo_root: Path) -> dict[str, Any]:
    manifest = load_source_manifest(manifest_path)
    fixture_path = resolve_repo_path(repo_root, manifest.retrieval.uri)
    if not fixture_path.exists():
        raise PipelineError(f"manifest retrieval.uri does not exist: {fixture_path}")

    actual_hash = sha256_file(fixture_path)
    expected_hash = manifest.retrieval.contentHash.value
    findings: list[dict[str, str]] = []

    if manifest.review.state != "approved":
        findings.append({"severity": "error", "code": "source_not_approved", "message": "source manifest review.state must be approved"})
    if not manifest.allowedUses.localDevelopment or not manifest.allowedUses.ci:
        findings.append({"severity": "error", "code": "use_not_allowed", "message": "source must allow localDevelopment and ci use"})
    if not manifest.allowedUses.commitToRepository:
        findings.append({"severity": "error", "code": "commit_not_allowed", "message": "tiny committed fixture must allow repository commit"})
    if actual_hash != expected_hash:
        findings.append({"severity": "error", "code": "content_hash_mismatch", "message": "retrieval content hash does not match fixture bytes"})
    if manifest.provenance.sourceType != "self-authored":
        findings.append({"severity": "error", "code": "external_source_not_allowed", "message": "Milestone 2 only permits the self-authored smoke fixture"})
    if manifest.licenseAndTerms.uncertainties:
        findings.append({"severity": "error", "code": "license_uncertainty", "message": "license uncertainties must be cleared before use"})

    return {
        "pipelineVersion": PIPELINE_VERSION,
        "command": "source-check",
        "sourceId": manifest.sourceId,
        "sourceType": manifest.provenance.sourceType,
        "reviewState": manifest.review.state,
        "allowedUses": manifest.allowedUses.model_dump(by_alias=True),
        "licenseName": manifest.licenseAndTerms.licenseName,
        "retrievalUri": manifest.retrieval.uri,
        "checksums": {
            "manifestSha256": sha256_file(manifest_path),
            "contentSha256": actual_hash,
            "expectedContentSha256": expected_hash,
        },
        "findings": findings,
        "ok": not any(item["severity"] == "error" for item in findings),
    }


def normalize_records(manifest_path: Path, fixture_path: Path) -> dict[str, Any]:
    manifest = load_source_manifest(manifest_path)
    fixture = load_json(fixture_path)
    if fixture.get("source") != "self-authored-fixture":
        raise PipelineError("only the self-authored fixture source is accepted in Milestone 2")
    records = fixture.get("records")
    if not isinstance(records, list):
        raise PipelineError("fixture records must be a list")

    games: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise PipelineError(f"record {index} must be an object")
        source_game_id = str(record.get("id") or "").strip()
        title = str(record.get("title") or "").strip()
        game = CatalogGameSchema.model_validate(
            {
                "sourceId": manifest.sourceId,
                "sourceGameId": source_game_id,
                "slug": slugify(source_game_id or title),
                "title": title,
                "description": record.get("description"),
                "genres": record.get("genres") or [],
                "tags": record.get("tags") or [],
                "platforms": record.get("platforms") or [],
                "releaseDate": record.get("releaseDate"),
                "metadata": {
                    "fixtureId": fixture.get("fixtureId"),
                    "fixtureSource": fixture.get("source"),
                    "inputRowNumber": index,
                },
                "isActive": True,
            }
        )
        games.append(game.model_dump(by_alias=True))

    normalized = {
        "pipelineVersion": PIPELINE_VERSION,
        "sourceId": manifest.sourceId,
        "fixtureId": fixture.get("fixtureId"),
        "rowCount": len(games),
        "games": games,
    }
    normalized["checksums"] = {"normalizedSha256": sha256_json(normalized)}
    return normalized


def find_duplicates(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for value in values:
        if value in seen:
            dupes.add(value)
        seen.add(value)
    return sorted(dupes)


def validate_normalized(manifest_path: Path, normalized_path: Path) -> dict[str, Any]:
    manifest = load_source_manifest(manifest_path)
    normalized = load_json(normalized_path)
    games_raw = normalized.get("games")
    findings: list[dict[str, Any]] = []
    invalid_rows: set[int] = set()
    games: list[tuple[int, CatalogGameSchema]] = []

    if not isinstance(games_raw, list):
        findings.append({"severity": "error", "code": "games_not_list", "message": "normalized games must be a list"})
        games_raw = []

    for index, raw_game in enumerate(games_raw, start=1):
        try:
            game = CatalogGameSchema.model_validate(raw_game)
            games.append((index, game))
        except ValidationError as exc:
            invalid_rows.add(index)
            findings.append({"severity": "error", "code": "game_schema_invalid", "row": index, "message": str(exc)})
            continue
        if game.sourceId != manifest.sourceId:
            invalid_rows.add(index)
            findings.append({"severity": "error", "code": "source_id_mismatch", "row": index, "message": "game sourceId does not match manifest sourceId"})
        if not game.genres:
            invalid_rows.add(index)
            findings.append({"severity": "error", "code": "missing_genres", "row": index, "message": "game must include at least one genre"})
        if not game.tags:
            invalid_rows.add(index)
            findings.append({"severity": "error", "code": "missing_tags", "row": index, "message": "game must include at least one tag"})

    for field_name, values in {
        "slug": [game.slug for _, game in games],
        "sourceGameId": [game.sourceGameId for _, game in games],
    }.items():
        for duplicate in find_duplicates(values):
            duplicate_rows = [index for index, game in games if getattr(game, field_name) == duplicate]
            invalid_rows.update(duplicate_rows)
            findings.append({"severity": "error", "code": "duplicate_identifier", "field": field_name, "rows": duplicate_rows, "value": duplicate, "message": f"duplicate {field_name}"})

    return {
        "pipelineVersion": PIPELINE_VERSION,
        "command": "validate",
        "sourceId": manifest.sourceId,
        "rowCount": len(games_raw),
        "validRowCount": len(games_raw) - len(invalid_rows),
        "invalidRowCount": len(invalid_rows),
        "checksums": {"normalizedSha256": sha256_file(normalized_path)},
        "findings": findings,
        "ok": not any(item["severity"] == "error" for item in findings),
    }


def _finding(severity: str, code: str, message: str) -> dict[str, str]:
    return {"severity": severity, "code": code, "message": message}


def steam_store_source_check(manifest_path: Path) -> dict[str, Any]:
    """Validate the approved local-demo scope for Kaggle Steam Store Games.

    This is intentionally separate from the Milestone 2 self-authored source-check. It allows
    the selected public dataset only for the captain-accepted local notebook/app-demo scope and
    preserves the disclosed Steam/SteamSpy upstream uncertainty as a warning, not a legal-clearance
    claim.
    """

    manifest = load_source_manifest(manifest_path)
    findings: list[dict[str, str]] = []
    if manifest.sourceId != "kaggle.steam-store-games-clean":
        findings.append(_finding("error", "unexpected_source", "only kaggle.steam-store-games-clean is accepted by this check"))
    if manifest.provenance.sourceType != "public-dataset":
        findings.append(_finding("error", "source_type", "Steam Store Games manifest must be a public-dataset source"))
    if manifest.review.state != "approved":
        findings.append(_finding("error", "review_not_approved", "manifest review.state must be approved for the local Kaggle run"))
    if "CC BY 4.0" not in manifest.licenseAndTerms.licenseName and "Attribution 4.0" not in manifest.licenseAndTerms.licenseName:
        findings.append(_finding("error", "license_name", "manifest must record Kaggle's listed CC BY 4.0 / Attribution 4.0 license"))
    if not manifest.attribution.required or not manifest.attribution.text.strip():
        findings.append(_finding("error", "attribution_missing", "CC BY 4.0 attribution text is required"))
    if manifest.allowedUses.commitToRepository:
        findings.append(_finding("error", "commit_not_allowed", "raw Kaggle data and generated bundles must not be committed to the repository"))
    if manifest.allowedUses.ci:
        findings.append(_finding("error", "ci_not_allowed", "CI must stay on cleared tiny samples, not the Kaggle dataset"))
    for flag in ("localDevelopment", "training", "evaluation", "serving"):
        if not getattr(manifest.allowedUses, flag):
            findings.append(_finding("error", f"{flag}_not_allowed", f"manifest must allow {flag} for the accepted local demo scope"))
    if manifest.licenseAndTerms.redistributionAllowed:
        findings.append(_finding("warning", "redistribution_not_unrestricted", "do not treat the dataset or generated bundle as unrestricted redistribution"))
    if manifest.licenseAndTerms.uncertainties:
        findings.append(_finding("warning", "accepted_upstream_uncertainty", "underlying Steam/SteamSpy terms uncertainty remains disclosed and accepted only for this local demo/training scope"))

    return {
        "pipelineVersion": PIPELINE_VERSION,
        "command": "steam-store-source-check",
        "sourceId": manifest.sourceId,
        "reviewState": manifest.review.state,
        "licenseName": manifest.licenseAndTerms.licenseName,
        "attribution": manifest.attribution.model_dump(by_alias=True),
        "allowedUses": manifest.allowedUses.model_dump(by_alias=True),
        "acceptedScope": "local Kaggle notebook fitting/evaluation and local app demo with attribution; no raw-data or bundle commit; no unrestricted redistribution claim",
        "unresolvedUncertainties": manifest.licenseAndTerms.uncertainties,
        "findings": findings,
        "ok": not any(item["severity"] == "error" for item in findings),
    }


def _split_multi(value: str | None) -> list[str]:
    if not value:
        return []
    parts = re.split(r"[;,]", value)
    seen: set[str] = set()
    output: list[str] = []
    for part in parts:
        cleaned = re.sub(r"\s+", " ", part).strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            output.append(cleaned)
    return output


def _strip_html(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _parse_float(value: str | None) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def _owner_midpoint(value: str | None) -> float | None:
    if not value:
        return None
    numbers = [float(item.replace(",", "")) for item in re.findall(r"[0-9][0-9,]*", value)]
    if len(numbers) >= 2:
        return (numbers[0] + numbers[1]) / 2
    if numbers:
        return numbers[0]
    return None


def _catalog_score(row: Mapping[str, str]) -> float:
    positive = _parse_float(row.get("positive")) or 0.0
    owners = _owner_midpoint(row.get("owners")) or 0.0
    average_playtime = _parse_float(row.get("average_playtime")) or 0.0
    score = math.log1p(max(positive, 0.0)) + (math.log1p(max(owners, 0.0)) / 4.0) + (math.log1p(max(average_playtime, 0.0)) / 8.0)
    return round(score, 6)


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _index_rows(rows: Sequence[Mapping[str, str]], key_names: Sequence[str]) -> dict[str, Mapping[str, str]]:
    indexed: dict[str, Mapping[str, str]] = {}
    for row in rows:
        key = next((str(row.get(name) or "").strip() for name in key_names if str(row.get(name) or "").strip()), "")
        if key:
            indexed[key] = row
    return indexed


def _top_tag_columns(row: Mapping[str, str], *, excluded: set[str], limit: int = 12) -> list[str]:
    scored: list[tuple[float, str]] = []
    for key, value in row.items():
        if key in excluded:
            continue
        score = _parse_float(value)
        if score and score > 0:
            scored.append((score, key))
    scored.sort(key=lambda item: (-item[0], item[1].lower()))
    return [tag for _, tag in scored[:limit]]


def normalize_steam_store_games(manifest_path: Path, dataset_dir: Path, *, limit: int | None = None) -> dict[str, Any]:
    source_report = steam_store_source_check(manifest_path)
    if not source_report["ok"]:
        raise PipelineError("Steam Store Games source manifest is not approved for the local bundle scope")
    manifest = load_source_manifest(manifest_path)
    steam_csv = dataset_dir / "steam.csv"
    steam_rows = _read_csv(steam_csv)
    if not steam_rows:
        raise PipelineError(f"expected Kaggle steam.csv at {steam_csv}")
    descriptions = _index_rows(_read_csv(dataset_dir / "steam_description_data.csv"), ("steam_appid", "appid"))
    steamspy_tags = _index_rows(_read_csv(dataset_dir / "steamspy_tag_data.csv"), ("appid", "steam_appid"))

    games: list[dict[str, Any]] = []
    skipped = {"missingIdOrTitle": 0, "nonEnglish": 0, "duplicateAppId": 0}
    seen_appids: set[str] = set()
    for raw_index, row in enumerate(steam_rows, start=1):
        appid = str(row.get("appid") or row.get("steam_appid") or "").strip()
        title = re.sub(r"\s+", " ", str(row.get("name") or "").strip())
        if not appid or not title:
            skipped["missingIdOrTitle"] += 1
            continue
        if appid in seen_appids:
            skipped["duplicateAppId"] += 1
            continue
        if str(row.get("english", "1")).strip() not in ("", "1", "true", "True"):
            skipped["nonEnglish"] += 1
            continue
        seen_appids.add(appid)
        desc_row = descriptions.get(appid, {})
        description = _strip_html(
            desc_row.get("short_description")
            or desc_row.get("about_the_game")
            or desc_row.get("detailed_description")
            or row.get("short_description")
        )
        genres = _split_multi(row.get("genres"))
        categories = _split_multi(row.get("categories"))
        tags = [*_split_multi(row.get("steamspy_tags")), *categories]
        tag_row = steamspy_tags.get(appid, {})
        tags.extend(_top_tag_columns(tag_row, excluded={"appid", "steam_appid"}))
        tags = _split_multi(";".join(tags))
        game = CatalogGameSchema.model_validate(
            {
                "sourceId": manifest.sourceId,
                "sourceGameId": appid,
                "slug": slugify(f"steam-{appid}"),
                "title": title[:240],
                "description": description,
                "genres": genres,
                "tags": tags,
                "platforms": _split_multi(row.get("platforms")),
                "releaseDate": row.get("release_date") or None,
                "metadata": {
                    "inputRowNumber": raw_index,
                    "steamAppId": appid,
                    "sourceUrl": f"https://store.steampowered.com/app/{appid}/",
                    "developer": row.get("developer") or None,
                    "publisher": row.get("publisher") or None,
                    "owners": row.get("owners") or None,
                    "positive": _parse_float(row.get("positive")),
                    "negative": _parse_float(row.get("negative")),
                    "averagePlaytime": _parse_float(row.get("average_playtime")),
                    "medianPlaytime": _parse_float(row.get("median_playtime")),
                    "price": _parse_float(row.get("price")),
                    "contentBundleScore": _catalog_score(row),
                    "sourceFiles": ["steam.csv", "steam_description_data.csv", "steamspy_tag_data.csv"],
                },
                "isActive": True,
            }
        )
        games.append(game.model_dump(by_alias=True))
        if limit is not None and len(games) >= limit:
            break

    normalized = {
        "pipelineVersion": PIPELINE_VERSION,
        "command": "normalize-steam-store",
        "sourceId": manifest.sourceId,
        "rowCount": len(games),
        "rawRowCount": len(steam_rows),
        "skippedRows": skipped,
        "datasetFiles": {
            "steam.csv": str(steam_csv),
            "steam_description_data.csv": str(dataset_dir / "steam_description_data.csv"),
            "steamspy_tag_data.csv": str(dataset_dir / "steamspy_tag_data.csv"),
        },
        "sourceReport": source_report,
        "games": games,
    }
    normalized["checksums"] = {"normalizedSha256": sha256_json(normalized)}
    return normalized


def generate_pipeline_manifest(manifest_path: Path, normalized_path: Path, validation_path: Path) -> dict[str, Any]:
    manifest = load_source_manifest(manifest_path)
    normalized = load_json(normalized_path)
    validation = load_json(validation_path)
    row_count = int(normalized.get("rowCount", len(normalized.get("games", []))))
    finding_counts: dict[str, int] = {}
    for finding in validation.get("findings", []):
        severity = str(finding.get("severity", "unknown"))
        finding_counts[severity] = finding_counts.get(severity, 0) + 1

    output = {
        "pipelineVersion": PIPELINE_VERSION,
        "generatedAt": "1970-01-01T00:00:00Z",
        "sourceId": manifest.sourceId,
        "sourceManifestSchemaVersion": SOURCE_MANIFEST_SCHEMA_VERSION,
        "input": {
            "manifestPath": str(manifest_path),
            "retrievalUri": manifest.retrieval.uri,
        },
        "rowCounts": {
            "rawRecords": row_count,
            "normalizedGames": row_count,
            "validGames": int(validation.get("validRowCount", 0)),
            "invalidGames": int(validation.get("invalidRowCount", 0)),
        },
        "validation": {
            "ok": bool(validation.get("ok")),
            "findingCounts": finding_counts,
            "findings": validation.get("findings", []),
        },
        "checksums": {
            "sourceManifestSha256": sha256_file(manifest_path),
            "normalizedSha256": sha256_file(normalized_path),
            "validationSha256": sha256_file(validation_path),
        },
        "licenseGate": {
            "reviewState": manifest.review.state,
            "licenseName": manifest.licenseAndTerms.licenseName,
            "externalSourcesAllowed": False,
            "approvalRequiredForFutureExternalSources": True,
        },
    }
    output["checksums"]["pipelineManifestSha256"] = sha256_json(output)
    return output


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output", type=Path, help="Write JSON output to this path instead of stdout")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GameSense local ML data-validation pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    source_parser = subparsers.add_parser("source-check", help="Verify source manifest approval, use gates, and fixture checksum")
    source_parser.add_argument("--manifest", type=Path, required=True)
    source_parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    add_common_args(source_parser)

    normalize_parser = subparsers.add_parser("normalize", help="Normalize the tiny self-authored sample into catalog-game records")
    normalize_parser.add_argument("--manifest", type=Path, required=True)
    normalize_parser.add_argument("--fixture", type=Path, required=True)
    add_common_args(normalize_parser)

    validate_parser = subparsers.add_parser("validate", help="Validate normalized catalog-game records")
    validate_parser.add_argument("--manifest", type=Path, required=True)
    validate_parser.add_argument("--normalized", type=Path, required=True)
    add_common_args(validate_parser)

    manifest_parser = subparsers.add_parser("manifest", help="Generate reproducible pipeline evidence manifest")
    manifest_parser.add_argument("--manifest", type=Path, required=True)
    manifest_parser.add_argument("--normalized", type=Path, required=True)
    manifest_parser.add_argument("--validation-report", type=Path, required=True)
    add_common_args(manifest_parser)

    steam_source_parser = subparsers.add_parser(
        "steam-store-source-check",
        help="Verify the accepted local-demo scope for Kaggle Steam Store Games (Clean dataset)",
    )
    steam_source_parser.add_argument("--manifest", type=Path, required=True)
    add_common_args(steam_source_parser)

    steam_normalize_parser = subparsers.add_parser(
        "normalize-steam-store",
        help="Normalize Kaggle Steam Store Games CSV files into catalog-game records",
    )
    steam_normalize_parser.add_argument("--manifest", type=Path, required=True)
    steam_normalize_parser.add_argument("--dataset-dir", type=Path, required=True)
    steam_normalize_parser.add_argument("--limit", type=int, default=None, help="Optional row limit for smoke tests")
    add_common_args(steam_normalize_parser)
    return parser


def emit(data: dict[str, Any], output: Path | None) -> None:
    if output:
        write_json(output, data)
    else:
        print(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False))


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "source-check":
            data = source_check(args.manifest, args.repo_root)
        elif args.command == "normalize":
            data = normalize_records(args.manifest, args.fixture)
        elif args.command == "validate":
            data = validate_normalized(args.manifest, args.normalized)
        elif args.command == "manifest":
            data = generate_pipeline_manifest(args.manifest, args.normalized, args.validation_report)
        elif args.command == "steam-store-source-check":
            data = steam_store_source_check(args.manifest)
        elif args.command == "normalize-steam-store":
            data = normalize_steam_store_games(args.manifest, args.dataset_dir, limit=args.limit)
        else:  # pragma: no cover
            parser.error(f"unknown command {args.command}")
        emit(data, args.output)
        return 0 if data.get("ok", True) else 1
    except PipelineError as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
