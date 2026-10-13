import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
MANIFEST = REPO_ROOT / "data/source-manifests/example.self-authored.json"
FIXTURE = REPO_ROOT / "data/fixtures/ml/sample_games.self-authored.json"


def run_pipeline(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "app.ml_pipeline", *args],
        cwd=BACKEND_ROOT,
        text=True,
        capture_output=True,
        check=check,
    )


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_source_check_reports_approved_self_authored_fixture_and_checksum() -> None:
    result = run_pipeline(
        "source-check",
        "--manifest",
        str(MANIFEST),
        "--repo-root",
        str(REPO_ROOT),
    )
    report = json.loads(result.stdout)

    assert report["ok"] is True
    assert report["sourceId"] == "gamesense-self-authored-smoke-fixture"
    assert report["sourceType"] == "self-authored"
    assert report["reviewState"] == "approved"
    assert report["findings"] == []
    assert report["checksums"]["contentSha256"] == "7bdc6bfeee54e01ada92be2b676237c643f413f642bd4598914032573ac571bd"


def test_normalize_validate_and_manifest_are_reproducible_for_tiny_sample(tmp_path: Path) -> None:
    normalized_path = tmp_path / "normalized.json"
    validation_path = tmp_path / "validation.json"
    pipeline_manifest_path = tmp_path / "pipeline-manifest.json"

    run_pipeline("normalize", "--manifest", str(MANIFEST), "--fixture", str(FIXTURE), "--output", str(normalized_path))
    normalized = load_json(normalized_path)

    assert normalized["rowCount"] == 2
    assert [game["slug"] for game in normalized["games"]] == ["fixture-moonlit-market", "fixture-orbit-runners"]
    assert all(game["sourceId"] == "gamesense-self-authored-smoke-fixture" for game in normalized["games"])
    assert normalized["games"][0]["metadata"]["inputRowNumber"] == 1

    run_pipeline("validate", "--manifest", str(MANIFEST), "--normalized", str(normalized_path), "--output", str(validation_path))
    validation = load_json(validation_path)

    assert validation["ok"] is True
    assert validation["rowCount"] == 2
    assert validation["validRowCount"] == 2
    assert validation["invalidRowCount"] == 0
    assert validation["findings"] == []

    run_pipeline(
        "manifest",
        "--manifest",
        str(MANIFEST),
        "--normalized",
        str(normalized_path),
        "--validation-report",
        str(validation_path),
        "--output",
        str(pipeline_manifest_path),
    )
    first_manifest = load_json(pipeline_manifest_path)
    run_pipeline(
        "manifest",
        "--manifest",
        str(MANIFEST),
        "--normalized",
        str(normalized_path),
        "--validation-report",
        str(validation_path),
        "--output",
        str(pipeline_manifest_path),
    )
    second_manifest = load_json(pipeline_manifest_path)

    assert first_manifest == second_manifest
    assert first_manifest["rowCounts"] == {
        "rawRecords": 2,
        "normalizedGames": 2,
        "validGames": 2,
        "invalidGames": 0,
    }
    assert first_manifest["validation"] == {"ok": True, "findingCounts": {}, "findings": []}
    assert first_manifest["licenseGate"]["approvalRequiredForFutureExternalSources"] is True
    assert first_manifest["licenseGate"]["externalSourcesAllowed"] is False
    assert len(first_manifest["checksums"]["pipelineManifestSha256"]) == 64


def test_validate_reports_duplicate_and_missing_required_catalog_signals(tmp_path: Path) -> None:
    normalized_path = tmp_path / "bad-normalized.json"
    bad_normalized = {
        "pipelineVersion": "gamesense-ml-pipeline-v1",
        "sourceId": "gamesense-self-authored-smoke-fixture",
        "rowCount": 2,
        "games": [
            {
                "sourceId": "gamesense-self-authored-smoke-fixture",
                "sourceGameId": "duplicate-id",
                "slug": "duplicate-slug",
                "title": "Missing Tags",
                "description": "Fixture row with missing tags.",
                "genres": ["Puzzle"],
                "tags": [],
                "platforms": [],
                "releaseDate": None,
                "metadata": {},
                "isActive": True,
            },
            {
                "sourceId": "gamesense-self-authored-smoke-fixture",
                "sourceGameId": "duplicate-id",
                "slug": "duplicate-slug",
                "title": "Missing Genres",
                "description": "Fixture row with missing genres.",
                "genres": [],
                "tags": ["logic"],
                "platforms": [],
                "releaseDate": None,
                "metadata": {},
                "isActive": True,
            },
        ],
    }
    normalized_path.write_text(json.dumps(bad_normalized), encoding="utf-8")

    result = run_pipeline("validate", "--manifest", str(MANIFEST), "--normalized", str(normalized_path), check=False)
    assert result.returncode == 1
    report = json.loads(result.stdout)
    codes = {finding["code"] for finding in report["findings"]}

    assert report["ok"] is False
    assert {"missing_tags", "missing_genres", "duplicate_identifier"}.issubset(codes)
