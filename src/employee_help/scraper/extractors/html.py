"""HTML content extraction for CRD pages.

Extracts main content from Playwright-rendered HTML, strips
navigation/boilerplate, and preserves semantic structure as Markdown.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from bs4 import BeautifulSoup, NavigableString, Tag


@dataclass
class HtmlExtractionResult:
    title: str
    markdown: str
    headings: list[str]
    source_url: str
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    last_modified: str | None = None


# Elements to remove entirely from the DOM before extraction
_REMOVE_SELECTORS = [
    "header",
    "footer",
    "nav",
    "#top-header",
    "#main-header",
    "#main-footer",
    ".et-fixed-header",
    "#footer-widgets",
    "#footer-info",
    ".et_pb_fullwidth_menu",
    ".cookie-notice",
    ".cookie-consent",
    "script",
    "style",
    "noscript",
    "iframe",
    ".screen-reader-text",
    ".et_pb_social_media_follow",
    '[role="navigation"]',
    ".bottom-nav",
    "#sidebar",
    ".et_pb_sidebar",
]


def extract_html(
    page_html: str,
    source_url: str,
    last_modified: str | None = None,
    content_selector: str | None = None,
) -> HtmlExtractionResult:
    """Extract structured content from a rendered CRD page HTML.

    Args:
        page_html: Full rendered HTML string (from Playwright's inner_html or page content).
        source_url: The URL this page was fetched from.
        last_modified: HTTP Last-Modified header value, if available.

    Returns:
        HtmlExtractionResult with cleaned Markdown content and metadata.
    """
    soup = BeautifulSoup(page_html, "lxml")

    # Extract title before stripping
    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)
        # Remove common suffixes like " | CRD" or " - Civil Rights Department"
        title = re.sub(r"\s*[|–-]\s*(CRD|Civil Rights Department).*$", "", title).strip()
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)

    # Remove boilerplate elements
    for selector in _REMOVE_SELECTORS:
        for el in soup.select(selector):
            el.decompose()

    # Find the main content area — config selector is authoritative when set
    main = None
    if content_selector:
        main = soup.select_one(content_selector)
    if main is None:
        main = soup.select_one("#et-main-area") or soup.select_one("main") or soup.select_one("body")
    if main is None:
        return HtmlExtractionResult(
            title=title or "Unknown",
            markdown="",
            headings=[],
            source_url=source_url,
            last_modified=last_modified,
        )

    # Convert to Markdown
    headings: list[str] = []
    lines = _element_to_markdown(main, headings)
    markdown = _clean_markdown("\n".join(lines))

    return HtmlExtractionResult(
        title=title or "Unknown",
        markdown=markdown,
        headings=headings,
        source_url=source_url,
        last_modified=last_modified,
    )


def _element_to_markdown(element: Tag, headings: list[str]) -> list[str]:
    """Recursively convert a BeautifulSoup element tree to Markdown lines."""
    lines: list[str] = []

    for child in element.children:
        if isinstance(child, NavigableString):
            text = str(child).strip()
            if text:
                lines.append(text)
            continue

        if not isinstance(child, Tag):
            continue

        tag = child.name.lower()

        # Headings
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            text = child.get_text(strip=True)
            if text:
                prefix = "#" * level
                lines.append("")
                lines.append(f"{prefix} {text}")
                lines.append("")
                headings.append(text)
            continue

        # Paragraphs
        if tag == "p":
            text = child.get_text(strip=True)
            if text:
                lines.append("")
                lines.append(text)
            continue

        # Unordered lists
        if tag == "ul":
            lines.append("")
            for li in child.find_all("li", recursive=False):
                text = li.get_text(strip=True)
                if text:
                    lines.append(f"- {text}")
            lines.append("")
            continue

        # Ordered lists
        if tag == "ol":
            lines.append("")
            for i, li in enumerate(child.find_all("li", recursive=False), 1):
                text = li.get_text(strip=True)
                if text:
                    lines.append(f"{i}. {text}")
            lines.append("")
            continue

        # Tables
        if tag == "table":
            table_md = _table_to_markdown(child)
            if table_md:
                lines.append("")
                lines.extend(table_md)
                lines.append("")
            continue

        # Strong / bold
        if tag in ("strong", "b"):
            text = child.get_text(strip=True)
            if text:
                lines.append(f"**{text}**")
            continue

        # Emphasis / italic
        if tag in ("em", "i"):
            text = child.get_text(strip=True)
            if text:
                lines.append(f"*{text}*")
            continue

        # Links
        if tag == "a":
            text = child.get_text(strip=True)
            href = child.get("href", "")
            if text and href:
                lines.append(f"[{text}]({href})")
            elif text:
                lines.append(text)
            continue

        # Accordion panels (CRD FAQ pattern) — extract content
        classes = child.get("class", [])
        if isinstance(classes, list) and "js-accordion__panel" in classes:
            inner_lines = _element_to_markdown(child, headings)
            lines.extend(inner_lines)
            continue

        # Generic block elements — recurse
        if tag in ("div", "section", "article", "span", "blockquote", "details", "summary"):
            inner_lines = _element_to_markdown(child, headings)
            lines.extend(inner_lines)
            continue

        # Skip elements like br, hr, img
        if tag == "br":
            lines.append("")
            continue
        if tag == "hr":
            lines.append("\n---\n")
            continue

        # Fallback: extract text from anything else
        text = child.get_text(strip=True)
        if text:
            lines.append(text)

    return lines


def _table_to_markdown(table: Tag) -> list[str]:
    """Convert an HTML table to Markdown table lines."""
    rows = table.find_all("tr")
    if not rows:
        return []

    md_rows: list[list[str]] = []
    for row in rows:
        cells = row.find_all(["th", "td"])
        md_rows.append([c.get_text(strip=True) for c in cells])

    if not md_rows:
        return []

    # Determine column count from widest row
    max_cols = max(len(r) for r in md_rows)
    # Pad short rows
    for r in md_rows:
        while len(r) < max_cols:
            r.append("")

    lines = []
    # Header row
    lines.append("| " + " | ".join(md_rows[0]) + " |")
    lines.append("| " + " | ".join("---" for _ in md_rows[0]) + " |")
    # Data rows
    for row in md_rows[1:]:
        lines.append("| " + " | ".join(row) + " |")

    return lines


def _clean_markdown(text: str) -> str:
    """Normalize whitespace and clean up generated Markdown."""
    # Collapse 3+ newlines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove leading/trailing whitespace per line, but preserve blank lines
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)
    # Remove "Skip to Main Content" and similar artifacts
    text = re.sub(r"Skip to (?:Main )?Content\s*", "", text, flags=re.IGNORECASE)
    return text.strip()
