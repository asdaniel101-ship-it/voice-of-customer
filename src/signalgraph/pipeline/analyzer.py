import json
import re
import uuid
from datetime import datetime

import anthropic

from signalgraph.models.mention import RawMention

ANALYSIS_PROMPT = """You are a product intelligence analyst. Analyze the following customer mentions for {company_name}.

{history_summary}

Mentions to analyze:
{mentions_json}

Your task:
1. **Sentiment tagging**: For each mention, assign a sentiment score from -1.0 (very negative) to 1.0 (very positive) and a confidence score from 0.0 to 1.0.
2. **Topic extraction**: Extract free-form topic labels for each mention (e.g., "battery life", "customer support", "pricing").
3. **Theme clustering**: Group the mentions into coherent themes. Each theme should have a name, summary, list of mention IDs, list of platforms, and average sentiment.

Return ONLY valid JSON in this exact format:
```json
{{
    "analysis_results": [
        {{
            "mention_id": "<uuid>",
            "sentiment": 0.0,
            "sentiment_confidence": 0.9,
            "topics": ["topic1", "topic2"]
        }}
    ],
    "themes": [
        {{
            "name": "Theme Name",
            "summary": "Brief description of the theme",
            "mention_ids": ["<uuid>"],
            "platforms": ["reddit"],
            "avg_sentiment": 0.0
        }}
    ]
}}
```

Be precise and analytical. Each mention must appear in analysis_results. Group related mentions into themes."""


def _extract_json(text: str) -> dict:
    """Extract JSON from markdown code blocks or raw text."""
    # Try to find JSON in a ```json ... ``` block
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1).strip())

    # Try to find raw JSON object
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0).strip())

    return json.loads(text.strip())


async def analyze_mentions(
    mentions: list[RawMention],
    company_name: str,
    run_id: uuid.UUID,
    history_summary: str = "",
) -> dict:
    """Analyze mentions using Claude Sonnet for sentiment, topics, and theme clustering.

    Returns dict with "analysis_results" and "themes" lists.
    """
    if not mentions:
        return {"analysis_results": [], "themes": []}

    mentions_data = []
    for mention in mentions:
        published_at = mention.published_at
        if isinstance(published_at, datetime):
            published_at_str = published_at.isoformat()
        else:
            published_at_str = str(published_at)

        mentions_data.append({
            "id": str(mention.id),
            "text": mention.text,
            "source": mention.source,
            "published_at": published_at_str,
            "author": mention.author,
        })

    mentions_json = json.dumps(mentions_data, indent=2)

    history_section = ""
    if history_summary:
        history_section = f"Historical context:\n{history_summary}\n"

    prompt = ANALYSIS_PROMPT.format(
        company_name=company_name,
        history_summary=history_section,
        mentions_json=mentions_json,
    )

    client = anthropic.AsyncAnthropic()
    message = await client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text
    raw = _extract_json(response_text)

    # Attach run_id to each result
    analysis_results = []
    for result in raw.get("analysis_results", []):
        analysis_results.append({
            "mention_id": result["mention_id"],
            "sentiment": result["sentiment"],
            "sentiment_confidence": result["sentiment_confidence"],
            "topics": result.get("topics", []),
            "run_id": str(run_id),
        })

    themes = []
    for theme in raw.get("themes", []):
        themes.append({
            "name": theme["name"],
            "summary": theme["summary"],
            "mention_ids": theme.get("mention_ids", []),
            "platforms": theme.get("platforms", []),
            "avg_sentiment": theme.get("avg_sentiment", 0.0),
            "run_id": str(run_id),
        })

    return {"analysis_results": analysis_results, "themes": themes}
