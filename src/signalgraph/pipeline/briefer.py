import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from signalgraph.models.analysis import Theme
from signalgraph.models.company import Company


def _theme_to_dict(theme: Theme) -> dict:
    """Convert a Theme ORM object to a plain dict."""
    return {
        "id": str(theme.id),
        "name": theme.name,
        "summary": theme.summary,
        "status": theme.status,
        "platforms": theme.platforms or [],
        "mention_count": theme.mention_count,
        "avg_sentiment": theme.avg_sentiment,
        "legitimacy_score": theme.legitimacy_score,
        "legitimacy_class": theme.legitimacy_class,
    }


async def generate_brief(
    company: Company,
    run_id: uuid.UUID,
    session: AsyncSession,
) -> dict:
    """Generate an intelligence brief from theme analysis for a pipeline run."""
    result = await session.execute(
        select(Theme)
        .where(
            Theme.company_id == company.id,
            Theme.run_id == run_id,
            Theme.status.in_(["active", "emerging", "declining"]),
        )
        .order_by(Theme.mention_count.desc())
    )
    themes = result.scalars().all()

    if not themes:
        return {
            "summary": "No significant themes detected in this run.",
            "emerging_themes": [],
            "trending_themes": [],
            "legitimacy_alerts": [],
            "competitive_signals": [],
            "recommended_actions": [],
        }

    top = themes[0]
    platforms_str = ", ".join(top.platforms) if top.platforms else "unknown platforms"
    summary = (
        f"Top theme '{top.name}' detected {top.mention_count} mentions "
        f"with {top.avg_sentiment:.2f} avg sentiment across {platforms_str}."
    )

    emerging_themes = [_theme_to_dict(t) for t in themes if t.status == "emerging"]
    trending_themes = [_theme_to_dict(t) for t in themes if t.status in ("active", "declining")]

    legitimacy_alerts = [
        _theme_to_dict(t)
        for t in themes
        if t.legitimacy_class in ("suspected_coordinated", "bot_amplified")
    ]

    recommended_actions = []
    for theme in themes:
        if (
            theme.mention_count >= 20
            and theme.avg_sentiment < 0
            and theme.legitimacy_score is not None
            and theme.legitimacy_score > 0.7
        ):
            recommended_actions.append(
                f"Investigate '{theme.name}': {theme.mention_count} negative mentions "
                f"with legitimacy score {theme.legitimacy_score:.2f}."
            )

    return {
        "summary": summary,
        "emerging_themes": emerging_themes,
        "trending_themes": trending_themes,
        "legitimacy_alerts": legitimacy_alerts,
        "competitive_signals": [],
        "recommended_actions": recommended_actions,
    }
