from pydantic import BaseModel


class ContactPayload(BaseModel):
    id: int
    label: str
    value: str
    href: str
    visible: bool
    sort_order: int

    model_config = {"from_attributes": True}
