from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ActivityItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    type: str
    actor: str
    target: str | None = None
    meta: dict[str, Any]
    created_at: datetime
