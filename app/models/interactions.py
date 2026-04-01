"""
Model for drug_interactions (relational-shape attribute).

Canonical ordering: drug_a_id < drug_b_id always.
See docs/schema.md for rationale and query pattern.

The interaction_severity Postgres enum is mapped with create_type=False.
"""
import enum
import uuid
from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.drugs import Drug


# ── Python-side enum mirror ───────────────────────────────────────────────────

class InteractionSeverity(str, enum.Enum):
    minor = "minor"
    moderate = "moderate"
    major = "major"
    contraindicated = "contraindicated"


# ── Postgres enum type ────────────────────────────────────────────────────────

_interaction_severity_pg = ENUM(
    InteractionSeverity,
    name="interaction_severity",
    create_type=False,
)


# ── drug_interactions ─────────────────────────────────────────────────────────

class DrugInteraction(Base):
    __tablename__ = "drug_interactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")
    )
    drug_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("drugs.id", ondelete="CASCADE"),
        nullable=False,
    )
    drug_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("drugs.id", ondelete="CASCADE"),
        nullable=False,
    )
    severity: Mapped[InteractionSeverity] = mapped_column(_interaction_severity_pg, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    details: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )

    drug_a: Mapped[Drug] = relationship("Drug", foreign_keys=[drug_a_id])
    drug_b: Mapped[Drug] = relationship("Drug", foreign_keys=[drug_b_id])

    __table_args__ = (
        # Canonical ordering enforced at DB level — drug_a_id < drug_b_id always.
        sa.CheckConstraint("drug_a_id < drug_b_id", name="chk_ddi_canonical_order"),
        sa.UniqueConstraint("drug_a_id", "drug_b_id"),
        sa.Index("idx_ddi_drug_a", "drug_a_id"),
        sa.Index("idx_ddi_drug_b", "drug_b_id"),
    )
