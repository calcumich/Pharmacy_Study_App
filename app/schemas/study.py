from uuid import UUID
from typing import Any
from pydantic import BaseModel


class TableCell(BaseModel):
    drug_id: UUID
    attribute_type_id: UUID
    # scalar → str | None; list → list[str]; relational → list[dict]
    content: Any


class TableResponse(BaseModel):
    drug_ids: list[UUID]
    attribute_type_ids: list[UUID]
    cells: list[TableCell]
