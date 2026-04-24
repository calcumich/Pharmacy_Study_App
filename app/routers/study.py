from datetime import datetime, timezone
from uuid import UUID
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.drugs import AttributeType, Drug, DrugAdr, DrugIndication, DrugMetabolism
from app.models.interactions import DrugInteraction
from app.models.study import FlashcardState, SrsCardState, SrsState, StudySession
from app.schemas.study import (
    TableCell, TableResponse,
    SessionCreate, SessionResponse,
    ReviewRequest, ReviewResponse,
    QueueItem, QueueResponse,
    FlashcardStateUpdate, FlashcardStateResponse,
)
from app.services.fsrs import schedule as fsrs_schedule

router = APIRouter(prefix="/study", tags=["study"])

# Map source_table name → SQLAlchemy model for list-shape attributes.
_LIST_MODELS = {
    "drug_indications": DrugIndication,
    "drug_adrs": DrugAdr,
    "drug_metabolism": DrugMetabolism,
}


@router.get("/table", response_model=TableResponse)
async def get_table(
    drug_ids: Annotated[list[UUID], Query()],
    attribute_type_ids: Annotated[list[UUID], Query()],
    db: AsyncSession = Depends(get_db),
) -> TableResponse:
    """
    Return a matrix of { drug_id, attribute_type_id, content } cells for the
    requested drugs × attributes — suitable for table-mode rendering.

    content shape varies by attribute shape:
      scalar     → str | None
      list       → list[str]
      relational → list[{severity, description, partner_id}]
    """
    # Load requested attribute types.
    attr_result = await db.execute(
        select(AttributeType).where(AttributeType.id.in_(attribute_type_ids))
    )
    attr_types = {at.id: at for at in attr_result.scalars().all()}

    # Load drugs (needed for scalar JSONB lookups).
    drug_result = await db.execute(select(Drug).where(Drug.id.in_(drug_ids)))
    drugs = {d.id: d for d in drug_result.scalars().all()}

    drug_id_set = set(drug_ids)
    cells: list[TableCell] = []

    for at_id in attribute_type_ids:
        at = attr_types.get(at_id)
        if at is None:
            for drug_id in drug_ids:
                cells.append(TableCell(drug_id=drug_id, attribute_type_id=at_id, content=None))
            continue

        shape = at.shape.value if hasattr(at.shape, "value") else at.shape

        if shape == "scalar":
            for drug_id in drug_ids:
                drug = drugs.get(drug_id)
                content = drug.attributes.get(at.slug) if drug else None
                cells.append(TableCell(drug_id=drug_id, attribute_type_id=at_id, content=content))

        elif shape == "list":
            model = _LIST_MODELS.get(at.source_table)
            if model is None:
                for drug_id in drug_ids:
                    cells.append(TableCell(drug_id=drug_id, attribute_type_id=at_id, content=[]))
                continue

            rows_result = await db.execute(
                select(model).where(model.drug_id.in_(drug_ids))  # type: ignore[attr-defined]
            )
            by_drug: dict[UUID, list[str]] = {did: [] for did in drug_ids}
            for row in rows_result.scalars().all():
                by_drug[row.drug_id].append(row.value)

            for drug_id in drug_ids:
                cells.append(TableCell(
                    drug_id=drug_id,
                    attribute_type_id=at_id,
                    content=by_drug.get(drug_id, []),
                ))

        elif shape == "relational":
            iact_result = await db.execute(
                select(DrugInteraction).where(
                    or_(
                        DrugInteraction.drug_a_id.in_(drug_ids),
                        DrugInteraction.drug_b_id.in_(drug_ids),
                    )
                )
            )
            interactions = iact_result.scalars().all()

            by_drug_rel: dict[UUID, list[dict]] = {did: [] for did in drug_ids}
            for iact in interactions:
                severity = iact.severity.value if hasattr(iact.severity, "value") else iact.severity
                if iact.drug_a_id in drug_id_set:
                    by_drug_rel[iact.drug_a_id].append({
                        "severity": severity,
                        "description": iact.description,
                        "partner_id": str(iact.drug_b_id),
                    })
                if iact.drug_b_id in drug_id_set:
                    by_drug_rel[iact.drug_b_id].append({
                        "severity": severity,
                        "description": iact.description,
                        "partner_id": str(iact.drug_a_id),
                    })

            for drug_id in drug_ids:
                cells.append(TableCell(
                    drug_id=drug_id,
                    attribute_type_id=at_id,
                    content=by_drug_rel.get(drug_id, []),
                ))

    return TableResponse(
        drug_ids=drug_ids,
        attribute_type_ids=attribute_type_ids,
        cells=cells,
    )


# ── Sessions ──────────────────────────────────────────────────────────────────

@router.post("/sessions", response_model=SessionResponse, status_code=201)
async def create_session(
    body: SessionCreate,
    user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """
    Start a study session.  Returns a session ID the client can attach to
    subsequent review submissions for grouping / analytics.
    """
    session = StudySession(
        user_id=user_id,
        drug_ids_studied=[str(did) for did in body.drug_ids],
        session_metadata={"mode": body.mode},
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionResponse(session_id=session.id, started_at=session.started_at)


# ── Reviews ───────────────────────────────────────────────────────────────────

@router.post("/review", response_model=ReviewResponse, status_code=200)
async def submit_review(
    body: ReviewRequest,
    user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    """
    Record a flashcard rating and advance the FSRS schedule for the drug.

    Loads the current srs_state row (if any), runs the FSRS-5 algorithm, then
    upserts the result.  The SRS state is tracked per (user, drug); the
    optional attribute_type_id is stored for context only.
    """
    now = datetime.now(timezone.utc)

    # Load existing state, if the user has reviewed this drug before.
    result = await db.execute(
        select(SrsState).where(
            SrsState.user_id == user_id,
            SrsState.drug_id == body.drug_id,
        )
    )
    existing: Optional[SrsState] = result.scalar_one_or_none()

    scheduled = fsrs_schedule(
        stability=existing.stability if existing else None,
        difficulty=existing.difficulty if existing else None,
        state=existing.state if existing else SrsCardState.new,
        review_count=existing.review_count if existing else 0,
        last_review=existing.last_review if existing else None,
        rating=body.rating,
        now=now,
    )

    # Upsert — one row per (user_id, drug_id), updated on every review.
    srs_data = scheduled.srs_data
    if body.attribute_type_id is not None:
        srs_data = {**srs_data, "attribute_type_id": str(body.attribute_type_id)}

    stmt = (
        pg_insert(SrsState)
        .values(
            user_id=user_id,
            drug_id=body.drug_id,
            stability=scheduled.stability,
            difficulty=scheduled.difficulty,
            state=scheduled.state,
            due_date=scheduled.due_date,
            last_review=scheduled.last_review,
            review_count=scheduled.review_count,
            srs_data=srs_data,
        )
        .on_conflict_do_update(
            index_elements=["user_id", "drug_id"],
            set_={
                "stability":    scheduled.stability,
                "difficulty":   scheduled.difficulty,
                "state":        scheduled.state,
                "due_date":     scheduled.due_date,
                "last_review":  scheduled.last_review,
                "review_count": scheduled.review_count,
                "srs_data":     srs_data,
                "updated_at":   now,
            },
        )
    )
    await db.execute(stmt)
    await db.commit()

    return ReviewResponse(
        drug_id=body.drug_id,
        state=scheduled.state.value,
        stability=scheduled.stability,
        difficulty=scheduled.difficulty,
        due_date=scheduled.due_date,
        review_count=scheduled.review_count,
    )


# ── Queue ─────────────────────────────────────────────────────────────────────

@router.get("/queue", response_model=QueueResponse)
async def get_queue(
    user_id: UUID = Depends(get_current_user),
    drug_ids: Annotated[Optional[list[UUID]], Query()] = None,
    limit: int = Query(default=20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> QueueResponse:
    """
    Return cards due for review, most overdue first.

    A card is due when due_date <= now, or when due_date IS NULL (never
    reviewed — treated as immediately due).  Pass drug_ids to restrict the
    queue to a specific study set; omit to return across all studied drugs.
    """
    now = datetime.now(timezone.utc)

    # Cards are due when:
    #   - due_date has passed (normal review cadence), OR
    #   - due_date is NULL (never reviewed), OR
    #   - state is learning/relearning — these always surface regardless of
    #     due_date so "Again" puts a card back into the active session queue.
    _short_term_states = (SrsCardState.learning, SrsCardState.relearning)
    query = (
        select(SrsState)
        .where(
            SrsState.user_id == user_id,
            or_(
                SrsState.due_date <= now,
                SrsState.due_date.is_(None),
                SrsState.state.in_(_short_term_states),
            ),
        )
        .order_by(SrsState.due_date.asc().nulls_first())
        .limit(limit)
    )
    if drug_ids:
        query = query.where(SrsState.drug_id.in_(drug_ids))

    rows = (await db.execute(query)).scalars().all()

    return QueueResponse(
        items=[
            QueueItem(
                drug_id=row.drug_id,
                state=row.state.value,
                stability=row.stability,
                due_date=row.due_date,
            )
            for row in rows
        ]
    )


# ── Flashcard state ───────────────────────────────────────────────────────────

@router.patch(
    "/flashcard-state/{drug_id}/{attribute_type_id}",
    response_model=FlashcardStateResponse,
    status_code=201,
)
async def patch_flashcard_state(
    drug_id: UUID,
    attribute_type_id: UUID,
    body: FlashcardStateUpdate,
    user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FlashcardStateResponse:
    """
    Upsert bury / flag / annotation state for one flashcard.

    Only non-None fields in the request body are written on conflict, so
    callers can update a single field without resetting the others.
    """
    now = datetime.now(timezone.utc)

    # Build the conflict-update set from only the fields the caller provided.
    update_fields: dict = {"updated_at": now}
    if body.is_buried is not None:
        update_fields["is_buried"] = body.is_buried
    if body.is_flagged is not None:
        update_fields["is_flagged"] = body.is_flagged
    if body.user_note is not None:
        update_fields["user_note"] = body.user_note

    stmt = (
        pg_insert(FlashcardState)
        .values(
            user_id=user_id,
            drug_id=drug_id,
            attribute_type_id=attribute_type_id,
            is_buried=body.is_buried if body.is_buried is not None else False,
            is_flagged=body.is_flagged if body.is_flagged is not None else False,
            user_note=body.user_note,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["user_id", "drug_id", "attribute_type_id"],
            set_=update_fields,
        )
    )
    await db.execute(stmt)
    await db.commit()

    # Re-fetch to return the authoritative DB state (conflict path may have
    # left some fields unchanged that are not in update_fields).
    row = (await db.execute(
        select(FlashcardState).where(
            FlashcardState.user_id == user_id,
            FlashcardState.drug_id == drug_id,
            FlashcardState.attribute_type_id == attribute_type_id,
        )
    )).scalar_one()

    return FlashcardStateResponse(
        drug_id=row.drug_id,
        attribute_type_id=row.attribute_type_id,
        is_buried=row.is_buried,
        is_flagged=row.is_flagged,
        user_note=row.user_note,
        updated_at=row.updated_at,
    )
