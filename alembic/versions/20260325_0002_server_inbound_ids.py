"""add servers.inbound_ids

Revision ID: 20260325_0002
Revises: 20260307_0001
Create Date: 2026-03-25 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260325_0002"
down_revision = "20260307_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("servers", sa.Column("inbound_ids", sa.String(length=255), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("servers", "inbound_ids")

