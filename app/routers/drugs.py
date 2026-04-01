from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.drugs import Drug
from app.schemas.drugs import DrugDetail

router = APIRouter(prefix="/drugs", tags=["drugs"])


@router.get("/{drug_id}", response_model=DrugDetail)
async def get_drug(drug_id: UUID, db: AsyncSession = Depends(get_db)) -> DrugDetail:
    """Return a single drug with all list-shape attributes loaded."""
    result = await db.execute(
        select(Drug)
        .options(
            selectinload(Drug.indications),
            selectinload(Drug.adrs),
            selectinload(Drug.metabolism),
        )
        .where(Drug.id == drug_id)
    )
    drug = result.scalar_one_or_none()
    if drug is None:
        raise HTTPException(status_code=404, detail="Drug not found")

    return DrugDetail(
        id=drug.id,
        name=drug.name,
        generic_name=drug.generic_name,
        drug_class_id=drug.drug_class_id,
        attributes=drug.attributes,
        indications=[i.value for i in drug.indications],
        adrs=[a.value for a in drug.adrs],
        metabolism=[m.value for m in drug.metabolism],
    )
