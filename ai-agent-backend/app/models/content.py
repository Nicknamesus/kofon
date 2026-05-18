"""Content tables — seeded by domain experts, read by the agent.

Names mirror `DB_structure_17-05-26.pdf` so the mapping is one-to-one.
Embedding tables (`product_embeddings`, `problem_embeddings`) are deferred
to Phase 3 along with the KB-search work.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class MainConversationType(Base):
    """One row per primary branch in the routing diagram.

    Codes: 'presales' | 'guide' | 'postsales' | 'other'.
    Seeded once. Referenced by `conversations.main_type_code`.
    """

    __tablename__ = "main_conversation_types"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    greeting_key: Mapped[str] = mapped_column(Text, nullable=False)


class UseCase(Base):
    """An (industry, application) context the chatbot can match a user to.

    `(industry, application)` is the natural key used by the seed loader to
    upsert; the surrogate `id` keeps FKs short.
    """

    __tablename__ = "use_cases"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    industry: Mapped[str] = mapped_column(Text, nullable=False)
    application: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint(
            "industry", "application", name="uq_use_cases_industry_application"
        ),
    )


class ProductType(Base):
    """A product family (CaesarPlanetary, Rollsate, ...).

    `spec_schema` declares which spec keys instances of this family expose,
    so the configurator UI can render the right inputs.
    """

    __tablename__ = "product_types"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    family: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    spec_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class UseCaseProductType(Base):
    """Pre-curated fit between a use case and a product family."""

    __tablename__ = "use_case_product_types"

    use_case_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("use_cases.id", ondelete="CASCADE"),
        primary_key=True,
    )
    product_type_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("product_types.id", ondelete="CASCADE"),
        primary_key=True,
    )
    fit_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "fit_score BETWEEN 1 AND 5",
            name="ck_use_case_product_types_fit_score",
        ),
    )


class Product(Base):
    """A concrete SKU. `specs` holds family-specific keys per `product_types.spec_schema`."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sku: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    product_type_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("product_types.id"),
        index=True,
    )
    specs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    datasheet_url: Mapped[str | None] = mapped_column(Text)
    cad_url: Mapped[str | None] = mapped_column(Text)
    lead_time_days: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="active",
        server_default="active",
    )


class ProblemType(Base):
    """A known failure mode for a product family.

    Unique per (family, code) so we can address it as
    `caesarplanetary.backlash_exceeds_spec` etc.
    """

    __tablename__ = "problem_types"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    product_type_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("product_types.id"),
        index=True,
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "product_type_id", "code", name="uq_problem_types_product_code"
        ),
        CheckConstraint(
            "severity BETWEEN 1 AND 5", name="ck_problem_types_severity"
        ),
    )


class Solution(Base):
    """One or more validated fixes per problem type.

    `confidence` feeds the partially-deterministic 'easily fixable?' gate
    in Phase 3 (the LLM doesn't get to judge that on its own).
    """

    __tablename__ = "solutions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    problem_type_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("problem_types.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    escalate_if: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    sop_url: Mapped[str | None] = mapped_column(Text)
    rma_template_url: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "confidence BETWEEN 1 AND 5", name="ck_solutions_confidence"
        ),
    )
