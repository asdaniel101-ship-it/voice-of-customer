import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from signalgraph.models.analysis import Theme


def _name_similarity(a: str, b: str) -> float:
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
    """Link new themes to existing ones by name similarity.

    For each new theme, find the best matching existing theme. If score >= threshold,
    merge into existing (update last_seen, add mention_count, average sentiments,
    merge platforms, delete the new duplicate). Otherwise keep as-is.

    Returns list of linked themes (either updated existing or new).
    """
    # Query existing active/emerging themes for this company
    result = await session.execute(
        select(Theme).where(
            Theme.company_id == company_id,
            Theme.status.in_(["active", "emerging"]),
        )
    )
    existing_themes = result.scalars().all()

    # Build a set of new theme IDs so we can exclude them from existing
    new_theme_ids = {t.id for t in new_themes}
    existing_themes = [t for t in existing_themes if t.id not in new_theme_ids]

    linked: list[Theme] = []

    for new_theme in new_themes:
        best_match: Theme | None = None
        best_score = 0.0

        for existing in existing_themes:
            score = _name_similarity(new_theme.name, existing.name)
            if score > best_score:
                best_score = score
                best_match = existing

        if best_match is not None and best_score >= similarity_threshold:
            # Merge new_theme into best_match
            now = datetime.now(timezone.utc)
            best_match.last_seen = now

            # Sum mention counts
            best_match.mention_count += new_theme.mention_count

            # Average sentiments weighted by mention count (simple average of averages
            # weighted by respective mention counts)
            old_count = best_match.mention_count - new_theme.mention_count
            new_count = new_theme.mention_count
            total = old_count + new_count
            if total > 0:
                best_match.avg_sentiment = (
                    (best_match.avg_sentiment * old_count + new_theme.avg_sentiment * new_count)
                    / total
                )

            # Merge platforms (union)
            merged_platforms = list(
                set(best_match.platforms or []) | set(new_theme.platforms or [])
            )
            best_match.platforms = merged_platforms

            # Delete the duplicate new theme
            await session.delete(new_theme)

            linked.append(best_match)
        else:
            linked.append(new_theme)

    await session.flush()
    return linked


async def build_history_summary(
    company_id: uuid.UUID,
    session: AsyncSession,
    limit: int = 20,
) -> str:
    """Build a text summary of recent themes for a company.

    Returns formatted string listing each theme with status, mention_count,
    avg_sentiment, and platforms. Returns 'No prior themes detected.' if empty.
    """
    result = await session.execute(
        select(Theme)
        .where(
            Theme.company_id == company_id,
            Theme.status.in_(["active", "emerging", "declining"]),
        )
        .order_by(Theme.last_seen.desc())
        .limit(limit)
    )
    themes = result.scalars().all()

    if not themes:
        return "No prior themes detected."

    lines = []
    for theme in themes:
        platforms_str = ", ".join(theme.platforms) if theme.platforms else "unknown"
        lines.append(
            f"- {theme.name} | status={theme.status} | mentions={theme.mention_count} "
            f"| avg_sentiment={theme.avg_sentiment:.2f} | platforms={platforms_str}"
        )

    return "\n".join(lines)
