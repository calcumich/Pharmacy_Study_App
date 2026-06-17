from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
import sqlalchemy as sa
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.drugs import Drug, DrugClass
from app.schemas.drug_classes import DrugClassNode
from app.schemas.drugs import DrugSummary

router = APIRouter(prefix="/drug-classes", tags=["drug-classes"])


@router.get("", response_model=list[DrugClassNode])
async def list_drug_classes(db: AsyncSession = Depends(get_db)) -> list[DrugClassNode]:
    """Return studyable drug classes as a tree.

    Empty classes are filtered by descendant drug count so users do not click
    through category chains that have no drugs at the leaves.
    """
    result = await db.execute(select(DrugClass).order_by(DrugClass.name))
    all_classes = result.scalars().all()

    count_result = await db.execute(
        select(Drug.drug_class_id, sa.func.count(Drug.id))
        .where(Drug.drug_class_id.is_not(None))
        .group_by(Drug.drug_class_id)
    )
    direct_counts = {class_id: count for class_id, count in count_result.all()}

    return _build_drug_class_tree(all_classes, direct_counts)


def _build_drug_class_tree(
    all_classes: list[DrugClass],
    direct_counts: dict[UUID, int],
) -> list[DrugClassNode]:
    # Build tree from flat list — acceptable here because we load every node.
    by_id: dict[UUID, DrugClassNode] = {
        c.id: DrugClassNode(
            id=c.id,
            name=c.name,
            slug=c.slug,
            description=c.description,
            direct_drug_count=direct_counts.get(c.id, 0),
            descendant_drug_count=direct_counts.get(c.id, 0),
        )
        for c in all_classes
    }
    children_by_parent: dict[UUID, list[DrugClass]] = {}
    for c in all_classes:
        if c.parent_id is not None and c.parent_id in by_id:
            children_by_parent.setdefault(c.parent_id, []).append(c)

    def descendant_count(class_id: UUID) -> int:
        node = by_id[class_id]
        total = node.direct_drug_count
        for child in children_by_parent.get(class_id, []):
            total += descendant_count(child.id)
        node.descendant_drug_count = total
        return total

    for c in all_classes:
        descendant_count(c.id)

    roots: list[DrugClassNode] = []
    for c in all_classes:
        node = by_id[c.id]
        if node.descendant_drug_count == 0:
            continue
        if c.parent_id is None:
            roots.append(node)
        else:
            parent = by_id.get(c.parent_id)
            if parent and parent.descendant_drug_count > 0:
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
