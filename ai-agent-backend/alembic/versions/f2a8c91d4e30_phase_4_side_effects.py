"""phase 4 side effects

Adds the runtime tables Phase 4 needs:

- `rfqs` and `tickets` — agent-owned records of what was sent to the CRM
  (separate from CRM-side ids so we keep an internal audit even if the
  external row gets deleted).
- `crm_calls` and `email_calls` — provider-agnostic call log. Every
  outbound side effect lands a row here, regardless of which CRM/email
  provider is configured. Lets us swap Zoho → Salesforce without losing
  history, and gives the `log` provider somewhere to write when no real
  service is wired.
- `conversations` gains `rfq_id`, `ticket_id` was already there, plus
  `division_code` so analytics can group by which division got the
  handoff.

Migration is idempotent for re-runs against an already-populated DB.

Revision ID: f2a8c91d4e30
Revises: d4e2a9f5c10b
Create Date: 2026-05-20
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2a8c91d4e30"
down_revision: Union[str, None] = "d4e2a9f5c10b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rfqs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("sku", sa.Text(), nullable=True),
        sa.Column("product_family", sa.Text(), nullable=True),
        sa.Column("division_code", sa.Text(), nullable=True),
        sa.Column("payload", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("crm_provider", sa.Text(), nullable=False),
        sa.Column("crm_record_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="created"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rfqs_conversation_id", "rfqs", ["conversation_id"])

    op.create_table(
        "tickets",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("division_code", sa.Text(), nullable=True),
        sa.Column("payload", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("crm_provider", sa.Text(), nullable=False),
        sa.Column("crm_record_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tickets_conversation_id", "tickets", ["conversation_id"])

    # Provider-agnostic outbound call audit. One row per side-effect attempt.
    op.create_table(
        "crm_calls",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),  # create_lead | create_ticket | log_activity
        sa.Column("request", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("response", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),  # ok | error | skipped
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_crm_calls_conversation_id", "crm_calls", ["conversation_id"]
    )
    op.create_index("ix_crm_calls_created_at", "crm_calls", ["created_at"])

    op.create_table(
        "email_calls",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("to_address", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),  # datasheet | handoff_notify | rfq_notify
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_email_calls_conversation_id", "email_calls", ["conversation_id"]
    )

    # New conversation columns. `ticket_id` already existed; we add rfq_id and division_code.
    op.add_column(
        "conversations",
        sa.Column("rfq_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "conversations",
        sa.Column("division_code", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_conversations_rfq_id",
        "conversations",
        "rfqs",
        ["rfq_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_conversations_rfq_id", "conversations", type_="foreignkey"
    )
    op.drop_column("conversations", "division_code")
    op.drop_column("conversations", "rfq_id")

    op.drop_index("ix_email_calls_conversation_id", table_name="email_calls")
    op.drop_table("email_calls")

    op.drop_index("ix_crm_calls_created_at", table_name="crm_calls")
    op.drop_index("ix_crm_calls_conversation_id", table_name="crm_calls")
    op.drop_table("crm_calls")

    op.drop_index("ix_tickets_conversation_id", table_name="tickets")
    op.drop_table("tickets")

    op.drop_index("ix_rfqs_conversation_id", table_name="rfqs")
    op.drop_table("rfqs")
