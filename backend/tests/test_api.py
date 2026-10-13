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


def test_readiness_checks_database_and_counts_catalog(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["database"] == "ok"
    assert response.json()["demoCatalogItems"] >= 6
