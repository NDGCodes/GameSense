from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Sequence

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
        else:  # pragma: no cover
            parser.error(f"unknown command {args.command}")
        emit(data, args.output)
        return 0 if data.get("ok", True) else 1
    except PipelineError as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
