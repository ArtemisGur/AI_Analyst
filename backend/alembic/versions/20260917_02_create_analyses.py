"""Persist dated analysis history."""

import sqlalchemy as sa

from alembic import op

revision = "20260917_02"
down_revision = "20260917_01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "analyses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "dataset_id",
            sa.Uuid(),
            sa.ForeignKey("datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question", sa.String(1000), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_analyses_dataset_created", "analyses", ["dataset_id", "created_at"])


def downgrade():
    op.drop_table("analyses")
