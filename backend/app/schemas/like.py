from pydantic import BaseModel, ConfigDict


class LikeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    likes: int
    was_new: bool
