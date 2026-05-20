"""Runtime tables — written by the agent as users interact.

These are the only tables the chatbot writes to in Phases 1-2. Schema is
defined now so we don't have to migrate later, but they stay empty until
Phase 2 plugs the LangGraph agent into them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CHAR,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Conversation(Base):
    """One row per browser session.

    `session_uuid` is generated client-side and stored in localStorage so
    a returning user resumes their last conversation. `state` is a slim
    denormalized mirror of the LangGraph checkpointer's payload — kept
    for analytics queries without unpacking the checkpoint blob.
    """

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_uuid: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), nullable=False, unique=True
    )
    user_email: Mapped[str | None] = mapped_column(Text)
    user_company: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str] = mapped_column(
        CHAR(2), nullable=False, default="EN", server_default="EN"
    )
    main_type_code: Mapped[str | None] = mapped_column(
        Text, ForeignKey("main_conversation_types.code")
    )
    current_node: Mapped[str | None] = mapped_column(Text)
    state: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    outcome: Mapped[str | None] = mapped_column(Text)
    ticket_id: Mapped[str | None] = mapped_column(Text)
    # Phase 4: provider-agnostic pointers to side-effect records.
    rfq_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("rfqs.id", ondelete="SET NULL")
    )
    division_code: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # `session_uuid` already has a unique index from the column definition.
        Index(
            "ix_conversations_user_email_present",
            "user_email",
            postgresql_where=text("user_email IS NOT NULL"),
        ),
        Index("ix_conversations_started_at", "started_at"),
    )


class Message(Base):
    """One row per turn in a conversation — user, bot, or system."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    node: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        Index(
            "ix_messages_conversation_id_created_at",
            "conversation_id",
            "created_at",
        ),
    )
