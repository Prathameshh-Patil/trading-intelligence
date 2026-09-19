"""Alerts -- what the socket pushes to every licensed client.

Revision ID: c3d4e5f6a7b8
Revises: b7c2d9e4f1a0
Create Date: 2026-09-19
"""

import sqlalchemy as sa
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b7c2d9e4f1a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tier", sa.String(16), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("symbol", sa.String(32)),
        sa.Column(
            "created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "tier IN ('breaking', 'signal', 'analysis')", name="ck_alerts_tier"
        ),
    )
    op.create_index("ix_alerts_tier", "alerts", ["tier"])
    op.create_index("ix_alerts_created_at", "alerts", ["created_at"])


def downgrade() -> None:
    op.drop_table("alerts")
