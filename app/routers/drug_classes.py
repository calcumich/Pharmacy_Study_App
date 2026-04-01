from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.drugs import Drug, DrugClass
from app.schemas.drug_classes import DrugClassNode
from app.schemas.drugs import DrugSummary

router = APIRouter(prefix="/drug-classes", tags=["drug-classes"])


@router.get("", response_model=list[DrugClassNode])
async def list_drug_classes(db: AsyncSession = Depends(get_db)) -> list[DrugClassNode]:
    """Return the full drug class hierarchy as a tree."""
    result = await db.execute(select(DrugClass).order_by(DrugClass.name))
    all_classes = result.scalars().all()

    # Build tree from flat list — acceptable here because we load every node.
    by_id: dict[UUID, DrugClassNode] = {
        c.id: DrugClassNode.model_validate(c) for c in all_classes
    }
    roots: list[DrugClassNode] = []
    for c in all_classes:
        node = by_id[c.id]
        if c.parent_id is None:
            roots.append(node)
        else:
            parent = by_id.get(c.parent_id)
            if parent:
                parent.children.append(node)
    return roots


@router.get("/{class_id}/drugs", response_model=list[DrugSummary])
async def list_drugs_by_class(
    class_id: UUID, db: AsyncSession = Depends(get_db)
) -> list[DrugSummary]:
    """Return all drugs belonging to a class or any of its descendants."""
    # Recursive CTE — see docs/schema.md for rationale.
    descendant_cte = text("""
        WITH RECURSIVE descendants AS (
            SELECT id FROM drug_classes WHERE id = :class_id
            UNION ALL
            SELECT dc.id
            FROM drug_classes dc
            JOIN descendants d ON dc.parent_id = d.id
        )
        SELECT id FROM descendants
    """)
    id_result = await db.execute(descendant_cte, {"class_id": class_id})
    class_ids = [row[0] for row in id_result]

    if not class_ids:
        raise HTTPException(status_code=404, detail="Drug class not found")

    drugs_result = await db.execute(
        select(Drug).where(Drug.drug_class_id.in_(class_ids)).order_by(Drug.name)
    )
    return drugs_result.scalars().all()
