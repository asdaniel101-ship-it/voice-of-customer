import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from signalgraph.database import Base, GUID


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("companies.id"))
    run_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True)
    mention_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("raw_mentions.id"))
    sentiment: Mapped[float] = mapped_column(Float)
    sentiment_confidence: Mapped[float] = mapped_column(Float)
    topics: Mapped[list] = mapped_column(JSON, default=list)
    theme_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("themes.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Theme(Base):
    __tablename__ = "themes"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("companies.id"))
    run_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True)
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
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True, default="medium")
    sub_themes: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    action_items: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    mention_ids: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
