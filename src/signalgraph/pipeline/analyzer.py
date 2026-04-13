import asyncio
import json
import logging
import re
import uuid
from datetime import datetime

import anthropic

from signalgraph.models.mention import RawMention

logger = logging.getLogger("signalgraph.pipeline")

ANALYSIS_PROMPT = """You are a product intelligence analyst. Analyze the following customer mentions for {company_name}.

{history_summary}

Mentions to analyze:
{mentions_json}

Your task:
1. **Sentiment tagging**: For each mention, assign a sentiment score from -1.0 (very negative) to 1.0 (very positive) and a confidence score from 0.0 to 1.0.
2. **Topic extraction**: Extract SPECIFIC topic labels — not generic categories. Use details from the text: feature names, version numbers, competitor names, device types, dollar amounts. BAD: "pricing". GOOD: "Standard plan price increase to $15.49".
3. **Theme clustering**: Group mentions into specific, observable themes. Theme names should describe what's happening, not what category it falls into. BAD: "Content Issues". GOOD: "Users frustrated by removal of classic shows (The Office, Friends)".

Return ONLY valid JSON in this exact format (no markdown, no code fences, just raw JSON):
{{
    "analysis_results": [
        {{
            "mention_id": "<uuid>",
            "sentiment": 0.0,
            "sentiment_confidence": 0.9,
            "topics": ["specific topic 1", "specific topic 2"]
        }}
    ],
    "themes": [
        {{
            "name": "Specific observable theme",
            "summary": "What users are specifically saying",
            "mention_ids": ["<uuid>"],
            "platforms": ["reddit"],
            "avg_sentiment": 0.0
        }}
    ]
}}

Be precise and analytical. Each mention must appear in analysis_results. Only group mentions into a theme if they share a SPECIFIC concern — don't force unrelated mentions into vague buckets. It's better to have a mention in no theme than in a wrong one."""

CONSOLIDATION_PROMPT = """You are a product intelligence analyst reporting to a PM who checks this dashboard daily. You have {mention_count} customer mentions about {company_name} that were analyzed in batches, producing {raw_theme_count} raw themes.

Your job: merge these into 5-10 consolidated themes that a PM can act on THIS WEEK.

CRITICAL — theme naming rules:
- Themes must be SPECIFIC and OBSERVABLE, not category labels
- BAD: "Pricing and Value Concerns", "Content Quality Issues", "User Experience"
- GOOD: "Users threatening to cancel over $23/month price hike", "Buffering and crashes on Samsung/LG smart TVs", "Backlash against removing download limits on Basic plan"
- Each theme name should tell a PM exactly what's happening without reading the summary
- Include specific details: dollar amounts, feature names, device types, competitor names, version numbers — whatever the data shows
- If a theme is too vague to act on, it's not a real signal

Raw themes to consolidate:
{themes_json}

For each consolidated theme, provide:
- **name**: A specific, observable signal (see rules above). Write it like a headline a PM would Slack to their team.
- **summary**: 2-3 sentences. What are users specifically saying? Quote or paraphrase real language. Why should the PM care right now?
- **severity**: "critical" (revenue/churn risk), "high" (growing frustration), "medium" (notable pattern), "low" (early signal worth watching)
- **sentiment_avg**: weighted average sentiment across all absorbed mentions
- **mention_ids**: ALL mention IDs from all absorbed raw themes (merge the lists)
- **platforms**: ALL platforms from absorbed themes (deduplicated)
- **mention_count**: total mention count
- **sub_themes**: list of the absorbed raw theme names for drill-down context
- **action_items**: 1-2 concrete, specific next steps (not "investigate further" — say what to investigate and where)

Return ONLY valid JSON (no markdown, no code fences):
{{
    "consolidated_themes": [
        {{
            "name": "Specific observable signal headline",
            "summary": "What users are saying, with specifics...",
            "severity": "high",
            "sentiment_avg": -0.5,
            "mention_ids": ["uuid1", "uuid2"],
            "platforms": ["reddit", "appstore"],
            "mention_count": 45,
            "sub_themes": ["Raw Theme 1", "Raw Theme 2"],
            "action_items": ["Do X specifically", "Check Y in Z"]
        }}
    ]
}}

Prioritize themes by business impact. Merge aggressively — 5-10 themes total, not more. Drop noise themes that aren't actionable."""

BATCH_SIZE = 30
CONCURRENCY = 5


def _extract_json(text: str) -> dict:
    """Extract JSON from markdown code blocks or raw text."""
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(text[first_brace : last_brace + 1])
        except json.JSONDecodeError:
            pass

    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return {"analysis_results": [], "themes": []}


async def _analyze_batch(
    mentions_data: list[dict],
    company_name: str,
    history_summary: str,
    client: anthropic.AsyncAnthropic,
) -> dict:
    """Analyze a single batch of mentions."""
    mentions_json = json.dumps(mentions_data, indent=2)

    history_section = ""
    if history_summary:
        history_section = f"Historical context:\n{history_summary}\n"

    prompt = ANALYSIS_PROMPT.format(
        company_name=company_name,
        history_summary=history_section,
        mentions_json=mentions_json,
    )

    message = await client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text
    return _extract_json(response_text)


async def _consolidate_themes(
    raw_themes: list[dict],
    company_name: str,
    mention_count: int,
    client: anthropic.AsyncAnthropic,
) -> list[dict]:
    """Merge overlapping raw themes into 5-10 consolidated themes."""
    if len(raw_themes) <= 10:
        # Already few enough, just add default fields
        for t in raw_themes:
            t.setdefault("severity", "medium")
            t.setdefault("sub_themes", [])
            t.setdefault("action_items", [])
            t.setdefault("mention_count", len(t.get("mention_ids", [])))
            t.setdefault("sentiment_avg", t.get("avg_sentiment", 0.0))
        return raw_themes

    # Prepare theme summaries for consolidation (don't send all mention IDs to save tokens)
    themes_for_prompt = []
    for t in raw_themes:
        themes_for_prompt.append({
            "name": t["name"],
            "summary": t["summary"],
            "mention_ids": t.get("mention_ids", []),
            "platforms": t.get("platforms", []),
            "avg_sentiment": t.get("avg_sentiment", 0.0),
            "mention_count": len(t.get("mention_ids", [])),
        })

    prompt = CONSOLIDATION_PROMPT.format(
        company_name=company_name,
        mention_count=mention_count,
        raw_theme_count=len(raw_themes),
        themes_json=json.dumps(themes_for_prompt, indent=2),
    )

    message = await client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = _extract_json(message.content[0].text)
    return raw.get("consolidated_themes", raw_themes[:10])


async def analyze_mentions(
    mentions: list[RawMention],
    company_name: str,
    run_id: uuid.UUID,
    history_summary: str = "",
) -> dict:
    """Analyze mentions using Claude Sonnet for sentiment, topics, and theme clustering.

    Batches mentions, analyzes in parallel, then consolidates themes into 5-10.
    Returns dict with "analysis_results" and "themes" lists.
    """
    if not mentions:
        return {"analysis_results": [], "themes": []}

    from signalgraph.config import settings

    if not settings.anthropic_api_key:
        logger.error("[analyzer] No API key found! Skipping analysis.")
        return {"analysis_results": [], "themes": []}

    # Prepare mention data
    mentions_data = []
    for mention in mentions:
        published_at = mention.published_at
        if isinstance(published_at, datetime):
            published_at_str = published_at.isoformat()
        else:
            published_at_str = str(published_at)

        mentions_data.append({
            "id": str(mention.id),
            "text": mention.text[:500],
            "source": mention.source,
            "published_at": published_at_str,
            "author": mention.author,
        })

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    # Build and process batches in parallel
    batches = [
        mentions_data[i : i + BATCH_SIZE]
        for i in range(0, len(mentions_data), BATCH_SIZE)
    ]

    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def _limited_batch(idx: int, batch: list[dict]) -> dict:
        async with semaphore:
            try:
                logger.info(f"[analyzer] Processing batch {idx + 1}/{len(batches)} ({len(batch)} mentions)...")
                result = await _analyze_batch(batch, company_name, history_summary, client)
                logger.info(f"[analyzer] Batch {idx + 1} done: {len(result.get('analysis_results', []))} results, {len(result.get('themes', []))} themes")
                return result
            except Exception as e:
                import traceback
                logger.error(f"[analyzer] Batch {idx + 1} FAILED: {type(e).__name__}: {e}")
                logger.error(traceback.format_exc())
                return {"analysis_results": [], "themes": []}

    logger.info(f"[analyzer] {len(batches)} batches, {CONCURRENCY} concurrent")
    results = await asyncio.gather(*[_limited_batch(i, b) for i, b in enumerate(batches)])

    all_analysis_results = []
    all_raw_themes = []

    for raw in results:
        for result in raw.get("analysis_results", []):
            all_analysis_results.append({
                "mention_id": result["mention_id"],
                "sentiment": result["sentiment"],
                "sentiment_confidence": result["sentiment_confidence"],
                "topics": result.get("topics", []),
                "run_id": str(run_id),
            })

        for theme in raw.get("themes", []):
            all_raw_themes.append({
                "name": theme["name"],
                "summary": theme["summary"],
                "mention_ids": theme.get("mention_ids", []),
                "platforms": theme.get("platforms", []),
                "avg_sentiment": theme.get("avg_sentiment", 0.0),
                "run_id": str(run_id),
            })

    # Consolidate overlapping themes into 5-10
    try:
        consolidated = await _consolidate_themes(
            all_raw_themes, company_name, len(mentions), client
        )
    except Exception:
        consolidated = all_raw_themes[:10]

    # Normalize consolidated themes to match expected format
    final_themes = []
    for t in consolidated:
        final_themes.append({
            "name": t["name"],
            "summary": t["summary"],
            "mention_ids": t.get("mention_ids", []),
            "platforms": t.get("platforms", []),
            "avg_sentiment": t.get("sentiment_avg", t.get("avg_sentiment", 0.0)),
            "mention_count": t.get("mention_count", len(t.get("mention_ids", []))),
            "severity": t.get("severity", "medium"),
            "sub_themes": t.get("sub_themes", []),
            "action_items": t.get("action_items", []),
            "run_id": str(run_id),
        })

    return {"analysis_results": all_analysis_results, "themes": final_themes}
