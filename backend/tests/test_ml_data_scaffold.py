import hashlib
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_json(relative_path: str):
    return json.loads((REPO_ROOT / relative_path).read_text(encoding="utf-8"))


def test_source_manifest_example_covers_policy_fields_and_fixture_hash() -> None:
    schema = load_json("data/source-manifest.schema.json")
    manifest = load_json("data/source-manifests/example.self-authored.json")
    fixture_path = REPO_ROOT / manifest["retrieval"]["uri"]

    for field in schema["required"]:
        assert field in manifest

    assert manifest["provenance"]["sourceType"] == "self-authored"
    assert manifest["licenseAndTerms"]["uncertainties"] == []
    assert manifest["allowedUses"]["commitToRepository"] is True
    assert manifest["allowedUses"]["serving"] is False
    assert manifest["review"]["state"] == "approved"

    digest = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    assert manifest["retrieval"]["contentHash"] == {"algorithm": "sha256", "value": digest}


def test_self_authored_fixture_is_tiny_and_identified() -> None:
    fixture_path = REPO_ROOT / "data/fixtures/ml/sample_games.self-authored.json"
    fixture = load_json("data/fixtures/ml/sample_games.self-authored.json")

    assert fixture_path.stat().st_size < 10_000
    assert fixture["source"] == "self-authored-fixture"
    assert "not external catalog data" in fixture["description"]
    assert len(fixture["records"]) == 2
    assert all(record["genres"] and record["tags"] for record in fixture["records"])


def test_readme_documents_data_policy_and_attribution() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    manifest = load_json("data/source-manifests/kaggle.steam-store-games-clean.json")

    assert manifest["attribution"]["text"] in readme
    assert "never committed" in readme
    assert "sparse TF-IDF" in readme


def test_gitignore_blocks_real_data_and_model_artifacts_but_not_fixtures() -> None:
    ignored_paths = [
        "data/raw/steam.csv",
        "data/external/catalog.json",
        "data/processed/features.parquet",
        "models/recommender.pkl",
        "artifacts/models/embeddings.npy",
    ]
    tracked_paths = [
        "data/fixtures/ml/sample_games.self-authored.json",
        "data/source-manifests/example.self-authored.json",
    ]

    for path in ignored_paths:
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", path],
            cwd=REPO_ROOT,
            check=False,
        )
        assert result.returncode == 0

    for path in tracked_paths:
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", path],
            cwd=REPO_ROOT,
            check=False,
        )
        assert result.returncode == 1
