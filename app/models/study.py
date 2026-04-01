"""
Models for user study state: srs_state, study_sessions, flashcard_state.

user_id is a plain UUID — no FK to an ORM User model. Auth is Supabase-managed;
the auth.users table is provisioned outside this codebase.

The srs_card_state Postgres enum is mapped with create_type=False.
"""
import enum
import uuid
from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.drugs import Drug, AttributeType


# ── Python-side enum mirror ───────────────────────────────────────────────────

class SrsCardState(str, enum.Enum):
    new = "new"
    learning = "learning"
    review = "review"
    relearning = "relearning"


# ── Postgres enum type ────────────────────────────────────────────────────────

_srs_card_state_pg = ENUM(
    SrsCardState,
    name="srs_card_state",
    create_type=False,
)


# ── srs_state ─────────────────────────────────────────────────────────────────

class SrsState(Base):
    __tablename__ = "srs_state"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")
    )
    # Plain UUID — references auth.users (Supabase-managed), no ORM FK.
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    drug_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("drugs.id", ondelete="CASCADE"),
        nullable=False,
    )

    # FSRS typed fields (see docs/schema.md for field semantics)
    stability: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)
    difficulty: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)
    state: Mapped[SrsCardState] = mapped_column(
        _srs_card_state_pg, nullable=False, server_default=sa.text("'new'")
    )
    due_date: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    last_review: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    review_count: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )

    # Safety column — extend here first if FSRS algorithm evolves.
    srs_data: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )

    drug: Mapped[Drug] = relationship("Drug")

    __table_args__ = (
        sa.UniqueConstraint("user_id", "drug_id"),
        sa.Index("idx_srs_state_user_id", "user_id"),
        sa.Index("idx_srs_state_due_date", "due_date"),
    )


# ── study_sessions ────────────────────────────────────────────────────────────
# Append-only. Do not add UPDATE logic — see docs/schema.md.

class StudySession(Base):
    __tablename__ = "study_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    # JSONB array of drug UUIDs studied in this session.
    drug_ids_studied: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
    )
    session_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )

    __table_args__ = (
        sa.Index("idx_study_sessions_user_id", "user_id"),
        sa.Index("idx_study_sessions_started_at", "started_at"),
    )


# ── flashcard_state ───────────────────────────────────────────────────────────

class FlashcardState(Base):
    __tablename__ = "flashcard_state"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    drug_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("drugs.id", ondelete="CASCADE"),
        nullable=False,
    )
    attribute_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("attribute_types.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_buried: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("FALSE")
    )
    is_flagged: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("FALSE")
    )
    user_note: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )

    drug: Mapped[Drug] = relationship("Drug")
    attribute_type: Mapped[AttributeType] = relationship(
        "AttributeType", back_populates="flashcard_states"
    )

    __table_args__ = (
        sa.UniqueConstraint("user_id", "drug_id", "attribute_type_id"),
        sa.Index("idx_flashcard_state_user_id", "user_id"),
    )
