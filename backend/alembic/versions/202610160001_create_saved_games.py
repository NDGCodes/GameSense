"""Create shared saved-game list.

Revision ID: 202610160001
Revises: 202510130001
"""

from alembic import op
import sqlalchemy as sa

revision = "202610160001"
down_revision = "202510130001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_games",
        sa.Column("slug", sa.String(length=160), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("saved_games")
