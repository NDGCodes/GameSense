"""Create the demo game catalog table.

Revision ID: 202510110001
Revises:
Create Date: 2025-10-11 00:01:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "202510110001"
down_revision = None
branch_labels = None
depends_on = None

DEMO_GAMES = [
    {
        "slug": "starforge-skies",
        "title": "Starforge Skies",
        "short_description": "A cooperative space-builder about restoring orbital habitats after a solar storm.",
        "genres": ["Strategy", "Co-op", "Simulation"],
        "modes": ["trending", "similar"],
        "demo_reason": "High demo popularity score and cooperative systems make it useful for infrastructure smoke tests.",
        "source": "demo-fixture",
        "popularity_score": 98,
        "is_active": True,
    },
    {
        "slug": "embervale-tactics",
        "title": "Embervale Tactics",
        "short_description": "Turn-based squad tactics with short roguelite campaigns and readable combat logs.",
        "genres": ["Strategy", "Roguelite", "Tactics"],
        "modes": ["trending", "similar", "competitive"],
        "demo_reason": "Shares strategy tags with other fixtures and exercises competitive-mode filtering.",
        "source": "demo-fixture",
        "popularity_score": 94,
        "is_active": True,
    },
    {
        "slug": "cozy-comet-cafe",
        "title": "Cozy Comet Cafe",
        "short_description": "A gentle management game about brewing tea for travelers on a tiny asteroid.",
        "genres": ["Cozy", "Management", "Simulation"],
        "modes": ["trending", "cozy"],
        "demo_reason": "Hand-labeled as cozy so the UI can prove mode-specific database queries.",
        "source": "demo-fixture",
        "popularity_score": 91,
        "is_active": True,
    },
    {
        "slug": "harbor-harvest",
        "title": "Harbor Harvest",
        "short_description": "A relaxed fishing and farming loop set around a walkable coastal town.",
        "genres": ["Cozy", "Farming", "Adventure"],
        "modes": ["cozy", "similar"],
        "demo_reason": "Provides a second cozy fixture with different tags for recommendation-card rendering.",
        "source": "demo-fixture",
        "popularity_score": 86,
        "is_active": True,
    },
    {
        "slug": "neon-rivals-arena",
        "title": "Neon Rivals Arena",
        "short_description": "A fast 3v3 arena battler focused on readable roles and quick rematches.",
        "genres": ["Action", "Competitive", "Multiplayer"],
        "modes": ["trending", "competitive"],
        "demo_reason": "Competitive-mode fixture used to validate API filtering without trained scoring.",
        "source": "demo-fixture",
        "popularity_score": 89,
        "is_active": True,
    },
    {
        "slug": "gridiron-galaxy",
        "title": "Gridiron Galaxy",
        "short_description": "An arcade sports-management hybrid with asynchronous league challenges.",
        "genres": ["Sports", "Competitive", "Management"],
        "modes": ["competitive", "similar"],
        "demo_reason": "Covers a non-shooter competitive example for broader UI and API test coverage.",
        "source": "demo-fixture",
        "popularity_score": 82,
        "is_active": True,
    },
]


def upgrade() -> None:
    op.create_table(
        "demo_games",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("short_description", sa.Text(), nullable=False),
        sa.Column("genres", sa.JSON(), nullable=False),
        sa.Column("modes", sa.JSON(), nullable=False),
        sa.Column("demo_reason", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="demo-fixture"),
        sa.Column("popularity_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("slug", name="uq_demo_games_slug"),
    )
    op.create_index("ix_demo_games_slug", "demo_games", ["slug"], unique=True)

    demo_games_table = sa.table(
        "demo_games",
        sa.column("slug", sa.String()),
        sa.column("title", sa.String()),
        sa.column("short_description", sa.Text()),
        sa.column("genres", sa.JSON()),
        sa.column("modes", sa.JSON()),
        sa.column("demo_reason", sa.Text()),
        sa.column("source", sa.String()),
        sa.column("popularity_score", sa.Integer()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(demo_games_table, DEMO_GAMES)


def downgrade() -> None:
    op.drop_index("ix_demo_games_slug", table_name="demo_games")
    op.drop_table("demo_games")
