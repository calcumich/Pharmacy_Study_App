"""
Models for the core drug domain: drug_classes, attribute_types, drugs, and
the list-shape attribute tables (drug_indications, drug_adrs, drug_metabolism).

All Postgres enums are mapped with create_type=False — the types are created by
001_core_schema.sql and must already exist in the DB.
"""
import enum
import uuid
from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


# ── Python-side enum mirrors ──────────────────────────────────────────────────

class AttributeShape(str, enum.Enum):
    scalar = "scalar"
    list = "list"
    relational = "relational"


# ── Postgres enum types (create_type=False: already created by migration) ─────

_attribute_shape_pg = ENUM(
    AttributeShape,
    name="attribute_shape",
    create_type=False,
)


# ── drug_classes ──────────────────────────────────────────────────────────────

class DrugClass(Base):
    __tablename__ = "drug_classes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")
    )
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    slug: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("drug_classes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    description: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )

    children: Mapped[list["DrugClass"]] = relationship("DrugClass", back_populates="parent")
    parent: Mapped[Optional["DrugClass"]] = relationship(
        "DrugClass", back_populates="children", remote_side="DrugClass.id"
    )
    drugs: Mapped[list["Drug"]] = relationship("Drug", back_populates="drug_class")

    __table_args__ = (
        sa.Index("idx_drug_classes_parent_id", "parent_id"),
    )


# ── attribute_types ───────────────────────────────────────────────────────────

class AttributeType(Base):
    __tablename__ = "attribute_types"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")
    )
    slug: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)
    label: Mapped[str] = mapped_column(sa.Text, nullable=False)
    shape: Mapped[AttributeShape] = mapped_column(_attribute_shape_pg, nullable=False)
    source_table: Mapped[str] = mapped_column(sa.Text, nullable=False)
    is_system: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("TRUE")
    )
    display_order: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )

    # Back-ref from flashcard_state; "FlashcardState" resolved lazily from registry.
    flashcard_states: Mapped[list["FlashcardState"]] = relationship(  # noqa: F821
        "FlashcardState", back_populates="attribute_type"
    )


# ── drugs ─────────────────────────────────────────────────────────────────────

class Drug(Base):
    __tablename__ = "drugs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")
    )
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    generic_name: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    drug_class_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("drug_classes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    # Intentional JSONB escape hatch — see docs/schema.md. Do not flatten.
    attributes: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    # Maintained by DB trigger trg_drugs_search_vector — never write from application.
    search_vector: Mapped[Optional[str]] = mapped_column(TSVECTOR, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )

    drug_class: Mapped[Optional[DrugClass]] = relationship("DrugClass", back_populates="drugs")
    indications: Mapped[list["DrugIndication"]] = relationship(
        "DrugIndication", back_populates="drug", cascade="all, delete-orphan"
    )
    adrs: Mapped[list["DrugAdr"]] = relationship(
        "DrugAdr", back_populates="drug", cascade="all, delete-orphan"
    )
    metabolism: Mapped[list["DrugMetabolism"]] = relationship(
        "DrugMetabolism", back_populates="drug", cascade="all, delete-orphan"
    )

    __table_args__ = (
        sa.Index("idx_drugs_search_vector", "search_vector", postgresql_using="gin"),
        sa.Index("idx_drugs_drug_class_id", "drug_class_id"),
        sa.Index(
            "idx_drugs_name_trgm", "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )


# ── drug_indications ──────────────────────────────────────────────────────────

class DrugIndication(Base):
    __tablename__ = "drug_indications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")
    )
    drug_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("drugs.id", ondelete="CASCADE"),
        nullable=False,
    )
    value: Mapped[str] = mapped_column(sa.Text, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)

    drug: Mapped[Drug] = relationship("Drug", back_populates="indications")

    __table_args__ = (
        sa.UniqueConstraint("drug_id", "value"),
        sa.Index("idx_drug_indications_drug_id", "drug_id"),
    )


# ── drug_adrs ─────────────────────────────────────────────────────────────────

class DrugAdr(Base):
    __tablename__ = "drug_adrs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")
    )
    drug_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("drugs.id", ondelete="CASCADE"),
        nullable=False,
    )
    value: Mapped[str] = mapped_column(sa.Text, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)

    drug: Mapped[Drug] = relationship("Drug", back_populates="adrs")

    __table_args__ = (
        sa.UniqueConstraint("drug_id", "value"),
        sa.Index("idx_drug_adrs_drug_id", "drug_id"),
    )


# ── drug_metabolism ───────────────────────────────────────────────────────────

class DrugMetabolism(Base):
    __tablename__ = "drug_metabolism"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")
    )
    drug_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("drugs.id", ondelete="CASCADE"),
        nullable=False,
    )
    value: Mapped[str] = mapped_column(sa.Text, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)

    drug: Mapped[Drug] = relationship("Drug", back_populates="metabolism")

    __table_args__ = (
        sa.UniqueConstraint("drug_id", "value"),
        sa.Index("idx_drug_metabolism_drug_id", "drug_id"),
    )
