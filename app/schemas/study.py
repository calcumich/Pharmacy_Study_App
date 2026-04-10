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
    # TODO: Replace user_id with the identity derived from the Supabase Auth
    # JWT once auth is wired up.  At that point this field should be removed
    # and user_id should be extracted from the request headers in a FastAPI
    # dependency (e.g. `get_current_user`).
    user_id: UUID
    drug_ids: list[UUID]
    mode: Literal["flashcard", "table"]


class SessionResponse(BaseModel):
    session_id: UUID
    started_at: datetime


# ── Flashcard reviews ─────────────────────────────────────────────────────────

class ReviewRequest(BaseModel):
    # TODO: Replace user_id with the identity derived from the Supabase Auth
    # JWT once auth is wired up.  At that point this field should be removed
    # and user_id should be extracted from the request headers in a FastAPI
    # dependency (e.g. `get_current_user`).
    user_id: UUID
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
