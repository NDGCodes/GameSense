import json
from pathlib import Path

import pytest

from app.ml_bundle import BundleError, build_tfidf_content_bundle, load_content_bundle
from app.ml_pipeline import normalize_steam_store_games, steam_store_source_check, validate_normalized, write_json

REPO_ROOT = Path(__file__).resolve().parents[2]
KAGGLE_MANIFEST = REPO_ROOT / "data/source-manifests/kaggle.steam-store-games-clean.json"


def write_tiny_steam_dataset(dataset_dir: Path) -> None:
    dataset_dir.mkdir(parents=True, exist_ok=True)
    (dataset_dir / "steam.csv").write_text(
        "\n".join(
            [
                "appid,name,release_date,english,developer,publisher,platforms,categories,genres,steamspy_tags,positive,negative,average_playtime,median_playtime,owners,price",
                "10,Forest Farm,May 1 2019,1,Example Dev,Example Pub,windows;mac,Single-player;Steam Achievements,Simulation;Indie,Relaxing;Farming;Crafting,120,5,42,30,20000 .. 50000,9.99",
                "20,Harbor Builder,Apr 4 2018,0,Example Dev,Example Pub,windows,Single-player;Steam Cloud,Simulation;Strategy,Management;Crafting;Relaxing,80,10,50,35,20000 .. 50000,12.99",
                "30,Arena Rockets,Mar 3 2017,1,Example Dev,Example Pub,windows,Multi-player;Co-op,Action;Sports,Competitive;Co-op;Teamwork,200,20,60,40,50000 .. 100000,0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (dataset_dir / "steam_description_data.csv").write_text(
        "\n".join(
            [
                "steam_appid,short_description,about_the_game,detailed_description",
                "10,Plant crops and craft gentle farm upgrades.,,",
                "20,Build a cozy harbor with workshops and markets.,,",
                "30,Fast team arenas with rocket jumps and co-op drills.,,",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (dataset_dir / "steamspy_tag_data.csv").write_text(
        "\n".join(
            [
                "appid,Relaxing,Farming,Crafting,Management,Competitive,Co-op,Teamwork",
                "10,90,80,70,10,0,0,0",
                "20,75,0,80,85,0,0,0",
                "30,0,0,0,0,90,80,70",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_steam_store_source_check_records_accepted_scope_and_uncertainty() -> None:
    report = steam_store_source_check(KAGGLE_MANIFEST)

    assert report["ok"] is True
    assert report["sourceId"] == "kaggle.steam-store-games-clean"
    assert report["attribution"]["required"] is True
    assert "local Kaggle notebook" in report["acceptedScope"]
    assert report["unresolvedUncertainties"]
    assert {finding["code"] for finding in report["findings"]} == {"accepted_upstream_uncertainty"}


def test_normalize_steam_store_games_uses_schema_compatible_tiny_csvs(tmp_path: Path) -> None:
    write_tiny_steam_dataset(tmp_path)

    normalized = normalize_steam_store_games(KAGGLE_MANIFEST, tmp_path)

    assert normalized["rowCount"] == 3
    assert normalized["sourceId"] == "kaggle.steam-store-games-clean"
    assert [game["slug"] for game in normalized["games"]] == ["steam-10", "steam-20", "steam-30"]
    assert normalized["games"][0]["metadata"]["sourceUrl"] == "https://store.steampowered.com/app/10/"
    assert "Single-player" in normalized["games"][0]["tags"]
    assert "Farming" in normalized["games"][0]["tags"]

    normalized_path = tmp_path / "normalized.json"
    write_json(normalized_path, normalized)
    validation = validate_normalized(KAGGLE_MANIFEST, normalized_path)
    assert validation["ok"] is True
    assert validation["validRowCount"] == 3


def test_export_import_bundle_validates_alignment_and_recommends_from_same_snapshot(tmp_path: Path) -> None:
    write_tiny_steam_dataset(tmp_path / "dataset")
    normalized = normalize_steam_store_games(KAGGLE_MANIFEST, tmp_path / "dataset")
    manifest = json.loads(KAGGLE_MANIFEST.read_text(encoding="utf-8"))
    bundle_path = tmp_path / "gamesense-content-bundle.zip"

    build_manifest = build_tfidf_content_bundle(
        games=normalized["games"],
        source_manifest=manifest,
        output_path=bundle_path,
        source_file_hashes={"steam.csv": "self-authored-test-sample"},
        generated_at="2026-10-14T00:00:00Z",
        max_features=200,
        max_item_terms=64,
    )
    bundle = load_content_bundle(bundle_path)

    assert build_manifest["rowCount"] == 3
    assert bundle.source_id == "kaggle.steam-store-games-clean"
    assert bundle.manifest["checksums"]["sourceFiles"] == {"steam.csv": "self-authored-test-sample"}
    assert [game.slug for game in bundle.catalog] == ["steam-10", "steam-20", "steam-30"]
    assert set(bundle.item_vectors) == {"steam-10", "steam-20", "steam-30"}
    assert "Steam Store Games" in bundle.disclosure


def test_catalog_uses_only_documented_bundle_configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.recommender_service import list_games_for_api

    missing_bundle = tmp_path / "missing.zip"
    monkeypatch.setenv("RECOMMENDER_MODE", "content")
    monkeypatch.delenv("CONTENT_BUNDLE_PATH", raising=False)
    monkeypatch.setenv("RECOMMENDER_BUNDLE_PATH", str(missing_bundle))

    assert list_games_for_api(None)

    monkeypatch.setenv("CONTENT_BUNDLE_PATH", str(missing_bundle))
    with pytest.raises(RuntimeError, match="Configured content bundle is invalid"):
        list_games_for_api(None)


@pytest.mark.parametrize("other_tag,expected_slugs", [("Competitive", []), ("Crafting", ["other"])])
def test_similar_fallback_excludes_seed_in_both_content_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, other_tag: str, expected_slugs: list[str],
) -> None:
    from app import recommender_service
    from app.schemas import CatalogGameSchema

    games = [
        CatalogGameSchema(sourceId="kaggle.steam-store-games-clean", sourceGameId="1", slug="seed", title="Unique", tags=["Cozy"]),
        CatalogGameSchema(sourceId="kaggle.steam-store-games-clean", sourceGameId="2", slug="other", title="Separate", tags=[other_tag]),
    ]
    monkeypatch.setattr(recommender_service, "_load_content_games", lambda: games)
    result = recommender_service._content_recommendations(mode="similar", favorite_game="seed", limit=3)
    assert result.fallbackReason == "similar_no_candidates"
    assert [game.slug for game in result.recommendations] == expected_slugs

    bundle_path = tmp_path / "fallback.zip"
    manifest = json.loads(KAGGLE_MANIFEST.read_text(encoding="utf-8"))
    build_tfidf_content_bundle(games=games, source_manifest=manifest, output_path=bundle_path)
    result = recommender_service._bundle_recommendations(
        load_content_bundle(bundle_path), mode="similar", favorite_game="seed", limit=3,
    )
    assert result.fallbackReason == "similar_no_candidates"
    assert [game.slug for game in result.recommendations] == expected_slugs


def test_load_bundle_rejects_id_mapping_mismatch(tmp_path: Path) -> None:
    write_tiny_steam_dataset(tmp_path / "dataset")
    normalized = normalize_steam_store_games(KAGGLE_MANIFEST, tmp_path / "dataset")
    manifest = json.loads(KAGGLE_MANIFEST.read_text(encoding="utf-8"))
    bundle_path = tmp_path / "gamesense-content-bundle.zip"
    build_tfidf_content_bundle(games=normalized["games"], source_manifest=manifest, output_path=bundle_path)

    # Rewrite only catalog.json inside a new zip and keep the old manifest checksums. The loader
    # must fail before the API can silently serve a bundle with shifted IDs.
    import zipfile

    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(bundle_path) as source, zipfile.ZipFile(tampered, "w") as target:
        for name in source.namelist():
            payload = source.read(name)
            if name == "catalog.json":
                catalog = json.loads(payload.decode("utf-8"))
                catalog["idMapping"][0]["slug"] = "wrong-slug"
                payload = json.dumps(catalog).encode("utf-8")
            target.writestr(name, payload)

    with pytest.raises(BundleError, match="checksum mismatch"):
        load_content_bundle(tampered)
