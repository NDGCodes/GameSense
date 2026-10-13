"""Create canonical catalog foundation tables.

Revision ID: 202510130001
Revises: 202510110001
Create Date: 2025-10-13 00:01:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "202510130001"
down_revision = "202510110001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalog_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("manifest_version", sa.Integer(), nullable=False),
        sa.Column("manifest_uri", sa.String(length=500), nullable=True),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("license_and_terms", sa.JSON(), nullable=False),
        sa.Column("attribution", sa.JSON(), nullable=False),
        sa.Column("allowed_uses", sa.JSON(), nullable=False),
        sa.Column("retrieval", sa.JSON(), nullable=False),
        sa.Column("review", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("source_id", name="uq_catalog_sources_source_id"),
    )
    op.create_index("ix_catalog_sources_source_id", "catalog_sources", ["source_id"], unique=True)

    op.create_table(
        "games",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_pk", sa.Integer(), nullable=False),
        sa.Column("source_game_id", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("genres", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("platforms", sa.JSON(), nullable=False),
        sa.Column("release_date", sa.String(length=40), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["source_pk"], ["catalog_sources.id"], name="fk_games_source_pk_catalog_sources"),
        sa.UniqueConstraint("slug", name="uq_games_slug"),
        sa.UniqueConstraint("source_pk", "source_game_id", name="uq_games_source_source_game_id"),
    )
    op.create_index("ix_games_slug", "games", ["slug"], unique=True)
    op.create_index("ix_games_source_pk", "games", ["source_pk"])

    op.create_table(
        "game_features",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("feature_version", sa.String(length=80), nullable=False),
        sa.Column("text_features", sa.JSON(), nullable=False),
        sa.Column("categorical_features", sa.JSON(), nullable=False),
        sa.Column("numeric_features", sa.JSON(), nullable=False),
        sa.Column("vector_features", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], name="fk_game_features_game_id_games"),
        sa.UniqueConstraint("game_id", "feature_version", name="uq_game_features_game_version"),
    )
    op.create_index("ix_game_features_game_id", "game_features", ["game_id"])

    op.create_table(
        "recommendation_artifacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("artifact_id", sa.String(length=160), nullable=False),
        sa.Column("artifact_type", sa.String(length=80), nullable=False),
        sa.Column("source_pk", sa.Integer(), nullable=True),
        sa.Column("feature_version", sa.String(length=80), nullable=True),
        sa.Column("artifact_uri", sa.String(length=500), nullable=True),
        sa.Column("training_source_ids", sa.JSON(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="registered"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["source_pk"], ["catalog_sources.id"], name="fk_recommendation_artifacts_source_pk_catalog_sources"),
        sa.UniqueConstraint("artifact_id", name="uq_recommendation_artifacts_artifact_id"),
    )
    op.create_index(
        "ix_recommendation_artifacts_artifact_id",
        "recommendation_artifacts",
        ["artifact_id"],
        unique=True,
    )
    op.create_index("ix_recommendation_artifacts_source_pk", "recommendation_artifacts", ["source_pk"])


def downgrade() -> None:
    op.drop_index("ix_recommendation_artifacts_source_pk", table_name="recommendation_artifacts")
    op.drop_index("ix_recommendation_artifacts_artifact_id", table_name="recommendation_artifacts")
    op.drop_table("recommendation_artifacts")
    op.drop_index("ix_game_features_game_id", table_name="game_features")
    op.drop_table("game_features")
    op.drop_index("ix_games_source_pk", table_name="games")
    op.drop_index("ix_games_slug", table_name="games")
    op.drop_table("games")
    op.drop_index("ix_catalog_sources_source_id", table_name="catalog_sources")
    op.drop_table("catalog_sources")
