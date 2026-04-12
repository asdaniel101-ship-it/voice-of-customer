import uuid
from datetime import datetime

from pydantic import BaseModel


class BriefResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    run_id: uuid.UUID
    content: dict
    summary: str
    created_at: datetime

    model_config = {"from_attributes": True}
