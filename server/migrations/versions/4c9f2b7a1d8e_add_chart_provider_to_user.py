"""Add chart provider preference to user

Revision ID: 4c9f2b7a1d8e
Revises: 8f3c1a2b4d5e
Create Date: 2026-08-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4c9f2b7a1d8e"
down_revision: Union[str, None] = "8f3c1a2b4d5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if "chart_provider" in {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("user")
    }:
        return

    op.add_column(
        "user",
        sa.Column(
            "chart_provider",
            sa.String(length=20),
            nullable=False,
            server_default="chartjs",
        ),
    )


def downgrade() -> None:
    op.drop_column("user", "chart_provider")