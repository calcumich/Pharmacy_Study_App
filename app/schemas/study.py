from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Table mode (read-only, existing) ─────────────────────────────────────────

class TableCell(BaseModel):
    drug_id: UUID
    attribute_type_id: UUID
    # scalar → str | None; list → list[str]; relational → list[dict]
    content: Any


class TableResponse(BaseModel):
    drug_ids: list[UUID]
    attribute_type_ids: list[UUID]
    cells: list[TableCell]


# ── Sessions ──────────────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    drug_ids: list[UUID]
    mode: Literal["flashcard", "table"]


class SessionResponse(BaseModel):
    session_id: UUID
    started_at: datetime


# ── Flashcard reviews ─────────────────────────────────────────────────────────

class ReviewRequest(BaseModel):
    drug_id: UUID
    rating: int = Field(..., ge=1, le=4, description="1=Again 2=Hard 3=Good 4=Easy")
    # Which attribute the user was viewing when they rated.  Stored for
    # context but does not affect the SRS schedule (state is per drug, not
    # per attribute).
    attribute_type_id: Optional[UUID] = None


class ReviewResponse(BaseModel):
    drug_id: UUID
    state: str
    stability: float
    difficulty: float
    due_date: datetime
    review_count: int


# ── Study queue ───────────────────────────────────────────────────────────────

class QueueItem(BaseModel):
    drug_id: UUID
    state: str
    stability: Optional[float]
    due_date: Optional[datetime]


class QueueResponse(BaseModel):
    items: list[QueueItem]


# ── Flashcard state (bury / flag / annotate) ──────────────────────────────────

class FlashcardStateUpdate(BaseModel):
    is_buried: Optional[bool] = None
    is_flagged: Optional[bool] = None
    user_note: Optional[str] = None


class FlashcardStateResponse(BaseModel):
    drug_id: UUID
    attribute_type_id: UUID
    is_buried: bool
    is_flagged: bool
    user_note: Optional[str]
    updated_at: datetime
