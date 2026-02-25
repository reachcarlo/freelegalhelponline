"""Content cleaning for extracted text.

Normalizes whitespace, removes boilerplate artifacts, and prepares
extracted Markdown for chunking.
"""

from __future__ import annotations

import re

# Boilerplate patterns commonly found in CRD page extractions
_BOILERPLATE_PATTERNS = [
    re.compile(r"Skip to (?:Main )?Content\s*", re.IGNORECASE),
    re.compile(r"^\s*Search\s*$", re.MULTILINE),
    re.compile(r"^\s*Menu\s*$", re.MULTILINE),
    re.compile(r"^\s*Close\s*$", re.MULTILINE),
    # CRD contact footer that appears on many pages
    re.compile(
        r"(?:Sacramento|CA\s+\d{5})[\s\S]*?(?:800-884-1684|contact\.center@calcivilrights\.ca\.gov)[\s\S]*?(?:711|relay\s+service).*$",
        re.IGNORECASE | re.MULTILINE,
    ),
    # Cookie/privacy notices
    re.compile(r"(?:We use cookies|cookie policy|privacy policy).*$", re.IGNORECASE | re.MULTILINE),
]

# Unicode cleanup
_UNICODE_REPLACEMENTS = {
    "\u2018": "'",  # Left single quotation mark
    "\u2019": "'",  # Right single quotation mark
    "\u201c": '"',  # Left double quotation mark
    "\u201d": '"',  # Right double quotation mark
    "\u2013": "-",  # En dash
    "\u2014": " - ",  # Em dash
    "\u2026": "...",  # Ellipsis
    "\u00a0": " ",  # Non-breaking space
    "\u200b": "",  # Zero-width space
    "\ufeff": "",  # BOM
}


def clean(text: str) -> str:
    """Clean extracted text content.

    Args:
        text: Raw extracted Markdown text.

    Returns:
        Cleaned text with normalized whitespace and boilerplate removed.
    """
    if not text:
        return ""

    result = text

    # Fix Unicode characters
    for char, replacement in _UNICODE_REPLACEMENTS.items():
        result = result.replace(char, replacement)

    # Fix common UTF-8 mojibake (mis-decoded smart quotes/dashes)
    _MOJIBAKE = {
        "\xc3\xa2\xe2\x82\xac\xe2\x84\xa2": "'",
        "\xc3\xa2\xe2\x82\xac\xe2\x80\x9c": "-",
        "\xc3\xa2\xe2\x82\xac\xc5\x93": '"',
    }
    for bad, good in _MOJIBAKE.items():
        result = result.replace(bad, good)

    # Remove boilerplate patterns
    for pattern in _BOILERPLATE_PATTERNS:
        result = pattern.sub("", result)

    # Normalize whitespace within lines (but preserve Markdown structure)
    lines = result.split("\n")
    cleaned_lines = []
    for line in lines:
        # Preserve heading markers and list markers
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("-") or re.match(r"^\d+\.", stripped):
            cleaned_lines.append(stripped)
        elif stripped.startswith("|"):
            # Markdown table row — preserve
            cleaned_lines.append(stripped)
        else:
            # Normalize internal whitespace for regular text
            cleaned_lines.append(re.sub(r"[ \t]+", " ", stripped))

    result = "\n".join(cleaned_lines)

    # Collapse 3+ blank lines into 2
    result = re.sub(r"\n{3,}", "\n\n", result)

    # Remove leading/trailing whitespace
    result = result.strip()

    return result
