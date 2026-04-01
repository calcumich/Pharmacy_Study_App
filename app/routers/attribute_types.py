from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.drugs import AttributeType
from app.schemas.attribute_types import AttributeTypeResponse

router = APIRouter(prefix="/attribute-types", tags=["attribute-types"])


@router.get("", response_model=list[AttributeTypeResponse])
async def list_attribute_types(
    db: AsyncSession = Depends(get_db),
) -> list[AttributeTypeResponse]:
    """Return all attribute types ordered by display_order."""
    result = await db.execute(
        select(AttributeType).order_by(AttributeType.display_order)
    )
    return result.scalars().all()
