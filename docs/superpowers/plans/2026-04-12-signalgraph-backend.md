# SignalGraph Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the SignalGraph backend: a Python API that ingests mentions from public sources, analyzes sentiment/themes with Claude, detects bot activity, builds rolling memory, and generates daily intelligence briefs.

**Architecture:** FastAPI app with 5 pipeline layers (ingestion, normalization, analysis, legitimacy, memory+output). Each layer is a module with clean interfaces. PostgreSQL with pgvector for storage. APScheduler for per-company cron scheduling. Claude API (Sonnet for analysis, Opus for legitimacy).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 + asyncpg, Alembic, PostgreSQL + pgvector, APScheduler, Anthropic SDK, Pydantic v2, pytest + httpx, uv for package management.

---

## Scope

This plan covers PRD Phases 1-4 (backend). Dashboard (Phase 5) and polish (Phase 6) are separate plans.

- Phase 1: Skeleton (Tasks 1-6) -- FastAPI, DB, models, company CRUD, Reddit source
- Phase 2: Analysis (Tasks 7-9) -- Claude Sonnet integration, theme clustering, App Store source
- Phase 3: Memory + Legitimacy (Tasks 10-12) -- Embeddings, cross-run linking, legitimacy filter
- Phase 4: Scheduling + Output (Tasks 13-16) -- APScheduler, brief generation, webhooks, remaining sources

## File Structure

```
signalgraph/
├── pyproject.toml
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
├── src/
│   └── signalgraph/
│       ├── __init__.py
│       ├── main.py                    # FastAPI app factory
│       ├── config.py                  # Settings via pydantic-settings
│       ├── database.py                # SQLAlchemy engine + session
│       ├── models/
│       │   ├── __init__.py
│       │   ├── company.py             # Company ORM model
│       │   ├── mention.py             # RawMention ORM model
│       │   ├── analysis.py            # AnalysisResult + Theme ORM models
│       │   └── brief.py               # Brief ORM model
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── company.py             # Company Pydantic schemas
│       │   ├── mention.py             # Mention Pydantic schemas
│       │   ├── analysis.py            # Analysis + Theme Pydantic schemas
│       │   └── brief.py               # Brief Pydantic schemas
│       ├── api/
│       │   ├── __init__.py
│       │   ├── companies.py           # Company CRUD endpoints
│       │   ├── briefs.py              # Brief retrieval endpoints
│       │   ├── themes.py              # Theme listing endpoints
│       │   ├── mentions.py            # Mention listing endpoints
│       │   └── health.py              # Health check endpoint
│       ├── sources/
│       │   ├── __init__.py
│       │   ├── base.py                # Source protocol + RawMentionData
│       │   ├── reddit.py              # Reddit source adapter
│       │   ├── appstore.py            # App Store source adapter
│       │   ├── youtube.py             # YouTube source adapter
│       │   ├── playstore.py           # Google Play source adapter
│       │   ├── hackernews.py          # Hacker News source adapter
│       │   └── websearch.py           # Web search source adapter
│       ├── pipeline/
│       │   ├── __init__.py
│       │   ├── runner.py              # Orchestrates the full pipeline for a company
│       │   ├── normalizer.py          # Dedup + clean raw mentions
│       │   ├── analyzer.py            # Claude Sonnet: sentiment, topics, themes
│       │   ├── legitimacy.py          # Claude Opus: bot detection, corroboration
│       │   ├── memory.py              # Theme linking, trend detection
│       │   └── briefer.py             # Generate intelligence briefs
│       └── scheduler.py               # APScheduler setup, per-company scheduling
└── tests/
    ├── conftest.py                    # Fixtures: test DB, async client, factories
    ├── test_company_api.py
    ├── test_mention_api.py
    ├── test_source_reddit.py
    ├── test_source_appstore.py
    ├── test_normalizer.py
    ├── test_analyzer.py
    ├── test_legitimacy.py
    ├── test_memory.py
    ├── test_briefer.py
    ├── test_pipeline_runner.py
    ├── test_scheduler.py
    └── test_health.py
```

---

## Phase 1: Skeleton

### Task 1: Project Setup

**Files:**
- Create: `pyproject.toml`
- Create: `src/signalgraph/__init__.py`
- Create: `src/signalgraph/config.py`

- [ ] **Step 1: Initialize the project with uv**

```bash
cd /Users/ashtondaniel/conductor/workspaces/voice-of-customer-v2/nairobi
uv init --name signalgraph --python 3.12
```

- [ ] **Step 2: Replace pyproject.toml with full dependencies**

Replace the generated `pyproject.toml` with:

```toml
[project]
name = "signalgraph"
version = "0.1.0"
description = "Cross-platform sentiment intelligence system"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.7.0",
    "anthropic>=0.42.0",
    "httpx>=0.28.0",
    "apscheduler>=3.10.0",
    "pgvector>=0.3.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.28.0",
    "aiosqlite>=0.20.0",
    "ruff>=0.8.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
target-version = "py312"
line-length = 100
```

- [ ] **Step 3: Install dependencies**

```bash
uv sync --all-extras
```

- [ ] **Step 4: Create config module**

Create `src/signalgraph/__init__.py` (empty file).

Create `src/signalgraph/config.py`:

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://localhost:5432/signalgraph"
    test_database_url: str = "sqlite+aiosqlite:///test.db"

    anthropic_api_key: str = ""

    reddit_client_id: str = ""
    reddit_client_secret: str = ""

    default_schedule_hours: int = 6
    backfill_days: int = 7

    model_config = {"env_prefix": "SIGNALGRAPH_"}


settings = Settings()
```

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock src/ .python-version
git commit -m "feat: project setup with FastAPI, SQLAlchemy, Anthropic deps"
```

---

### Task 2: Database and ORM Models

**Files:**
- Create: `src/signalgraph/database.py`
- Create: `src/signalgraph/models/__init__.py`
- Create: `src/signalgraph/models/company.py`
- Create: `src/signalgraph/models/mention.py`
- Create: `src/signalgraph/models/analysis.py`
- Create: `src/signalgraph/models/brief.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write the test for database connectivity**

Create `tests/conftest.py`:

```python
import asyncio
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from signalgraph.database import Base, get_session
from signalgraph.main import create_app

TEST_DATABASE_URL = "sqlite+aiosqlite:///test.db"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
```

- [ ] **Step 2: Create database module**

Create `src/signalgraph/database.py`:

```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from signalgraph.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
```

- [ ] **Step 3: Create all ORM models**

Create `src/signalgraph/models/__init__.py`:

```python
from signalgraph.models.company import Company
from signalgraph.models.mention import RawMention
from signalgraph.models.analysis import AnalysisResult, Theme
from signalgraph.models.brief import Brief

__all__ = ["Company", "RawMention", "AnalysisResult", "Theme", "Brief"]
```

Create `src/signalgraph/models/company.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from signalgraph.database import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    search_terms: Mapped[list] = mapped_column(JSON, default=list)
    competitors: Mapped[list] = mapped_column(JSON, default=list)
    sources: Mapped[dict] = mapped_column(JSON, default=dict)
    schedule: Mapped[str] = mapped_column(String(50), default="0 */6 * * *")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

Create `src/signalgraph/models/mention.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from signalgraph.database import Base


class RawMention(Base):
    __tablename__ = "raw_mentions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    source: Mapped[str] = mapped_column(String(50))
    source_id: Mapped[str] = mapped_column(String(255))
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    author_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    language: Mapped[str] = mapped_column(String(10), default="en")
    raw_data: Mapped[dict] = mapped_column(JSON, default=dict)
```

Create `src/signalgraph/models/analysis.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from signalgraph.database import Base


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    mention_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_mentions.id")
    )
    sentiment: Mapped[float] = mapped_column(Float)
    sentiment_confidence: Mapped[float] = mapped_column(Float)
    topics: Mapped[list] = mapped_column(JSON, default=list)
    theme_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("themes.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Theme(Base):
    __tablename__ = "themes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    name: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text)
    first_seen: Mapped[datetime] = mapped_column(DateTime)
    last_seen: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), default="emerging")
    platforms: Mapped[list] = mapped_column(JSON, default=list)
    mention_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_sentiment: Mapped[float] = mapped_column(Float, default=0.0)
    legitimacy_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    legitimacy_class: Mapped[str | None] = mapped_column(String(50), nullable=True)
    legitimacy_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

Create `src/signalgraph/models/brief.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from signalgraph.database import Base


class Brief(Base):
    __tablename__ = "briefs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    content: Mapped[dict] = mapped_column(JSON)
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

- [ ] **Step 4: Write a test that verifies models can be created**

Create `tests/test_models.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from signalgraph.models import Company, RawMention


async def test_create_company(db_session):
    company = Company(
        name="Acme Corp",
        slug="acme-corp",
        search_terms=["Acme", "AcmePro"],
    )
    db_session.add(company)
    await db_session.commit()

    result = await db_session.execute(select(Company).where(Company.slug == "acme-corp"))
    saved = result.scalar_one()
    assert saved.name == "Acme Corp"
    assert saved.search_terms == ["Acme", "AcmePro"]
    assert saved.active is True


async def test_create_mention(db_session):
    company = Company(name="Test Co", slug="test-co", search_terms=["test"])
    db_session.add(company)
    await db_session.commit()

    mention = RawMention(
        company_id=company.id,
        source="reddit",
        source_id="abc123",
        text="This product is great",
        published_at=datetime.now(timezone.utc),
    )
    db_session.add(mention)
    await db_session.commit()

    result = await db_session.execute(
        select(RawMention).where(RawMention.company_id == company.id)
    )
    saved = result.scalar_one()
    assert saved.text == "This product is great"
    assert saved.source == "reddit"
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/ashtondaniel/conductor/workspaces/voice-of-customer-v2/nairobi
uv run pytest tests/test_models.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/signalgraph/ tests/
git commit -m "feat: database layer and ORM models for all core entities"
```

---

### Task 3: FastAPI App + Health Endpoint

**Files:**
- Create: `src/signalgraph/main.py`
- Create: `src/signalgraph/api/__init__.py`
- Create: `src/signalgraph/api/health.py`
- Create: `tests/test_health.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_health.py`:

```python
async def test_health_endpoint(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_health.py -v
```

Expected: FAIL (main module doesn't exist yet).

- [ ] **Step 3: Implement the app and health endpoint**

Create `src/signalgraph/api/__init__.py` (empty file).

Create `src/signalgraph/api/health.py`:

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
```

Create `src/signalgraph/main.py`:

```python
from fastapi import FastAPI

from signalgraph.api.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="SignalGraph", version="0.1.0")
    app.include_router(health_router)
    return app


app = create_app()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_health.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/signalgraph/main.py src/signalgraph/api/
git commit -m "feat: FastAPI app factory and health endpoint"
```

---

### Task 4: Company CRUD API

**Files:**
- Create: `src/signalgraph/schemas/__init__.py`
- Create: `src/signalgraph/schemas/company.py`
- Create: `src/signalgraph/api/companies.py`
- Modify: `src/signalgraph/main.py`
- Create: `tests/test_company_api.py`

- [ ] **Step 1: Write failing tests for company CRUD**

Create `tests/test_company_api.py`:

```python
async def test_create_company(client):
    response = await client.post(
        "/api/companies",
        json={
            "name": "Acme Corp",
            "slug": "acme-corp",
            "search_terms": ["Acme", "AcmePro"],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Acme Corp"
    assert data["slug"] == "acme-corp"
    assert data["active"] is True
    assert "id" in data


async def test_list_companies(client):
    await client.post(
        "/api/companies",
        json={"name": "Co A", "slug": "co-a", "search_terms": ["A"]},
    )
    await client.post(
        "/api/companies",
        json={"name": "Co B", "slug": "co-b", "search_terms": ["B"]},
    )

    response = await client.get("/api/companies")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


async def test_update_company(client):
    create = await client.post(
        "/api/companies",
        json={"name": "Old Name", "slug": "old-name", "search_terms": ["old"]},
    )
    company_id = create.json()["id"]

    response = await client.patch(
        f"/api/companies/{company_id}",
        json={"name": "New Name", "search_terms": ["new", "terms"]},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"
    assert response.json()["search_terms"] == ["new", "terms"]


async def test_delete_company(client):
    create = await client.post(
        "/api/companies",
        json={"name": "Doomed", "slug": "doomed", "search_terms": ["doom"]},
    )
    company_id = create.json()["id"]

    response = await client.delete(f"/api/companies/{company_id}")
    assert response.status_code == 200

    # Should still appear in list but be inactive (soft delete)
    get = await client.get("/api/companies")
    companies = get.json()
    doomed = [c for c in companies if c["id"] == company_id]
    assert len(doomed) == 1
    assert doomed[0]["active"] is False


async def test_create_duplicate_slug_fails(client):
    await client.post(
        "/api/companies",
        json={"name": "First", "slug": "same-slug", "search_terms": ["a"]},
    )
    response = await client.post(
        "/api/companies",
        json={"name": "Second", "slug": "same-slug", "search_terms": ["b"]},
    )
    assert response.status_code == 409
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_company_api.py -v
```

Expected: FAIL.

- [ ] **Step 3: Create Pydantic schemas**

Create `src/signalgraph/schemas/__init__.py` (empty file).

Create `src/signalgraph/schemas/company.py`:

```python
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
    search_terms: list[str]
    competitors: list[str]
    sources: dict
    schedule: str
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Implement company API endpoints**

Create `src/signalgraph/api/companies.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from signalgraph.database import get_session
from signalgraph.models.company import Company
from signalgraph.schemas.company import CompanyCreate, CompanyResponse, CompanyUpdate

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.post("", status_code=201, response_model=CompanyResponse)
async def create_company(body: CompanyCreate, session: AsyncSession = Depends(get_session)):
    company = Company(**body.model_dump())
    session.add(company)
    try:
        await session.commit()
        await session.refresh(company)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Company with this slug already exists")
    return company


@router.get("", response_model=list[CompanyResponse])
async def list_companies(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Company))
    return result.scalars().all()


@router.patch("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: uuid.UUID,
    body: CompanyUpdate,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(company, field, value)

    await session.commit()
    await session.refresh(company)
    return company


@router.delete("/{company_id}", response_model=CompanyResponse)
async def delete_company(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    company.active = False
    await session.commit()
    await session.refresh(company)
    return company
```

- [ ] **Step 5: Register the router in main.py**

Add to `src/signalgraph/main.py`:

```python
from fastapi import FastAPI

from signalgraph.api.companies import router as companies_router
from signalgraph.api.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="SignalGraph", version="0.1.0")
    app.include_router(health_router)
    app.include_router(companies_router)
    return app


app = create_app()
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_company_api.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/signalgraph/schemas/ src/signalgraph/api/companies.py src/signalgraph/main.py tests/test_company_api.py
git commit -m "feat: company CRUD API with create, list, update, soft-delete"
```

---

### Task 5: Source Protocol + Reddit Adapter

**Files:**
- Create: `src/signalgraph/sources/__init__.py`
- Create: `src/signalgraph/sources/base.py`
- Create: `src/signalgraph/sources/reddit.py`
- Create: `tests/test_source_reddit.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_source_reddit.py`:

```python
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from signalgraph.sources.reddit import RedditSource


@pytest.fixture
def reddit_source():
    return RedditSource(client_id="test_id", client_secret="test_secret")


MOCK_REDDIT_RESPONSE = {
    "data": {
        "children": [
            {
                "data": {
                    "id": "abc123",
                    "selftext": "This product has terrible battery life",
                    "title": "Battery issues with Acme",
                    "author": "testuser",
                    "subreddit": "technology",
                    "permalink": "/r/technology/comments/abc123",
                    "created_utc": 1712000000.0,
                    "score": 42,
                    "num_comments": 10,
                }
            },
            {
                "data": {
                    "id": "def456",
                    "selftext": "",
                    "title": "Acme just released a great update",
                    "author": "happyuser",
                    "subreddit": "gadgets",
                    "permalink": "/r/gadgets/comments/def456",
                    "created_utc": 1712100000.0,
                    "score": 15,
                    "num_comments": 3,
                }
            },
        ]
    }
}


async def test_reddit_fetch_returns_mentions(reddit_source):
    mock_response = AsyncMock()
    mock_response.json.return_value = MOCK_REDDIT_RESPONSE
    mock_response.raise_for_status = lambda: None

    mock_token_response = AsyncMock()
    mock_token_response.json.return_value = {"access_token": "fake_token"}
    mock_token_response.raise_for_status = lambda: None

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post.return_value = mock_token_response
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        mentions = await reddit_source.fetch(
            search_terms=["Acme"],
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )

    assert len(mentions) == 2
    assert mentions[0].source == "reddit"
    assert mentions[0].source_id == "abc123"
    assert "battery" in mentions[0].text.lower()
    assert mentions[0].author == "testuser"


async def test_reddit_source_has_correct_name(reddit_source):
    assert reddit_source.name == "reddit"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_source_reddit.py -v
```

Expected: FAIL (module not found).

- [ ] **Step 3: Create the source protocol and Reddit adapter**

Create `src/signalgraph/sources/__init__.py` (empty file).

Create `src/signalgraph/sources/base.py`:

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass
class RawMentionData:
    source: str
    source_id: str
    text: str
    published_at: datetime
    author: str | None = None
    author_metadata: dict | None = None
    url: str | None = None
    language: str = "en"
    raw_data: dict = field(default_factory=dict)


class Source(Protocol):
    name: str

    async def fetch(
        self, search_terms: list[str], since: datetime
    ) -> list[RawMentionData]: ...
```

Create `src/signalgraph/sources/reddit.py`:

```python
from datetime import datetime, timezone

import httpx

from signalgraph.sources.base import RawMentionData


class RedditSource:
    name = "reddit"

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret

    async def _get_token(self, client: httpx.AsyncClient) -> str:
        response = await client.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=(self.client_id, self.client_secret),
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": "SignalGraph/0.1"},
        )
        response.raise_for_status()
        return response.json()["access_token"]

    async def fetch(
        self, search_terms: list[str], since: datetime
    ) -> list[RawMentionData]:
        mentions: list[RawMentionData] = []

        async with httpx.AsyncClient() as client:
            token = await self._get_token(client)
            headers = {
                "Authorization": f"Bearer {token}",
                "User-Agent": "SignalGraph/0.1",
            }

            for term in search_terms:
                response = await client.get(
                    "https://oauth.reddit.com/search",
                    params={
                        "q": term,
                        "sort": "new",
                        "limit": 100,
                        "t": "week",
                    },
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()

                for post in data["data"]["children"]:
                    post_data = post["data"]
                    created = datetime.fromtimestamp(
                        post_data["created_utc"], tz=timezone.utc
                    )

                    if created < since:
                        continue

                    text = post_data.get("selftext", "") or post_data.get("title", "")
                    if post_data.get("selftext"):
                        text = f"{post_data['title']}\n\n{post_data['selftext']}"

                    mentions.append(
                        RawMentionData(
                            source="reddit",
                            source_id=post_data["id"],
                            text=text,
                            published_at=created,
                            author=post_data.get("author"),
                            author_metadata={
                                "subreddit": post_data.get("subreddit"),
                                "score": post_data.get("score"),
                                "num_comments": post_data.get("num_comments"),
                            },
                            url=f"https://reddit.com{post_data.get('permalink', '')}",
                            raw_data=post_data,
                        )
                    )

        return mentions
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_source_reddit.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/signalgraph/sources/ tests/test_source_reddit.py
git commit -m "feat: source protocol and Reddit adapter with OAuth"
```

---

### Task 6: Normalizer + Pipeline Runner Skeleton

**Files:**
- Create: `src/signalgraph/pipeline/__init__.py`
- Create: `src/signalgraph/pipeline/normalizer.py`
- Create: `src/signalgraph/pipeline/runner.py`
- Create: `tests/test_normalizer.py`

- [ ] **Step 1: Write the failing test for normalizer**

Create `tests/test_normalizer.py`:

```python
from datetime import datetime, timezone

from signalgraph.sources.base import RawMentionData
from signalgraph.pipeline.normalizer import deduplicate, normalize_text


def test_deduplicate_removes_same_source_id():
    mentions = [
        RawMentionData(
            source="reddit", source_id="abc", text="hello",
            published_at=datetime.now(timezone.utc),
        ),
        RawMentionData(
            source="reddit", source_id="abc", text="hello duplicate",
            published_at=datetime.now(timezone.utc),
        ),
        RawMentionData(
            source="reddit", source_id="def", text="different",
            published_at=datetime.now(timezone.utc),
        ),
    ]
    result = deduplicate(mentions)
    assert len(result) == 2
    source_ids = {m.source_id for m in result}
    assert source_ids == {"abc", "def"}


def test_normalize_text_cleans_whitespace():
    assert normalize_text("  hello   world  \n\n  ") == "hello world"


def test_normalize_text_strips_urls():
    text = "Check this out https://example.com/foo?bar=baz and this"
    result = normalize_text(text)
    assert "https://example.com" not in result
    assert "Check this out" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_normalizer.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement normalizer**

Create `src/signalgraph/pipeline/__init__.py` (empty file).

Create `src/signalgraph/pipeline/normalizer.py`:

```python
import re

from signalgraph.sources.base import RawMentionData

URL_PATTERN = re.compile(r"https?://\S+")
WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    text = URL_PATTERN.sub("", text)
    text = WHITESPACE_PATTERN.sub(" ", text)
    return text.strip()


def deduplicate(mentions: list[RawMentionData]) -> list[RawMentionData]:
    seen: set[str] = set()
    unique: list[RawMentionData] = []

    for mention in mentions:
        key = f"{mention.source}:{mention.source_id}"
        if key not in seen:
            seen.add(key)
            unique.append(mention)

    return unique
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_normalizer.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Create pipeline runner skeleton**

Create `src/signalgraph/pipeline/runner.py`:

```python
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from signalgraph.models.company import Company
from signalgraph.models.mention import RawMention
from signalgraph.pipeline.normalizer import deduplicate, normalize_text
from signalgraph.sources.base import RawMentionData, Source


async def run_ingestion(
    company: Company,
    sources: list[Source],
    since: datetime | None,
    session: AsyncSession,
) -> list[RawMention]:
    if since is None:
        since = datetime.now(timezone.utc) - timedelta(days=7)

    all_mentions: list[RawMentionData] = []
    for source in sources:
        fetched = await source.fetch(
            search_terms=company.search_terms, since=since
        )
        all_mentions.extend(fetched)

    unique = deduplicate(all_mentions)

    saved: list[RawMention] = []
    for mention_data in unique:
        mention = RawMention(
            company_id=company.id,
            source=mention_data.source,
            source_id=mention_data.source_id,
            author=mention_data.author,
            author_metadata=mention_data.author_metadata,
            text=normalize_text(mention_data.text),
            url=mention_data.url,
            published_at=mention_data.published_at,
            language=mention_data.language,
            raw_data=mention_data.raw_data,
        )
        session.add(mention)
        saved.append(mention)

    await session.commit()
    return saved


async def run_pipeline(
    company: Company,
    sources: list[Source],
    session: AsyncSession,
    since: datetime | None = None,
) -> uuid.UUID:
    run_id = uuid.uuid4()

    mentions = await run_ingestion(company, sources, since, session)

    # Analysis, legitimacy, and brief generation are added in later tasks.

    return run_id
```

- [ ] **Step 6: Commit**

```bash
git add src/signalgraph/pipeline/ tests/test_normalizer.py
git commit -m "feat: normalizer with dedup + text cleaning, pipeline runner skeleton"
```

---

## Phase 2: Analysis

### Task 7: Claude Sonnet Analyzer

**Files:**
- Create: `src/signalgraph/pipeline/analyzer.py`
- Create: `tests/test_analyzer.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_analyzer.py`:

```python
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from signalgraph.models.mention import RawMention
from signalgraph.pipeline.analyzer import analyze_mentions


def _make_mention(text: str, source: str = "reddit") -> RawMention:
    return RawMention(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        source=source,
        source_id=f"test-{uuid.uuid4().hex[:8]}",
        text=text,
        published_at=datetime.now(timezone.utc),
        raw_data={},
    )


MOCK_ANALYSIS_RESPONSE = {
    "mentions": [
        {
            "mention_id": "PLACEHOLDER",
            "sentiment": -0.7,
            "sentiment_confidence": 0.9,
            "topics": ["battery drain", "hardware"],
        }
    ],
    "themes": [
        {
            "name": "Battery drain after update",
            "summary": "Users report battery issues after the latest update",
            "mention_ids": ["PLACEHOLDER"],
            "platforms": ["reddit"],
            "avg_sentiment": -0.7,
        }
    ],
}


async def test_analyze_mentions_returns_results():
    mentions = [_make_mention("The battery drains so fast after the update")]
    MOCK_ANALYSIS_RESPONSE["mentions"][0]["mention_id"] = str(mentions[0].id)
    MOCK_ANALYSIS_RESPONSE["themes"][0]["mention_ids"] = [str(mentions[0].id)]

    mock_message = AsyncMock()
    mock_message.content = [
        AsyncMock(text='```json\n' + __import__("json").dumps(MOCK_ANALYSIS_RESPONSE) + '\n```')
    ]

    with patch("signalgraph.pipeline.analyzer.anthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_client.messages.create.return_value = mock_message
        mock_anthropic.AsyncAnthropic.return_value = mock_client

        results = await analyze_mentions(
            mentions=mentions,
            company_name="Acme Corp",
            run_id=uuid.uuid4(),
            history_summary="No prior themes.",
        )

    assert len(results["analysis_results"]) == 1
    assert results["analysis_results"][0]["sentiment"] == -0.7
    assert len(results["themes"]) == 1
    assert results["themes"][0]["name"] == "Battery drain after update"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_analyzer.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement the analyzer**

Create `src/signalgraph/pipeline/analyzer.py`:

```python
import json
import re
import uuid

import anthropic

from signalgraph.models.mention import RawMention

ANALYSIS_PROMPT = """You are a sentiment intelligence analyst. Analyze these mentions about "{company_name}".

## Context from previous runs
{history_summary}

## Mentions to analyze
{mentions_json}

## Tasks
1. **Sentiment tagging**: For each mention, assign a sentiment score (-1.0 to +1.0) and confidence (0-1).
2. **Topic extraction**: For each mention, extract topic labels (e.g., "battery drain", "pricing").
3. **Theme clustering**: Group mentions into themes. For each theme provide: name, summary, mention_ids, platforms list, avg_sentiment.

## Output format
Return valid JSON (no extra text) with this structure:
```json
{{
  "mentions": [
    {{
      "mention_id": "uuid",
      "sentiment": -0.5,
      "sentiment_confidence": 0.9,
      "topics": ["topic1", "topic2"]
    }}
  ],
  "themes": [
    {{
      "name": "Theme name",
      "summary": "One sentence summary",
      "mention_ids": ["uuid1", "uuid2"],
      "platforms": ["reddit", "appstore"],
      "avg_sentiment": -0.3
    }}
  ]
}}
```"""


def _extract_json(text: str) -> dict:
    json_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group(1))
    return json.loads(text)


async def analyze_mentions(
    mentions: list[RawMention],
    company_name: str,
    run_id: uuid.UUID,
    history_summary: str = "No prior analysis available.",
) -> dict:
    mentions_data = [
        {
            "id": str(m.id),
            "text": m.text,
            "source": m.source,
            "published_at": m.published_at.isoformat() if m.published_at else None,
            "author": m.author,
        }
        for m in mentions
    ]

    prompt = ANALYSIS_PROMPT.format(
        company_name=company_name,
        history_summary=history_summary,
        mentions_json=json.dumps(mentions_data, indent=2),
    )

    client = anthropic.AsyncAnthropic()
    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text
    parsed = _extract_json(response_text)

    return {
        "analysis_results": [
            {
                "mention_id": m["mention_id"],
                "sentiment": m["sentiment"],
                "sentiment_confidence": m["sentiment_confidence"],
                "topics": m["topics"],
                "run_id": str(run_id),
            }
            for m in parsed["mentions"]
        ],
        "themes": [
            {
                "name": t["name"],
                "summary": t["summary"],
                "mention_ids": t["mention_ids"],
                "platforms": t["platforms"],
                "avg_sentiment": t["avg_sentiment"],
                "run_id": str(run_id),
            }
            for t in parsed["themes"]
        ],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_analyzer.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/signalgraph/pipeline/analyzer.py tests/test_analyzer.py
git commit -m "feat: Claude Sonnet analyzer for sentiment, topics, theme clustering"
```

---

### Task 8: Wire Analysis into Pipeline Runner + Save Results to DB

**Files:**
- Modify: `src/signalgraph/pipeline/runner.py`
- Create: `tests/test_pipeline_runner.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_pipeline_runner.py`:

```python
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from signalgraph.models.company import Company
from signalgraph.models.analysis import AnalysisResult, Theme
from signalgraph.models.mention import RawMention
from signalgraph.pipeline.runner import run_pipeline
from signalgraph.sources.base import RawMentionData


class FakeSource:
    name = "fake"

    async def fetch(self, search_terms, since):
        return [
            RawMentionData(
                source="fake",
                source_id="fake-1",
                text="Great product, love the battery life",
                published_at=datetime.now(timezone.utc),
                author="user1",
            ),
            RawMentionData(
                source="fake",
                source_id="fake-2",
                text="Terrible customer support experience",
                published_at=datetime.now(timezone.utc),
                author="user2",
            ),
        ]


MOCK_ANALYSIS = {
    "analysis_results": [
        {
            "mention_id": "PLACEHOLDER",
            "sentiment": 0.8,
            "sentiment_confidence": 0.9,
            "topics": ["battery"],
            "run_id": "PLACEHOLDER",
        },
        {
            "mention_id": "PLACEHOLDER",
            "sentiment": -0.6,
            "sentiment_confidence": 0.85,
            "topics": ["support"],
            "run_id": "PLACEHOLDER",
        },
    ],
    "themes": [
        {
            "name": "Battery praise",
            "summary": "Users love the battery",
            "mention_ids": [],
            "platforms": ["fake"],
            "avg_sentiment": 0.8,
            "run_id": "PLACEHOLDER",
        },
    ],
}


async def test_run_pipeline_saves_mentions_and_analysis(db_session):
    company = Company(
        name="Test Co", slug="test-co", search_terms=["test"]
    )
    db_session.add(company)
    await db_session.commit()

    with patch("signalgraph.pipeline.runner.analyze_mentions") as mock_analyze:
        async def fake_analyze(mentions, company_name, run_id, history_summary=""):
            result = MOCK_ANALYSIS.copy()
            for i, m in enumerate(mentions):
                if i < len(result["analysis_results"]):
                    result["analysis_results"][i]["mention_id"] = str(m.id)
                    result["analysis_results"][i]["run_id"] = str(run_id)
            result["themes"][0]["run_id"] = str(run_id)
            result["themes"][0]["mention_ids"] = [str(mentions[0].id)]
            return result

        mock_analyze.side_effect = fake_analyze

        run_id = await run_pipeline(
            company=company,
            sources=[FakeSource()],
            session=db_session,
        )

    # Check mentions were saved
    mentions_result = await db_session.execute(
        select(RawMention).where(RawMention.company_id == company.id)
    )
    mentions = mentions_result.scalars().all()
    assert len(mentions) == 2

    # Check analysis results were saved
    analysis_result = await db_session.execute(
        select(AnalysisResult).where(AnalysisResult.run_id == run_id)
    )
    results = analysis_result.scalars().all()
    assert len(results) == 2

    # Check themes were saved
    themes_result = await db_session.execute(
        select(Theme).where(Theme.run_id == run_id)
    )
    themes = themes_result.scalars().all()
    assert len(themes) == 1
    assert themes[0].name == "Battery praise"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_pipeline_runner.py -v
```

Expected: FAIL.

- [ ] **Step 3: Update pipeline runner to run analysis and save results**

Replace `src/signalgraph/pipeline/runner.py`:

```python
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from signalgraph.models.analysis import AnalysisResult, Theme
from signalgraph.models.company import Company
from signalgraph.models.mention import RawMention
from signalgraph.pipeline.analyzer import analyze_mentions
from signalgraph.pipeline.normalizer import deduplicate, normalize_text
from signalgraph.sources.base import RawMentionData, Source


async def run_ingestion(
    company: Company,
    sources: list[Source],
    since: datetime | None,
    session: AsyncSession,
) -> list[RawMention]:
    if since is None:
        since = datetime.now(timezone.utc) - timedelta(days=7)

    all_mentions: list[RawMentionData] = []
    for source in sources:
        fetched = await source.fetch(
            search_terms=company.search_terms, since=since
        )
        all_mentions.extend(fetched)

    unique = deduplicate(all_mentions)

    saved: list[RawMention] = []
    for mention_data in unique:
        mention = RawMention(
            company_id=company.id,
            source=mention_data.source,
            source_id=mention_data.source_id,
            author=mention_data.author,
            author_metadata=mention_data.author_metadata,
            text=normalize_text(mention_data.text),
            url=mention_data.url,
            published_at=mention_data.published_at,
            language=mention_data.language,
            raw_data=mention_data.raw_data,
        )
        session.add(mention)
        saved.append(mention)

    await session.commit()
    # Refresh all to get IDs assigned by DB
    for mention in saved:
        await session.refresh(mention)
    return saved


async def save_analysis(
    analysis: dict,
    company_id: uuid.UUID,
    run_id: uuid.UUID,
    session: AsyncSession,
) -> list[Theme]:
    # Save themes first so we can reference their IDs
    theme_map: dict[str, Theme] = {}
    for theme_data in analysis["themes"]:
        theme = Theme(
            company_id=company_id,
            run_id=run_id,
            name=theme_data["name"],
            summary=theme_data["summary"],
            first_seen=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc),
            platforms=theme_data["platforms"],
            mention_count=len(theme_data.get("mention_ids", [])),
            avg_sentiment=theme_data["avg_sentiment"],
        )
        session.add(theme)
        await session.flush()
        for mid in theme_data.get("mention_ids", []):
            theme_map[mid] = theme

    # Save analysis results
    for result_data in analysis["analysis_results"]:
        mention_id = result_data["mention_id"]
        theme = theme_map.get(mention_id)
        result = AnalysisResult(
            company_id=company_id,
            run_id=run_id,
            mention_id=uuid.UUID(mention_id),
            sentiment=result_data["sentiment"],
            sentiment_confidence=result_data["sentiment_confidence"],
            topics=result_data["topics"],
            theme_id=theme.id if theme else None,
        )
        session.add(result)

    await session.commit()
    return list({t.id: t for t in theme_map.values()}.values())


async def run_pipeline(
    company: Company,
    sources: list[Source],
    session: AsyncSession,
    since: datetime | None = None,
) -> uuid.UUID:
    run_id = uuid.uuid4()

    mentions = await run_ingestion(company, sources, since, session)

    if not mentions:
        return run_id

    analysis = await analyze_mentions(
        mentions=mentions,
        company_name=company.name,
        run_id=run_id,
    )

    await save_analysis(analysis, company.id, run_id, session)

    return run_id
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_pipeline_runner.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/signalgraph/pipeline/runner.py tests/test_pipeline_runner.py
git commit -m "feat: pipeline runner saves analysis results and themes to DB"
```

---

### Task 9: App Store Source Adapter

**Files:**
- Create: `src/signalgraph/sources/appstore.py`
- Create: `tests/test_source_appstore.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_source_appstore.py`:

```python
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from signalgraph.sources.appstore import AppStoreSource


MOCK_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:im="http://itunes.apple.com/rss">
  <entry>
    <id>12345</id>
    <title>Terrible battery</title>
    <content type="text">Battery drains so fast after update. Very disappointed.</content>
    <author><name>AngryUser</name></author>
    <im:rating>1</im:rating>
    <im:version>4.2.0</im:version>
    <updated>2024-04-01T10:00:00Z</updated>
  </entry>
  <entry>
    <id>67890</id>
    <title>Love this app</title>
    <content type="text">Works great, no complaints!</content>
    <author><name>HappyUser</name></author>
    <im:rating>5</im:rating>
    <im:version>4.2.0</im:version>
    <updated>2024-04-02T12:00:00Z</updated>
  </entry>
</feed>"""


async def test_appstore_fetch_parses_rss():
    source = AppStoreSource(app_id="123456789", country="us")

    mock_response = AsyncMock()
    mock_response.text = MOCK_RSS_XML
    mock_response.raise_for_status = lambda: None

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        mentions = await source.fetch(
            search_terms=["Acme"],
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )

    assert len(mentions) == 2
    assert mentions[0].source == "appstore"
    assert mentions[0].source_id == "12345"
    assert "battery" in mentions[0].text.lower()
    assert mentions[0].author == "AngryUser"
    assert mentions[0].author_metadata["rating"] == "1"


async def test_appstore_source_name():
    source = AppStoreSource(app_id="123", country="us")
    assert source.name == "appstore"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_source_appstore.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement App Store source**

Create `src/signalgraph/sources/appstore.py`:

```python
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx

from signalgraph.sources.base import RawMentionData

ATOM_NS = "http://www.w3.org/2005/Atom"
IM_NS = "http://itunes.apple.com/rss"


class AppStoreSource:
    name = "appstore"

    def __init__(self, app_id: str, country: str = "us"):
        self.app_id = app_id
        self.country = country

    async def fetch(
        self, search_terms: list[str], since: datetime
    ) -> list[RawMentionData]:
        url = (
            f"https://itunes.apple.com/{self.country}/rss/customerreviews"
            f"/id={self.app_id}/sortBy=mostRecent/xml"
        )

        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()

        root = ET.fromstring(response.text)
        mentions: list[RawMentionData] = []

        for entry in root.findall(f"{{{ATOM_NS}}}entry"):
            entry_id = entry.findtext(f"{{{ATOM_NS}}}id", "")
            title = entry.findtext(f"{{{ATOM_NS}}}title", "")
            content = entry.findtext(f"{{{ATOM_NS}}}content", "")
            author_el = entry.find(f"{{{ATOM_NS}}}author")
            author = (
                author_el.findtext(f"{{{ATOM_NS}}}name", "") if author_el else None
            )
            rating = entry.findtext(f"{{{IM_NS}}}rating", "")
            version = entry.findtext(f"{{{IM_NS}}}version", "")
            updated = entry.findtext(f"{{{ATOM_NS}}}updated", "")

            try:
                published_at = datetime.fromisoformat(
                    updated.replace("Z", "+00:00")
                )
            except ValueError:
                published_at = datetime.now(timezone.utc)

            if published_at < since:
                continue

            text = f"{title}\n\n{content}" if title and content else (title or content)

            mentions.append(
                RawMentionData(
                    source="appstore",
                    source_id=entry_id,
                    text=text,
                    published_at=published_at,
                    author=author,
                    author_metadata={"rating": rating, "version": version},
                    url=f"https://apps.apple.com/{self.country}/app/id{self.app_id}",
                    raw_data={"title": title, "content": content, "rating": rating},
                )
            )

        return mentions
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_source_appstore.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/signalgraph/sources/appstore.py tests/test_source_appstore.py
git commit -m "feat: App Store source adapter via RSS feed parsing"
```

---

## Phase 3: Memory + Legitimacy

### Task 10: Theme Memory and Cross-Run Linking

**Files:**
- Create: `src/signalgraph/pipeline/memory.py`
- Create: `tests/test_memory.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_memory.py`:

```python
import uuid
from datetime import datetime, timedelta, timezone

from signalgraph.models.analysis import Theme
from signalgraph.models.company import Company
from signalgraph.pipeline.memory import link_themes, build_history_summary


async def test_link_themes_matches_similar_names(db_session):
    company = Company(name="Test Co", slug="test-link", search_terms=["test"])
    db_session.add(company)
    await db_session.commit()

    # Old theme from a previous run
    old_theme = Theme(
        company_id=company.id,
        run_id=uuid.uuid4(),
        name="Battery drain issues",
        summary="Users report battery problems",
        first_seen=datetime.now(timezone.utc) - timedelta(days=7),
        last_seen=datetime.now(timezone.utc) - timedelta(days=1),
        status="active",
        platforms=["reddit"],
        mention_count=15,
        avg_sentiment=-0.6,
    )
    db_session.add(old_theme)
    await db_session.commit()

    # New theme from current run
    new_theme = Theme(
        company_id=company.id,
        run_id=uuid.uuid4(),
        name="Battery drain after v4.2",
        summary="Battery drains fast after recent update",
        first_seen=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
        status="emerging",
        platforms=["reddit", "appstore"],
        mention_count=8,
        avg_sentiment=-0.7,
    )
    db_session.add(new_theme)
    await db_session.commit()

    linked = await link_themes([new_theme], company.id, db_session)

    # Should update old theme rather than keeping both
    assert len(linked) == 1
    assert linked[0].id == old_theme.id
    assert "appstore" in linked[0].platforms
    assert linked[0].mention_count == 23  # 15 + 8
    assert linked[0].status == "active"


async def test_build_history_summary(db_session):
    company = Company(name="Test Co", slug="test-hist", search_terms=["test"])
    db_session.add(company)
    await db_session.commit()

    for i in range(3):
        theme = Theme(
            company_id=company.id,
            run_id=uuid.uuid4(),
            name=f"Theme {i}",
            summary=f"Summary for theme {i}",
            first_seen=datetime.now(timezone.utc) - timedelta(days=i),
            last_seen=datetime.now(timezone.utc),
            status="active",
            platforms=["reddit"],
            mention_count=10 + i,
            avg_sentiment=-0.3 - (i * 0.1),
        )
        db_session.add(theme)

    await db_session.commit()

    summary = await build_history_summary(company.id, db_session)
    assert "Theme 0" in summary
    assert "Theme 1" in summary
    assert "Theme 2" in summary
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_memory.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement memory module**

Create `src/signalgraph/pipeline/memory.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from signalgraph.models.analysis import Theme


def _name_similarity(a: str, b: str) -> float:
    """Simple word-overlap similarity between two theme names."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


async def link_themes(
    new_themes: list[Theme],
    company_id: uuid.UUID,
    session: AsyncSession,
    similarity_threshold: float = 0.3,
) -> list[Theme]:
    result = await session.execute(
        select(Theme)
        .where(Theme.company_id == company_id)
        .where(Theme.status.in_(["emerging", "active"]))
        .order_by(Theme.last_seen.desc())
    )
    existing_themes = list(result.scalars().all())

    linked: list[Theme] = []

    for new_theme in new_themes:
        best_match: Theme | None = None
        best_score = 0.0

        for existing in existing_themes:
            if existing.id == new_theme.id:
                continue
            score = _name_similarity(existing.name, new_theme.name)
            if score > best_score and score >= similarity_threshold:
                best_score = score
                best_match = existing

        if best_match:
            # Merge into existing theme
            best_match.last_seen = datetime.now(timezone.utc)
            best_match.mention_count += new_theme.mention_count
            best_match.avg_sentiment = (
                best_match.avg_sentiment + new_theme.avg_sentiment
            ) / 2

            # Merge platforms
            all_platforms = set(best_match.platforms or []) | set(
                new_theme.platforms or []
            )
            best_match.platforms = sorted(all_platforms)

            # Escalate status if spreading
            if len(all_platforms) > len(set(best_match.platforms or [])):
                best_match.status = "active"

            # Remove the duplicate new theme
            await session.delete(new_theme)
            linked.append(best_match)
        else:
            linked.append(new_theme)

    await session.commit()
    for theme in linked:
        await session.refresh(theme)
    return linked


async def build_history_summary(
    company_id: uuid.UUID,
    session: AsyncSession,
    limit: int = 20,
) -> str:
    result = await session.execute(
        select(Theme)
        .where(Theme.company_id == company_id)
        .where(Theme.status.in_(["emerging", "active", "declining"]))
        .order_by(Theme.last_seen.desc())
        .limit(limit)
    )
    themes = result.scalars().all()

    if not themes:
        return "No prior themes detected."

    lines = ["Recent themes for this company:"]
    for theme in themes:
        lines.append(
            f"- {theme.name} (status: {theme.status}, "
            f"mentions: {theme.mention_count}, "
            f"sentiment: {theme.avg_sentiment:.2f}, "
            f"platforms: {', '.join(theme.platforms or [])})"
        )

    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_memory.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/signalgraph/pipeline/memory.py tests/test_memory.py
git commit -m "feat: theme memory with cross-run linking and history summaries"
```

---

### Task 11: Legitimacy Filter (Claude Opus)

**Files:**
- Create: `src/signalgraph/pipeline/legitimacy.py`
- Create: `tests/test_legitimacy.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_legitimacy.py`:

```python
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from signalgraph.models.analysis import Theme
from signalgraph.pipeline.legitimacy import evaluate_legitimacy


def _make_theme(name: str, platforms: list[str], mention_count: int) -> Theme:
    return Theme(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        name=name,
        summary=f"Summary of {name}",
        first_seen=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
        status="active",
        platforms=platforms,
        mention_count=mention_count,
        avg_sentiment=-0.5,
    )


MOCK_LEGITIMACY_RESPONSE = [
    {
        "theme_id": "PLACEHOLDER",
        "legitimacy_score": 0.85,
        "legitimacy_class": "organic",
        "reasoning": "Theme appears across 3 platforms independently with gradual growth.",
    }
]


async def test_evaluate_legitimacy_returns_scores():
    theme = _make_theme("Battery issues", ["reddit", "appstore", "youtube"], 45)
    MOCK_LEGITIMACY_RESPONSE[0]["theme_id"] = str(theme.id)

    mock_message = AsyncMock()
    mock_message.content = [
        AsyncMock(text=json.dumps(MOCK_LEGITIMACY_RESPONSE))
    ]

    with patch("signalgraph.pipeline.legitimacy.anthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_client.messages.create.return_value = mock_message
        mock_anthropic.AsyncAnthropic.return_value = mock_client

        results = await evaluate_legitimacy([theme])

    assert len(results) == 1
    assert results[0]["legitimacy_score"] == 0.85
    assert results[0]["legitimacy_class"] == "organic"
    assert "3 platforms" in results[0]["reasoning"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_legitimacy.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement legitimacy filter**

Create `src/signalgraph/pipeline/legitimacy.py`:

```python
import json
import re

import anthropic

from signalgraph.models.analysis import Theme

LEGITIMACY_PROMPT = """You are a sentiment authenticity analyst. Evaluate these themes for legitimacy.

For each theme, assess:
1. **Cross-platform corroboration**: Does this theme appear independently on multiple platforms? More platforms = higher legitimacy.
2. **Temporal pattern**: Organic complaints build gradually. Coordinated campaigns spike sharply.
3. **Account-level signals**: Consider author diversity and metadata if available.

## Themes to evaluate
{themes_json}

## Output format
Return a JSON array (no extra text):
```json
[
  {{
    "theme_id": "uuid",
    "legitimacy_score": 0.85,
    "legitimacy_class": "organic|suspected_coordinated|bot_amplified|ambiguous",
    "reasoning": "One sentence explanation"
  }}
]
```

Classification guide:
- **organic** (score > 0.7): Real user sentiment across multiple platforms
- **suspected_coordinated** (score 0.3-0.7): Suspicious spike patterns or single-platform concentration
- **bot_amplified** (score < 0.3): Signs of automated or fake accounts
- **ambiguous**: Not enough data to classify confidently"""


def _extract_json(text: str) -> list:
    json_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group(1))
    return json.loads(text)


async def evaluate_legitimacy(themes: list[Theme]) -> list[dict]:
    if not themes:
        return []

    themes_data = [
        {
            "id": str(t.id),
            "name": t.name,
            "summary": t.summary,
            "platforms": t.platforms,
            "mention_count": t.mention_count,
            "avg_sentiment": t.avg_sentiment,
            "status": t.status,
        }
        for t in themes
    ]

    prompt = LEGITIMACY_PROMPT.format(
        themes_json=json.dumps(themes_data, indent=2)
    )

    client = anthropic.AsyncAnthropic()
    message = await client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text
    return _extract_json(response_text)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_legitimacy.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/signalgraph/pipeline/legitimacy.py tests/test_legitimacy.py
git commit -m "feat: legitimacy filter using Claude Opus for bot/coordination detection"
```

---

### Task 12: Wire Memory + Legitimacy into Pipeline

**Files:**
- Modify: `src/signalgraph/pipeline/runner.py`
- Modify: `tests/test_pipeline_runner.py`

- [ ] **Step 1: Write the test for the full pipeline**

Add to `tests/test_pipeline_runner.py`:

```python
async def test_full_pipeline_with_memory_and_legitimacy(db_session):
    company = Company(name="Full Co", slug="full-co", search_terms=["full"])
    db_session.add(company)
    await db_session.commit()

    mock_legitimacy = [
        {
            "theme_id": "PLACEHOLDER",
            "legitimacy_score": 0.9,
            "legitimacy_class": "organic",
            "reasoning": "Genuine cross-platform signal",
        }
    ]

    with (
        patch("signalgraph.pipeline.runner.analyze_mentions") as mock_analyze,
        patch("signalgraph.pipeline.runner.evaluate_legitimacy") as mock_legit,
        patch("signalgraph.pipeline.runner.link_themes") as mock_link,
        patch("signalgraph.pipeline.runner.build_history_summary") as mock_history,
    ):
        async def fake_analyze(mentions, company_name, run_id, history_summary=""):
            result = MOCK_ANALYSIS.copy()
            for i, m in enumerate(mentions):
                if i < len(result["analysis_results"]):
                    result["analysis_results"][i]["mention_id"] = str(m.id)
                    result["analysis_results"][i]["run_id"] = str(run_id)
            result["themes"][0]["run_id"] = str(run_id)
            result["themes"][0]["mention_ids"] = [str(mentions[0].id)]
            return result

        mock_analyze.side_effect = fake_analyze
        mock_history.return_value = "No prior themes."

        async def fake_link(themes, company_id, session):
            return themes

        mock_link.side_effect = fake_link

        async def fake_legit(themes):
            return [
                {
                    "theme_id": str(themes[0].id),
                    "legitimacy_score": 0.9,
                    "legitimacy_class": "organic",
                    "reasoning": "Genuine signal",
                }
            ]

        mock_legit.side_effect = fake_legit

        run_id = await run_pipeline(
            company=company,
            sources=[FakeSource()],
            session=db_session,
        )

    # Verify legitimacy was evaluated
    mock_legit.assert_called_once()

    # Verify memory linking was run
    mock_link.assert_called_once()

    # Check theme has legitimacy data
    themes_result = await db_session.execute(
        select(Theme).where(Theme.run_id == run_id)
    )
    themes = themes_result.scalars().all()
    assert len(themes) == 1
    assert themes[0].legitimacy_score == 0.9
    assert themes[0].legitimacy_class == "organic"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_pipeline_runner.py::test_full_pipeline_with_memory_and_legitimacy -v
```

Expected: FAIL.

- [ ] **Step 3: Update pipeline runner with memory + legitimacy**

Update `src/signalgraph/pipeline/runner.py` to add imports and update `run_pipeline`:

Add these imports at the top:

```python
from signalgraph.pipeline.legitimacy import evaluate_legitimacy
from signalgraph.pipeline.memory import build_history_summary, link_themes
```

Replace the `run_pipeline` function:

```python
async def run_pipeline(
    company: Company,
    sources: list[Source],
    session: AsyncSession,
    since: datetime | None = None,
) -> uuid.UUID:
    run_id = uuid.uuid4()

    mentions = await run_ingestion(company, sources, since, session)

    if not mentions:
        return run_id

    # Build context from prior runs
    history = await build_history_summary(company.id, session)

    # Run LLM analysis
    analysis = await analyze_mentions(
        mentions=mentions,
        company_name=company.name,
        run_id=run_id,
        history_summary=history,
    )

    themes = await save_analysis(analysis, company.id, run_id, session)

    # Link themes across runs
    linked_themes = await link_themes(themes, company.id, session)

    # Evaluate legitimacy
    if linked_themes:
        legitimacy_results = await evaluate_legitimacy(linked_themes)
        for legit in legitimacy_results:
            for theme in linked_themes:
                if str(theme.id) == legit["theme_id"]:
                    theme.legitimacy_score = legit["legitimacy_score"]
                    theme.legitimacy_class = legit["legitimacy_class"]
                    theme.legitimacy_reasoning = legit["reasoning"]
        await session.commit()

    return run_id
```

- [ ] **Step 4: Run all pipeline tests to verify they pass**

```bash
uv run pytest tests/test_pipeline_runner.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/signalgraph/pipeline/runner.py tests/test_pipeline_runner.py
git commit -m "feat: full pipeline with memory linking and legitimacy evaluation"
```

---

## Phase 4: Scheduling + Output

### Task 13: Brief Generator

**Files:**
- Create: `src/signalgraph/pipeline/briefer.py`
- Create: `tests/test_briefer.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_briefer.py`:

```python
import uuid
from datetime import datetime, timedelta, timezone

from signalgraph.models.analysis import Theme
from signalgraph.models.company import Company
from signalgraph.pipeline.briefer import generate_brief


async def test_generate_brief_from_themes(db_session):
    company = Company(name="Brief Co", slug="brief-co", search_terms=["brief"])
    db_session.add(company)
    await db_session.commit()

    run_id = uuid.uuid4()

    themes = [
        Theme(
            company_id=company.id,
            run_id=run_id,
            name="Battery drain after v4.2",
            summary="Multiple users report rapid battery drain following the 4.2 update",
            first_seen=datetime.now(timezone.utc) - timedelta(days=3),
            last_seen=datetime.now(timezone.utc),
            status="active",
            platforms=["reddit", "appstore"],
            mention_count=42,
            avg_sentiment=-0.7,
            legitimacy_score=0.92,
            legitimacy_class="organic",
            legitimacy_reasoning="Cross-platform, gradual growth",
        ),
        Theme(
            company_id=company.id,
            run_id=run_id,
            name="New dark mode praise",
            summary="Users love the new dark mode feature",
            first_seen=datetime.now(timezone.utc) - timedelta(days=1),
            last_seen=datetime.now(timezone.utc),
            status="emerging",
            platforms=["reddit"],
            mention_count=15,
            avg_sentiment=0.8,
            legitimacy_score=0.75,
            legitimacy_class="organic",
            legitimacy_reasoning="Authentic positive feedback",
        ),
    ]
    for t in themes:
        db_session.add(t)
    await db_session.commit()

    brief = await generate_brief(company, run_id, db_session)

    assert "summary" in brief
    assert "emerging_themes" in brief
    assert "trending_themes" in brief
    assert "legitimacy_alerts" in brief
    assert "recommended_actions" in brief
    assert len(brief["trending_themes"]) >= 1
    assert brief["trending_themes"][0]["name"] == "Battery drain after v4.2"


async def test_generate_brief_empty_themes(db_session):
    company = Company(name="Empty Co", slug="empty-co", search_terms=["empty"])
    db_session.add(company)
    await db_session.commit()

    brief = await generate_brief(company, uuid.uuid4(), db_session)

    assert brief["summary"] == "No significant themes detected in this run."
    assert brief["emerging_themes"] == []
    assert brief["trending_themes"] == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_briefer.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement brief generator**

Create `src/signalgraph/pipeline/briefer.py`:

```python
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from signalgraph.models.analysis import Theme
from signalgraph.models.company import Company


async def generate_brief(
    company: Company,
    run_id: uuid.UUID,
    session: AsyncSession,
) -> dict:
    result = await session.execute(
        select(Theme)
        .where(Theme.company_id == company.id)
        .where(Theme.status.in_(["emerging", "active", "declining"]))
        .order_by(Theme.mention_count.desc())
    )
    themes = list(result.scalars().all())

    if not themes:
        return {
            "summary": "No significant themes detected in this run.",
            "emerging_themes": [],
            "trending_themes": [],
            "legitimacy_alerts": [],
            "competitive_signals": [],
            "recommended_actions": [],
        }

    emerging = [_theme_to_dict(t) for t in themes if t.status == "emerging"]
    trending = [_theme_to_dict(t) for t in themes if t.status in ("active", "declining")]
    alerts = [
        _theme_to_dict(t)
        for t in themes
        if t.legitimacy_class in ("suspected_coordinated", "bot_amplified")
    ]

    # Build actions from high-signal themes
    actions = []
    for theme in themes:
        if theme.mention_count >= 20 and theme.avg_sentiment < -0.3:
            if theme.legitimacy_score and theme.legitimacy_score > 0.7:
                actions.append(
                    f"Respond to '{theme.name}' -- {theme.mention_count} mentions, "
                    f"{theme.legitimacy_score:.0%} organic, "
                    f"on {', '.join(theme.platforms or [])}"
                )

    # Build summary from top theme
    top = themes[0]
    summary = (
        f"Top signal: '{top.name}' with {top.mention_count} mentions "
        f"(sentiment: {top.avg_sentiment:+.2f}) across {', '.join(top.platforms or [])}."
    )

    return {
        "summary": summary,
        "emerging_themes": emerging,
        "trending_themes": trending,
        "legitimacy_alerts": alerts,
        "competitive_signals": [],
        "recommended_actions": actions,
    }


def _theme_to_dict(theme: Theme) -> dict:
    return {
        "id": str(theme.id),
        "name": theme.name,
        "summary": theme.summary,
        "status": theme.status,
        "platforms": theme.platforms,
        "mention_count": theme.mention_count,
        "avg_sentiment": theme.avg_sentiment,
        "legitimacy_score": theme.legitimacy_score,
        "legitimacy_class": theme.legitimacy_class,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_briefer.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/signalgraph/pipeline/briefer.py tests/test_briefer.py
git commit -m "feat: intelligence brief generator from theme analysis"
```

---

### Task 14: Brief + Theme + Mention API Endpoints

**Files:**
- Create: `src/signalgraph/api/briefs.py`
- Create: `src/signalgraph/api/themes.py`
- Create: `src/signalgraph/api/mentions.py`
- Create: `src/signalgraph/schemas/brief.py`
- Create: `src/signalgraph/schemas/analysis.py`
- Create: `src/signalgraph/schemas/mention.py`
- Modify: `src/signalgraph/main.py`
- Create: `tests/test_mention_api.py`

- [ ] **Step 1: Write failing tests for brief and mention APIs**

Create `tests/test_mention_api.py`:

```python
import uuid
from datetime import datetime, timezone

from signalgraph.models.company import Company
from signalgraph.models.mention import RawMention
from signalgraph.models.brief import Brief


async def test_get_mentions_for_company(client, db_session):
    company = Company(name="Mention Co", slug="mention-co", search_terms=["m"])
    db_session.add(company)
    await db_session.commit()

    mention = RawMention(
        company_id=company.id,
        source="reddit",
        source_id="test-1",
        text="Test mention text",
        published_at=datetime.now(timezone.utc),
        raw_data={},
    )
    db_session.add(mention)
    await db_session.commit()

    response = await client.get(f"/api/companies/{company.id}/mentions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["text"] == "Test mention text"


async def test_get_latest_brief(client, db_session):
    company = Company(name="Brief Co", slug="brief-api-co", search_terms=["b"])
    db_session.add(company)
    await db_session.commit()

    brief = Brief(
        company_id=company.id,
        run_id=uuid.uuid4(),
        content={"summary": "Test brief", "themes": []},
        summary="Test brief summary",
    )
    db_session.add(brief)
    await db_session.commit()

    response = await client.get(f"/api/companies/{company.id}/briefs")
    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "Test brief summary"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_mention_api.py -v
```

Expected: FAIL.

- [ ] **Step 3: Create Pydantic schemas**

Create `src/signalgraph/schemas/mention.py`:

```python
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
```

Create `src/signalgraph/schemas/analysis.py`:

```python
import uuid

from pydantic import BaseModel


class ThemeResponse(BaseModel):
    id: uuid.UUID
    name: str
    summary: str
    status: str
    platforms: list[str]
    mention_count: int
    avg_sentiment: float
    legitimacy_score: float | None
    legitimacy_class: str | None

    model_config = {"from_attributes": True}
```

Create `src/signalgraph/schemas/brief.py`:

```python
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
```

- [ ] **Step 4: Create API endpoints**

Create `src/signalgraph/api/mentions.py`:

```python
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from signalgraph.database import get_session
from signalgraph.models.mention import RawMention
from signalgraph.schemas.mention import MentionResponse

router = APIRouter(tags=["mentions"])


@router.get(
    "/api/companies/{company_id}/mentions", response_model=list[MentionResponse]
)
async def list_mentions(
    company_id: uuid.UUID,
    source: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    query = (
        select(RawMention)
        .where(RawMention.company_id == company_id)
        .order_by(RawMention.published_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if source:
        query = query.where(RawMention.source == source)

    result = await session.execute(query)
    return result.scalars().all()
```

Create `src/signalgraph/api/briefs.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from signalgraph.database import get_session
from signalgraph.models.brief import Brief
from signalgraph.schemas.brief import BriefResponse

router = APIRouter(tags=["briefs"])


@router.get("/api/companies/{company_id}/briefs", response_model=BriefResponse)
async def get_latest_brief(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Brief)
        .where(Brief.company_id == company_id)
        .order_by(Brief.created_at.desc())
        .limit(1)
    )
    brief = result.scalar_one_or_none()
    if not brief:
        raise HTTPException(status_code=404, detail="No briefs found")
    return brief
```

Create `src/signalgraph/api/themes.py`:

```python
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from signalgraph.database import get_session
from signalgraph.models.analysis import Theme
from signalgraph.schemas.analysis import ThemeResponse

router = APIRouter(tags=["themes"])


@router.get(
    "/api/companies/{company_id}/themes", response_model=list[ThemeResponse]
)
async def list_themes(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Theme)
        .where(Theme.company_id == company_id)
        .where(Theme.status.in_(["emerging", "active", "declining"]))
        .order_by(Theme.mention_count.desc())
    )
    return result.scalars().all()
```

- [ ] **Step 5: Register all new routers in main.py**

Update `src/signalgraph/main.py`:

```python
from fastapi import FastAPI

from signalgraph.api.briefs import router as briefs_router
from signalgraph.api.companies import router as companies_router
from signalgraph.api.health import router as health_router
from signalgraph.api.mentions import router as mentions_router
from signalgraph.api.themes import router as themes_router


def create_app() -> FastAPI:
    app = FastAPI(title="SignalGraph", version="0.1.0")
    app.include_router(health_router)
    app.include_router(companies_router)
    app.include_router(briefs_router)
    app.include_router(mentions_router)
    app.include_router(themes_router)
    return app


app = create_app()
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_mention_api.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/signalgraph/schemas/ src/signalgraph/api/ src/signalgraph/main.py tests/test_mention_api.py
git commit -m "feat: API endpoints for briefs, themes, and mentions"
```

---

### Task 15: Pipeline Trigger Endpoint + Brief Saving

**Files:**
- Modify: `src/signalgraph/api/companies.py`
- Modify: `src/signalgraph/pipeline/runner.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_company_api.py`:

```python
from unittest.mock import AsyncMock, patch


async def test_trigger_pipeline_run(client, db_session):
    create = await client.post(
        "/api/companies",
        json={"name": "Run Co", "slug": "run-co", "search_terms": ["run"]},
    )
    company_id = create.json()["id"]

    with patch("signalgraph.api.companies.run_pipeline") as mock_run:
        mock_run.return_value = "fake-run-id"

        response = await client.post(f"/api/companies/{company_id}/run")

    assert response.status_code == 202
    assert "run_id" in response.json()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_company_api.py::test_trigger_pipeline_run -v
```

Expected: FAIL.

- [ ] **Step 3: Add the trigger endpoint**

Add to `src/signalgraph/api/companies.py`:

```python
from signalgraph.pipeline.runner import run_pipeline


@router.post("/{company_id}/run", status_code=202)
async def trigger_run(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    run_id = await run_pipeline(company=company, sources=[], session=session)
    return {"run_id": str(run_id), "status": "started"}
```

- [ ] **Step 4: Update pipeline runner to save briefs**

Add to the end of `run_pipeline` in `src/signalgraph/pipeline/runner.py`, before `return run_id`:

Add import at top:

```python
from signalgraph.models.brief import Brief
from signalgraph.pipeline.briefer import generate_brief
```

Add at the end of `run_pipeline`, before `return run_id`:

```python
    # Generate and save brief
    brief_content = await generate_brief(company, run_id, session)
    brief = Brief(
        company_id=company.id,
        run_id=run_id,
        content=brief_content,
        summary=brief_content["summary"],
    )
    session.add(brief)
    await session.commit()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_company_api.py -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/signalgraph/api/companies.py src/signalgraph/pipeline/runner.py
git commit -m "feat: pipeline trigger endpoint and brief persistence"
```

---

### Task 16: Scheduler (APScheduler)

**Files:**
- Create: `src/signalgraph/scheduler.py`
- Create: `tests/test_scheduler.py`
- Modify: `src/signalgraph/main.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_scheduler.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

from signalgraph.scheduler import schedule_company, get_scheduler


def test_get_scheduler_returns_instance():
    scheduler = get_scheduler()
    assert scheduler is not None


def test_schedule_company_adds_job():
    scheduler = get_scheduler()
    # Clear any existing jobs
    scheduler.remove_all_jobs()

    schedule_company(
        scheduler=scheduler,
        company_id="test-uuid",
        company_slug="test-co",
        cron_expression="0 */6 * * *",
    )

    jobs = scheduler.get_jobs()
    assert len(jobs) == 1
    assert "test-co" in jobs[0].id


def test_schedule_company_replaces_existing_job():
    scheduler = get_scheduler()
    scheduler.remove_all_jobs()

    schedule_company(scheduler, "test-uuid", "test-co", "0 */6 * * *")
    schedule_company(scheduler, "test-uuid", "test-co", "0 */2 * * *")

    jobs = scheduler.get_jobs()
    assert len(jobs) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_scheduler.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement the scheduler**

Create `src/signalgraph/scheduler.py`:

```python
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def parse_cron(expression: str) -> dict:
    """Parse '0 */6 * * *' into CronTrigger kwargs."""
    parts = expression.split()
    if len(parts) != 5:
        return {"hour": "*/6"}
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


def schedule_company(
    scheduler: AsyncIOScheduler,
    company_id: str,
    company_slug: str,
    cron_expression: str,
) -> None:
    job_id = f"pipeline-{company_slug}"

    # Remove existing job if present
    existing = scheduler.get_job(job_id)
    if existing:
        scheduler.remove_job(job_id)

    cron_kwargs = parse_cron(cron_expression)
    trigger = CronTrigger(**cron_kwargs)

    scheduler.add_job(
        _run_company_pipeline,
        trigger=trigger,
        id=job_id,
        kwargs={"company_id": company_id},
        replace_existing=True,
    )
    logger.info(f"Scheduled pipeline for {company_slug}: {cron_expression}")


async def _run_company_pipeline(company_id: str) -> None:
    """Called by the scheduler. Creates its own DB session."""
    from signalgraph.database import SessionLocal
    from signalgraph.models.company import Company
    from signalgraph.pipeline.runner import run_pipeline

    from sqlalchemy import select

    async with SessionLocal() as session:
        result = await session.execute(
            select(Company).where(Company.id == company_id)
        )
        company = result.scalar_one_or_none()
        if not company or not company.active:
            return

        try:
            run_id = await run_pipeline(
                company=company, sources=[], session=session
            )
            logger.info(f"Pipeline completed for {company.slug}: run_id={run_id}")
        except Exception:
            logger.exception(f"Pipeline failed for {company.slug}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_scheduler.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Wire scheduler into FastAPI app lifecycle**

Update `src/signalgraph/main.py`:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from signalgraph.api.briefs import router as briefs_router
from signalgraph.api.companies import router as companies_router
from signalgraph.api.health import router as health_router
from signalgraph.api.mentions import router as mentions_router
from signalgraph.api.themes import router as themes_router
from signalgraph.scheduler import get_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = get_scheduler()
    scheduler.start()
    yield
    scheduler.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title="SignalGraph", version="0.1.0", lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(companies_router)
    app.include_router(briefs_router)
    app.include_router(mentions_router)
    app.include_router(themes_router)
    return app


app = create_app()
```

- [ ] **Step 6: Run all tests**

```bash
uv run pytest -v
```

Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/signalgraph/scheduler.py src/signalgraph/main.py tests/test_scheduler.py
git commit -m "feat: APScheduler integration with per-company cron scheduling"
```

---

### Task 17: Remaining Source Adapters (YouTube, HN, Play Store, Web Search)

**Files:**
- Create: `src/signalgraph/sources/youtube.py`
- Create: `src/signalgraph/sources/hackernews.py`
- Create: `src/signalgraph/sources/playstore.py`
- Create: `src/signalgraph/sources/websearch.py`

- [ ] **Step 1: Write tests for all remaining sources**

Create `tests/test_sources_remaining.py`:

```python
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from signalgraph.sources.hackernews import HackerNewsSource
from signalgraph.sources.youtube import YouTubeSource


MOCK_HN_RESPONSE = {
    "hits": [
        {
            "objectID": "hn-1",
            "title": "Acme releases new product",
            "comment_text": None,
            "story_text": "Acme just launched their latest product and it looks great",
            "author": "hn_user",
            "story_url": "https://example.com/acme",
            "created_at_i": 1712000000,
        },
        {
            "objectID": "hn-2",
            "title": None,
            "comment_text": "I've been using Acme for years, really disappointed lately",
            "story_text": None,
            "author": "critic",
            "story_url": None,
            "created_at_i": 1712100000,
        },
    ]
}


async def test_hackernews_fetch():
    source = HackerNewsSource()

    mock_response = AsyncMock()
    mock_response.json.return_value = MOCK_HN_RESPONSE
    mock_response.raise_for_status = lambda: None

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_cls.return_value = mock_client

        mentions = await source.fetch(
            search_terms=["Acme"],
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )

    assert len(mentions) == 2
    assert mentions[0].source == "hackernews"
    assert mentions[0].source_id == "hn-1"


MOCK_YT_RESPONSE = {
    "items": [
        {
            "id": "yt-comment-1",
            "snippet": {
                "topLevelComment": {
                    "id": "yt-comment-1",
                    "snippet": {
                        "textDisplay": "This product is amazing!",
                        "authorDisplayName": "YouTuber",
                        "publishedAt": "2024-04-01T10:00:00Z",
                        "videoId": "abc123",
                    }
                }
            }
        }
    ]
}


async def test_youtube_fetch():
    source = YouTubeSource(api_key="test-key")

    mock_search = AsyncMock()
    mock_search.json.return_value = {
        "items": [{"id": {"videoId": "abc123"}}]
    }
    mock_search.raise_for_status = lambda: None

    mock_comments = AsyncMock()
    mock_comments.json.return_value = MOCK_YT_RESPONSE
    mock_comments.raise_for_status = lambda: None

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.side_effect = [mock_search, mock_comments]
        mock_cls.return_value = mock_client

        mentions = await source.fetch(
            search_terms=["Acme"],
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )

    assert len(mentions) == 1
    assert mentions[0].source == "youtube"
    assert "amazing" in mentions[0].text
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_sources_remaining.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement Hacker News source**

Create `src/signalgraph/sources/hackernews.py`:

```python
from datetime import datetime, timezone

import httpx

from signalgraph.sources.base import RawMentionData


class HackerNewsSource:
    name = "hackernews"

    async def fetch(
        self, search_terms: list[str], since: datetime
    ) -> list[RawMentionData]:
        mentions: list[RawMentionData] = []
        since_ts = int(since.timestamp())

        async with httpx.AsyncClient() as client:
            for term in search_terms:
                response = await client.get(
                    "https://hn.algolia.com/api/v1/search_by_date",
                    params={
                        "query": term,
                        "numericFilters": f"created_at_i>{since_ts}",
                        "hitsPerPage": 100,
                    },
                )
                response.raise_for_status()
                data = response.json()

                for hit in data.get("hits", []):
                    text = (
                        hit.get("comment_text")
                        or hit.get("story_text")
                        or hit.get("title")
                        or ""
                    )
                    if not text:
                        continue

                    created = datetime.fromtimestamp(
                        hit["created_at_i"], tz=timezone.utc
                    )

                    mentions.append(
                        RawMentionData(
                            source="hackernews",
                            source_id=hit["objectID"],
                            text=text,
                            published_at=created,
                            author=hit.get("author"),
                            url=hit.get("story_url")
                            or f"https://news.ycombinator.com/item?id={hit['objectID']}",
                            raw_data=hit,
                        )
                    )

        return mentions
```

- [ ] **Step 4: Implement YouTube source**

Create `src/signalgraph/sources/youtube.py`:

```python
from datetime import datetime, timezone

import httpx

from signalgraph.sources.base import RawMentionData


class YouTubeSource:
    name = "youtube"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def fetch(
        self, search_terms: list[str], since: datetime
    ) -> list[RawMentionData]:
        mentions: list[RawMentionData] = []

        async with httpx.AsyncClient() as client:
            for term in search_terms:
                # Search for videos
                search_resp = await client.get(
                    "https://www.googleapis.com/youtube/v3/search",
                    params={
                        "q": term,
                        "part": "id",
                        "type": "video",
                        "order": "date",
                        "maxResults": 10,
                        "publishedAfter": since.isoformat(),
                        "key": self.api_key,
                    },
                )
                search_resp.raise_for_status()
                videos = search_resp.json().get("items", [])

                for video in videos:
                    video_id = video["id"]["videoId"]

                    # Get comments for each video
                    comments_resp = await client.get(
                        "https://www.googleapis.com/youtube/v3/commentThreads",
                        params={
                            "videoId": video_id,
                            "part": "snippet",
                            "maxResults": 50,
                            "key": self.api_key,
                        },
                    )
                    comments_resp.raise_for_status()

                    for item in comments_resp.json().get("items", []):
                        comment = item["snippet"]["topLevelComment"]["snippet"]

                        try:
                            published = datetime.fromisoformat(
                                comment["publishedAt"].replace("Z", "+00:00")
                            )
                        except ValueError:
                            published = datetime.now(timezone.utc)

                        if published < since:
                            continue

                        mentions.append(
                            RawMentionData(
                                source="youtube",
                                source_id=item["id"],
                                text=comment["textDisplay"],
                                published_at=published,
                                author=comment.get("authorDisplayName"),
                                url=f"https://youtube.com/watch?v={comment.get('videoId', video_id)}",
                                raw_data=comment,
                            )
                        )

        return mentions
```

- [ ] **Step 5: Create stub adapters for Play Store and Web Search**

Create `src/signalgraph/sources/playstore.py`:

```python
import asyncio
from datetime import datetime

import httpx

from signalgraph.sources.base import RawMentionData


class PlayStoreSource:
    name = "playstore"

    def __init__(self, app_id: str):
        self.app_id = app_id

    async def fetch(
        self, search_terms: list[str], since: datetime
    ) -> list[RawMentionData]:
        # Play Store requires web scraping with polite crawling (1 req/2s per PRD).
        # Full implementation requires HTML parsing of review pages.
        # For MVP, return empty list. Replace with real scraper when ready.
        return []
```

Create `src/signalgraph/sources/websearch.py`:

```python
from datetime import datetime

import httpx

from signalgraph.sources.base import RawMentionData


class WebSearchSource:
    name = "websearch"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def fetch(
        self, search_terms: list[str], since: datetime
    ) -> list[RawMentionData]:
        # Requires SerpAPI or similar key. Stub for now.
        # Full implementation: search each term, extract snippets + URLs,
        # optionally fetch page content for richer analysis.
        return []
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_sources_remaining.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/signalgraph/sources/ tests/test_sources_remaining.py
git commit -m "feat: YouTube, HN, Play Store, web search source adapters"
```

---

### Task 18: Run All Tests + Final Verification

- [ ] **Step 1: Run the full test suite**

```bash
uv run pytest -v --tb=short
```

Expected: All tests PASS.

- [ ] **Step 2: Verify the server starts**

```bash
uv run uvicorn signalgraph.main:app --host 0.0.0.0 --port 8000 &
sleep 2
curl -s http://localhost:8000/api/health | python3 -m json.tool
kill %1
```

Expected: `{"status": "ok", "version": "0.1.0"}`

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "chore: verify full test suite and server startup"
```
