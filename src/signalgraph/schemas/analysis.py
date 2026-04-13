import uuid

from pydantic import BaseModel


class ThemeResponse(BaseModel):
    id: uuid.UUID
    name: str
    summary: str
    status: str
    severity: str | None = "medium"
    platforms: list
    mention_count: int
    avg_sentiment: float
    legitimacy_score: float | None
    legitimacy_class: str | None
    sub_themes: list | None = []
    action_items: list | None = []
    mention_ids: list | None = []

    model_config = {"from_attributes": True}
