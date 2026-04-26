from pydantic import BaseModel


class TagPayload(BaseModel):
    id: str   # slug; "all" is synthetic
    label: str
    n: int    # post count
