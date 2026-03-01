"""Input sanitization for API boundary.

Provides text cleaning and prompt injection detection for user inputs.
"""

from __future__ import annotations

import re
import unicodedata

# Characters to strip: C0/C1 control chars except \n \r \t
_CONTROL_CHAR_RE = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]"
)

# Collapse runs of whitespace (3+ newlines → 2, 3+ spaces → 1)
_EXCESSIVE_NEWLINES_RE = re.compile(r"\n{3,}")
_EXCESSIVE_SPACES_RE = re.compile(r"[^\S\n]{3,}")

# Prompt injection patterns — common attempts to override system instructions.
# These are matched case-insensitively against the sanitized input.
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    # Direct system prompt overrides
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?|directions?)", re.IGNORECASE),
    re.compile(r"ignore\s+everything\s+(above|before|previously)", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?|directions?)", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?|directions?)", re.IGNORECASE),
    # Role-playing as system
    re.compile(r"you\s+are\s+now\s+(a|an|the)\s+", re.IGNORECASE),
    re.compile(r"new\s+(system\s+)?instructions?:\s*", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+are", re.IGNORECASE),
    # Jailbreak markers
    re.compile(r"\bDAN\s+mode\b", re.IGNORECASE),
    re.compile(r"\bjailbreak\b", re.IGNORECASE),
    re.compile(r"do\s+anything\s+now", re.IGNORECASE),
    # Prompt leak attempts
    re.compile(r"(reveal|show|print|output|repeat|display)\s+(me\s+)?(your|the)\s+(system\s+)?(prompt|instructions?|rules?)", re.IGNORECASE),
    re.compile(r"what\s+(are|is)\s+your\s+(system\s+)?(prompt|instructions?|rules?)", re.IGNORECASE),
]


def sanitize_text(text: str) -> str:
    """Clean user input text.

    - Strips leading/trailing whitespace
    - Removes null bytes and control characters (preserves \\n \\r \\t)
    - Normalizes Unicode to NFC form
    - Collapses excessive whitespace
    """
    # NFC normalization (combine diacritics, canonical form)
    text = unicodedata.normalize("NFC", text)

    # Remove control characters
    text = _CONTROL_CHAR_RE.sub("", text)

    # Collapse excessive whitespace
    text = _EXCESSIVE_NEWLINES_RE.sub("\n\n", text)
    text = _EXCESSIVE_SPACES_RE.sub(" ", text)

    return text.strip()


def detect_prompt_injection(text: str) -> str | None:
    """Check text for prompt injection patterns.

    Returns the matched pattern description if injection is detected,
    or None if the input appears clean.
    """
    for pattern in _INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None
