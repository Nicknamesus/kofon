"""add product_page_url to product_types

Revision ID: a7b1c2d3e4f5
Revises: f2a8c91d4e30
Create Date: 2026-05-23
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7b1c2d3e4f5"
down_revision: Union[str, None] = "f2a8c91d4e30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "product_types",
        sa.Column("product_page_url", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("product_types", "product_page_url")
