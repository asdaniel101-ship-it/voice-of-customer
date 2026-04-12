import uuid
from datetime import datetime

from pydantic import BaseModel


class MentionResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    source: str
    source_id: str
    author: str | None
    text: str
    url: str | None
    published_at: datetime
    fetched_at: datetime
    language: str

    model_config = {"from_attributes": True}
