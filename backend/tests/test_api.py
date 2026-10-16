import json
from pathlib import Path
import sys

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.db import get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.ml_bundle import build_tfidf_content_bundle  # noqa: E402
from app.ml_pipeline import normalize_steam_store_games  # noqa: E402
from app.recommender_service import clear_content_bundle_cache  # noqa: E402


def run_migrations(database_url: str) -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def build_test_client(tmp_path: Path) -> TestClient:
    database_url = f"sqlite:///{tmp_path / 'gamesense-test.db'}"
    run_migrations(database_url)
    engine = create_engine(database_url, connect_args={"check_same_thread": False}, future=True)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def override_get_session():
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app)


def test_alembic_migration_creates_labeled_demo_fixtures(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'migration-test.db'}"
    run_migrations(database_url)
    engine = create_engine(database_url, future=True)

    with engine.connect() as connection:
        rows = connection.execute(text("SELECT slug, source FROM demo_games ORDER BY slug")).mappings().all()

    assert len(rows) >= 6
    assert {row["source"] for row in rows} == {"demo-fixture"}


def test_recommendations_come_from_demo_database_fixtures(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("RECOMMENDER_MODE", raising=False)
    client = build_test_client(tmp_path)

    response = client.post(
        "/api/recommendations",
        json={"mode": "cozy", "favorite_game": "Cozy Comet Cafe"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "cozy"
    assert payload["favoriteGame"] == "Cozy Comet Cafe"
    assert "Demo fixture catalog only" in payload["fixtureNotice"]
    assert payload["algorithm"] == "demo-fixture-rules"
    assert payload["version"] == "gamesense-demo-fixture-rules-v1"
    assert payload["dataSnapshot"] == "demo-database-fixtures"
    assert payload["disclosure"] == payload["fixtureNotice"]
    assert len(payload["recommendations"]) >= 2
    assert {game["source"] for game in payload["recommendations"]} == {"demo-fixture"}
    assert all(
        game["imageUrl"] is None and game["steamAppId"] is None and game["imageFallbackUrl"] is None
        for game in payload["recommendations"]
    )


def test_content_recommender_mode_uses_self_authored_sample_and_grounded_reasons(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RECOMMENDER_MODE", "content")
    client = build_test_client(tmp_path)

    response = client.post(
        "/api/recommendations",
        json={"mode": "cozy", "favorite_game": "Moonlit Market"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "cozy"
    assert payload["algorithm"] == "content-baseline-rrf"
    assert payload["version"] == "gamesense-local-baseline-recommender-v1"
    assert payload["dataSnapshot"] == "gamesense-ml-self-authored-smoke-v1"
    assert "tiny self-authored smoke fixture" in payload["disclosure"]
    assert "Kaggle" in payload["disclosure"]
    assert payload["fixtureNotice"]
    assert payload["recommendations"][0]["source"] == "gamesense-self-authored-smoke-fixture"
    assert "Evidence fields:" in payload["recommendations"][0]["reason"]
    assert "Score source:" in payload["recommendations"][0]["reason"]

    metrics = client.get("/metrics").text
    assert 'gamesense_recommendation_requests_total{algorithm="content-baseline-rrf",data_snapshot="gamesense-ml-self-authored-smoke-v1",mode="cozy",version="gamesense-local-baseline-recommender-v1"}' in metrics
    assert 'gamesense_recommendation_catalog_items{algorithm="content-baseline-rrf",data_snapshot="gamesense-ml-self-authored-smoke-v1"} 2.0' in metrics
    assert 'gamesense_recommendation_model_info{algorithm="content-baseline-rrf",data_snapshot="gamesense-ml-self-authored-smoke-v1",version="gamesense-local-baseline-recommender-v1"} 1.0' in metrics


def test_content_recommender_fallback_metric_uses_bounded_reason(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RECOMMENDER_MODE", "content")
    client = build_test_client(tmp_path)

    response = client.post(
        "/api/recommendations",
        json={"mode": "similar", "favorite_game": "Unknown Game"},
    )

    assert response.status_code == 200
    metrics = client.get("/metrics").text
    assert 'gamesense_recommendation_fallbacks_total{algorithm="content-baseline-rrf",reason="similar_seed_not_found"}' in metrics
    assert "Unknown Game" not in metrics


def test_content_recommender_loads_returned_bundle_for_catalog_and_recommendations(tmp_path: Path, monkeypatch) -> None:
    dataset_dir = tmp_path / "steam-sample"
    dataset_dir.mkdir()
    (dataset_dir / "steam.csv").write_text(
        "appid,name,release_date,english,developer,publisher,platforms,categories,genres,steamspy_tags,positive,negative,average_playtime,median_playtime,owners,price\n"
        "10,Forest Farm,May 1 2019,1,Example Dev,Example Pub,windows,Single-player,Simulation;Indie,Relaxing;Farming;Crafting,120,5,42,30,20000 .. 50000,9.99\n"
        "20,Harbor Builder,Apr 4 2018,1,Example Dev,Example Pub,windows,Single-player,Simulation;Strategy,Management;Crafting;Relaxing,80,10,50,35,20000 .. 50000,12.99\n"
        "30,Arena Rockets,Mar 3 2017,1,Example Dev,Example Pub,windows,Multi-player;Co-op,Action;Sports,Competitive;Co-op;Teamwork,200,20,60,40,50000 .. 100000,0\n",
        encoding="utf-8",
    )
    (dataset_dir / "steam_description_data.csv").write_text(
        "steam_appid,short_description\n"
        "10,Plant crops and craft gentle farm upgrades.\n"
        "20,Build a cozy harbor with workshops and markets.\n"
        "30,Fast team arenas with rocket jumps and co-op drills.\n",
        encoding="utf-8",
    )
    manifest_path = Path(__file__).resolve().parents[2] / "data/source-manifests/kaggle.steam-store-games-clean.json"
    normalized = normalize_steam_store_games(manifest_path, dataset_dir)
    bundle_path = tmp_path / "bundle.zip"
    build_tfidf_content_bundle(
        games=normalized["games"],
        source_manifest=json.loads(manifest_path.read_text(encoding="utf-8")),
        output_path=bundle_path,
        generated_at="2026-10-14T00:00:00Z",
    )

    monkeypatch.setenv("RECOMMENDER_MODE", "content")
    monkeypatch.setenv("CONTENT_BUNDLE_PATH", str(bundle_path))
    clear_content_bundle_cache()
    client = build_test_client(tmp_path)

    catalog_response = client.get("/api/games?limit=10&q=Harbor")
    assert catalog_response.status_code == 200
    catalog = catalog_response.json()
    assert [game["slug"] for game in catalog] == ["steam-20"]
    assert catalog[0]["source"] == "kaggle.steam-store-games-clean"
    assert catalog[0]["steamAppId"] == "20"
    assert catalog[0]["imageUrl"].endswith("/20/header.jpg")
    assert catalog[0]["imageFallbackUrl"].endswith("/20/capsule_231x87.jpg")
    assert "loaded Kaggle snapshot bundle" in catalog[0]["reason"]
    assert client.put("/api/saved-games/steam-20").json() == {
        "slug": "steam-20"
    }
    assert client.get("/api/saved-games").json() == [{"slug": "steam-20"}]
    assert client.delete("/api/saved-games/steam-20").status_code == 204

    first_page = client.get("/api/games?limit=1&offset=0").json()
    second_page = client.get("/api/games?limit=1&offset=1").json()
    assert len(first_page) == len(second_page) == 1
    assert first_page[0]["slug"] != second_page[0]["slug"]

    response = client.post("/api/recommendations", json={"mode": "similar", "favorite_game": "Forest Farm", "limit": 9})
    assert response.status_code == 200
    payload = response.json()
    slugs = [game["slug"] for game in payload["recommendations"]]
    for game in payload["recommendations"]:
        assert game["slug"] == f"steam-{game['steamAppId']}"
        assert game["imageUrl"].endswith(f"/{game['steamAppId']}/header.jpg")
        assert game["imageFallbackUrl"].endswith(f"/{game['steamAppId']}/capsule_231x87.jpg")
    assert "steam-10" not in slugs
    assert len(slugs) == 2
    assert payload["algorithm"] == "tfidf-tag-content-baseline"
    assert payload["dataSnapshot"] == "kaggle.steam-store-games-clean-local-snapshot"
    assert "historical" in payload["disclosure"].lower()
    assert {game["source"] for game in payload["recommendations"]} == {"kaggle.steam-store-games-clean"}


def test_readiness_checks_database_and_counts_catalog(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["database"] == "ok"
    assert response.json()["demoCatalogItems"] >= 6


def test_saved_games_put_update_delete_persist_and_validate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RECOMMENDER_MODE", "fixture")
    client = build_test_client(tmp_path)
    slug = client.get("/api/games?limit=1").json()[0]["slug"]

    catalog = client.get("/api/games").json()
    response = client.put(f"/api/saved-games/{slug}")
    assert response.status_code == 200
    assert response.json() == {"slug": slug}
    assert client.put(f"/api/saved-games/{slug}").json() == {"slug": slug}
    client = build_test_client(tmp_path)
    assert client.get("/api/saved-games").json() == [{"slug": slug}]
    assert client.put("/api/saved-games/not-in-catalog").status_code == 404
    assert client.get("/api/games").json() == catalog
    assert client.delete(f"/api/saved-games/{slug}").status_code == 204
    assert client.get("/api/saved-games").json() == []
    assert client.delete(f"/api/saved-games/{slug}").status_code == 404


def test_saved_games_preserve_existing_database_data(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RECOMMENDER_MODE", "fixture")
    client = build_test_client(tmp_path)
    slugs = [game["slug"] for game in client.get("/api/games?limit=2").json()]
    engine = create_engine(f"sqlite:///{tmp_path / 'gamesense-test.db'}", future=True)
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE saved_games ADD COLUMN note VARCHAR(500) NOT NULL DEFAULT ''"))
        connection.execute(
            text("INSERT INTO saved_games (slug, note) VALUES (:slug, :note)"),
            {"slug": slugs[0], "note": "Existing user data"},
        )

    assert client.get("/api/saved-games").json() == [{"slug": slugs[0]}]
    assert client.put(f"/api/saved-games/{slugs[0]}").json() == {"slug": slugs[0]}
    assert client.put(f"/api/saved-games/{slugs[1]}").status_code == 200
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT note FROM saved_games WHERE slug = :slug"), {"slug": slugs[0]}
        ).scalar_one() == "Existing user data"
