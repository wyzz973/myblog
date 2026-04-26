from pydantic import BaseModel


class ProjectPayload(BaseModel):
    name: str
    desc: str
    lang: str
    stars: int
    status: str
