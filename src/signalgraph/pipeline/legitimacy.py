import json
import re

import anthropic

from signalgraph.models.analysis import Theme

LEGITIMACY_PROMPT = """You are a trust and authenticity analyst specializing in detecting coordinated inauthentic behavior in online customer feedback.

Evaluate the following themes for authenticity and legitimacy. For each theme, consider:

1. **Cross-platform corroboration**: Themes appearing across multiple independent platforms are more likely organic. A theme limited to a single platform may indicate coordination or amplification.
2. **Temporal patterns**: Organic feedback tends to grow gradually over time. A sudden spike in mentions (especially from new or low-activity accounts) may indicate coordinated activity.
3. **Account-level signals**: Consider patterns in account ages, post histories, and metadata that suggest bot or coordinated behavior vs. genuine users.
4. **Mention volume relative to platform size**: Abnormally high mention counts relative to platform norms may indicate artificial amplification.

Themes to evaluate:
{themes_json}

Return ONLY valid JSON in this exact format:
```json
[
    {{
        "theme_id": "<uuid>",
        "legitimacy_score": 0.85,
        "legitimacy_class": "organic",
        "reasoning": "Brief explanation of legitimacy assessment"
    }}
]
```

Legitimacy classes:
- "organic": Genuine user feedback, no suspicious patterns
- "suspected_coordinated": Multiple signals suggest organized campaign
- "bot_amplified": Evidence of automated or bot accounts inflating theme
- "ambiguous": Insufficient data to determine legitimacy

Legitimacy score: 0.0 (definitely inorganic) to 1.0 (definitely organic).
Assign scores and classes for ALL themes provided."""


def _extract_json(text: str) -> list:
    """Extract JSON array from markdown code blocks or raw text."""
    # Try to find JSON in a ```json ... ``` block
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1).strip())

    # Try to find raw JSON array
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        return json.loads(match.group(0).strip())

    return json.loads(text.strip())


async def evaluate_legitimacy(themes: list[Theme]) -> list[dict]:
    """Evaluate themes for authenticity using Claude Opus.

    Takes a list of Theme objects, calls Claude Opus, and returns a list of dicts
    with theme_id, legitimacy_score (0-1), legitimacy_class, and reasoning.
    """
    if not themes:
        return []

    themes_data = []
    for theme in themes:
        themes_data.append({
            "theme_id": str(theme.id),
            "name": theme.name,
            "mention_count": theme.mention_count,
            "platforms": theme.platforms or [],
            "avg_sentiment": theme.avg_sentiment,
            "status": theme.status,
        })

    themes_json = json.dumps(themes_data, indent=2)
    prompt = LEGITIMACY_PROMPT.format(themes_json=themes_json)

    client = anthropic.AsyncAnthropic()
    message = await client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text
    raw = _extract_json(response_text)

    results = []
    for item in raw:
        results.append({
            "theme_id": item["theme_id"],
            "legitimacy_score": item["legitimacy_score"],
            "legitimacy_class": item["legitimacy_class"],
            "reasoning": item.get("reasoning", ""),
        })

    return results
