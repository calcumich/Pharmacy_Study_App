from uuid import UUID
from typing import Optional
from pydantic import BaseModel


class DrugClassNode(BaseModel):
    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    children: list["DrugClassNode"] = []

    model_config = {"from_attributes": True}
