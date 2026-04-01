from uuid import UUID
from typing import Any, Optional
from pydantic import BaseModel


class DrugSummary(BaseModel):
    id: UUID
    name: str
    generic_name: Optional[str] = None
    drug_class_id: Optional[UUID] = None

    model_config = {"from_attributes": True}


class DrugDetail(BaseModel):
    id: UUID
    name: str
    generic_name: Optional[str] = None
    drug_class_id: Optional[UUID] = None
    attributes: dict[str, Any] = {}
    indications: list[str] = []
    adrs: list[str] = []
    metabolism: list[str] = []

    model_config = {"from_attributes": True}
