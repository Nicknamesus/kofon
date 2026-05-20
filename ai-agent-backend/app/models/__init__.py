"""ORM models for the Kofon chatbot backend.

The schema follows `DB_structure_17-05-26.pdf` and `BACKEND_PLAN.md` §2
literally. Models are grouped into two modules by lifecycle:

- `content` — seeded by the domain team, mostly static (read-heavy)
- `runtime` — written by the agent as users interact (read/write)

Importing this package registers all models on `Base.metadata`, which is
what Alembic autogenerate uses to detect schema drift.
"""

from app.models.content import (
    MainConversationType,
    ProblemEmbedding,
    ProblemType,
    Product,
    ProductEmbedding,
    ProductType,
    Solution,
    UseCase,
    UseCaseProductType,
)
from app.models.runtime import Conversation, Message
from app.models.sideeffects import CrmCall, EmailCall, Rfq, Ticket

__all__ = [
    "MainConversationType",
    "UseCase",
    "ProductType",
    "UseCaseProductType",
    "Product",
    "ProblemType",
    "Solution",
    "ProductEmbedding",
    "ProblemEmbedding",
    "Conversation",
    "Message",
    "Rfq",
    "Ticket",
    "CrmCall",
    "EmailCall",
]
