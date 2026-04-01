from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.drugs import AttributeType, Drug, DrugAdr, DrugIndication, DrugMetabolism
from app.models.interactions import DrugInteraction
from app.schemas.study import TableCell, TableResponse

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
