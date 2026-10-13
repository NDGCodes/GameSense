import json
from pathlib import Path
import sys

from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas import (  # noqa: E402
    CatalogGameSchema,
    CatalogSourceSchema,
    GameFeatureSchema,
    RecommendationArtifactSchema,
)


def run_migrations(database_url: str) -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def test_sqlite_migrations_create_canonical_catalog_without_changing_demo_fixtures(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'catalog-foundation.db'}"
    run_migrations(database_url)
    engine = create_engine(database_url, future=True)
    inspector = inspect(engine)

    assert {
        "catalog_sources",
        "games",
        "game_features",
        "recommendation_artifacts",
        "demo_games",
    }.issubset(set(inspector.get_table_names()))

    assert {column["name"] for column in inspector.get_columns("catalog_sources")} >= {
        "source_id",
        "manifest_version",
        "provenance",
        "license_and_terms",
        "allowed_uses",
        "retrieval",
        "review",
    }
    assert {column["name"] for column in inspector.get_columns("games")} >= {
        "source_pk",
        "source_game_id",
        "slug",
        "title",
        "genres",
        "tags",
        "platforms",
        "metadata",
    }
    assert {column["name"] for column in inspector.get_columns("game_features")} >= {
        "game_id",
        "feature_version",
        "text_features",
        "categorical_features",
        "numeric_features",
        "vector_features",
    }
    assert {column["name"] for column in inspector.get_columns("recommendation_artifacts")} >= {
        "artifact_id",
        "artifact_type",
        "training_source_ids",
        "parameters",
        "metrics",
        "manifest",
        "status",
    }

    with engine.connect() as connection:
        demo_rows = connection.execute(text("SELECT slug, source FROM demo_games ORDER BY slug")).mappings().all()
        canonical_count = connection.execute(text("SELECT COUNT(*) FROM games")).scalar_one()

    assert len(demo_rows) >= 6
    assert {row["source"] for row in demo_rows} == {"demo-fixture"}
    assert canonical_count == 0


def test_source_manifest_example_validates_as_catalog_source_schema() -> None:
    manifest = json.loads((REPO_ROOT / "data/source-manifests/example.self-authored.json").read_text(encoding="utf-8"))

    source = CatalogSourceSchema.model_validate(manifest)

    assert source.sourceId == "gamesense-self-authored-smoke-fixture"
    assert source.provenance.sourceType == "self-authored"
    assert source.allowedUses.training is False
    assert source.review.state == "approved"


def test_catalog_game_feature_and_artifact_schemas_validate_canonical_records() -> None:
    game = CatalogGameSchema.model_validate(
        {
            "sourceId": "gamesense-self-authored-smoke-fixture",
            "sourceGameId": "fixture-001",
            "slug": "fixture-adventure",
            "title": "Fixture Adventure",
            "description": "Small fictional record for schema validation.",
            "genres": ["Adventure"],
            "tags": ["single-player", "story-rich"],
            "platforms": ["pc"],
            "releaseDate": "2025-10-11",
            "metadata": {"fixture": True},
        }
    )
    features = GameFeatureSchema.model_validate(
        {
            "gameSlug": game.slug,
            "featureVersion": "fixture-v1",
            "textFeatures": {"description": game.description},
            "categoricalFeatures": {"genres": game.genres, "tags": game.tags},
            "numericFeatures": {"popularity": 0.0},
            "vectorFeatures": {"descriptionEmbedding": [0.0, 1.0]},
        }
    )
    artifact = RecommendationArtifactSchema.model_validate(
        {
            "artifactId": "fixture-baseline-v1",
            "artifactType": "baseline",
            "sourceId": game.sourceId,
            "featureVersion": features.featureVersion,
            "trainingSourceIds": [game.sourceId],
            "parameters": {"strategy": "schema-only"},
            "metrics": {"coverage": 1.0},
            "manifest": {"notes": "No trained model artifact is produced in Milestone 1."},
            "status": "validated",
        }
    )

    assert game.metadata == {"fixture": True}
    assert features.vectorFeatures == {"descriptionEmbedding": [0.0, 1.0]}
    assert artifact.artifactType == "baseline"


def test_catalog_schemas_reject_invalid_identifiers() -> None:
    invalid_manifest = json.loads((REPO_ROOT / "data/source-manifests/example.self-authored.json").read_text(encoding="utf-8"))
    invalid_manifest["sourceId"] = "Invalid Source Id"

    try:
        CatalogSourceSchema.model_validate(invalid_manifest)
    except ValidationError as exc:
        assert "sourceId" in str(exc)
    else:
        raise AssertionError("invalid sourceId should fail validation")

    try:
        RecommendationArtifactSchema.model_validate({"artifactId": "bad id", "artifactType": "model"})
    except ValidationError as exc:
        assert "artifactId" in str(exc)
    else:
        raise AssertionError("invalid artifactId should fail validation")
