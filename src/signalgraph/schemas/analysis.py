import uuid

from pydantic import BaseModel


class ThemeResponse(BaseModel):
    id: uuid.UUID
    name: str
    summary: str
    status: str
    platforms: list
    mention_count: int
    avg_sentiment: float
    legitimacy_score: float | None
    legitimacy_class: str | None

    model_config = {"from_attributes": True}
