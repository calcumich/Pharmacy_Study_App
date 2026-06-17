from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field


class DrugClassNode(BaseModel):
    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    direct_drug_count: int = 0
    descendant_drug_count: int = 0
    children: list["DrugClassNode"] = Field(default_factory=list)

    model_config = {"from_attributes": True}
