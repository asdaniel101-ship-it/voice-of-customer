import re

from signalgraph.sources.base import RawMentionData

_URL_PATTERN = re.compile(r"https?://\S+")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Strip URLs and collapse whitespace."""
    text = _URL_PATTERN.sub("", text)
    text = _WHITESPACE_PATTERN.sub(" ", text)
    return text.strip()


def deduplicate(mentions: list[RawMentionData]) -> list[RawMentionData]:
    """Remove duplicate mentions by source:source_id key."""
    seen: set[str] = set()
    result: list[RawMentionData] = []
    for mention in mentions:
        key = f"{mention.source}:{mention.source_id}"
        if key not in seen:
            seen.add(key)
            result.append(mention)
    return result
