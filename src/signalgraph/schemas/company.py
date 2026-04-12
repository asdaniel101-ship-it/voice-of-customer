import uuid
from datetime import datetime

from pydantic import BaseModel


class CompanyCreate(BaseModel):
    name: str
    slug: str
    search_terms: list[str]
    competitors: list[str] = []
    sources: dict = {}
    schedule: str = "0 */6 * * *"


class CompanyUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    search_terms: list[str] | None = None
    competitors: list[str] | None = None
    sources: dict | None = None
    schedule: str | None = None
    active: bool | None = None


class CompanyResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    search_terms: list
    competitors: list
    sources: dict
    schedule: str
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
