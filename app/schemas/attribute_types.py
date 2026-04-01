from uuid import UUID
from pydantic import BaseModel


class AttributeTypeResponse(BaseModel):
    id: UUID
    slug: str
    label: str
    shape: str
    source_table: str
    display_order: int

    model_config = {"from_attributes": True}
