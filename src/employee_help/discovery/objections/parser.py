"""Request parser for discovery objection drafter.

Extracts individual requests from unstructured pasted text. Works identically
for pasted text and extracted document text.

Two-pass architecture:
  Pass 1 — Structural (regex-based, fast): detect sections, extract numbered
           requests by header patterns, auto-detect discovery type.
  Pass 2 — LLM-assisted (future, for ambiguous input): when Pass 1 finds
           fewer requests than expected.
"""

from __future__ import annotations

import re
import uuid
from typing import Sequence

import structlog

from employee_help.discovery.objections.models import (
    ExtractedMetadata,
    ParsedRequest,
    ParseResult,
    ResponseDiscoveryType,
    SkippedSection,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Section delimiter patterns — content before/after these is separated
# ---------------------------------------------------------------------------

SECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("definitions", re.compile(
        r"^\s*DEFINITION[S]?\s*$", re.IGNORECASE | re.MULTILINE
    )),
    ("instructions", re.compile(
        r"^\s*INSTRUCTION[S]?\s*$", re.IGNORECASE | re.MULTILINE
    )),
    ("preliminary_statement", re.compile(
        r"^\s*PRELIMINARY\s+STATEMENT\s*$", re.IGNORECASE | re.MULTILINE
    )),
    ("pos", re.compile(
        r"^\s*PROOF\s+OF\s+SERVICE\b", re.IGNORECASE | re.MULTILINE
    )),
]

# ---------------------------------------------------------------------------
# Request header patterns — ordered from most specific to least
# ---------------------------------------------------------------------------

# Interrogatory headers
_SROG_PATTERN = re.compile(
    r"^\s*(?:SPECIAL\s+)?INTERROGATOR(?:Y|IES)\s+"
    r"(?:NO\.?\s*)?(\d+)\s*[:.)\s]",
    re.IGNORECASE | re.MULTILINE,
)
_SROG_ABBREV_PATTERN = re.compile(
    r"^\s*SROG\s+(?:NO\.?\s*)?(\d+)\s*[:.)\s]",
    re.IGNORECASE | re.MULTILINE,
)

# RFP headers
_RFP_LONG_PATTERN = re.compile(
    r"^\s*(?:REQUEST\s+FOR\s+PRODUCTION\s+(?:OF\s+DOCUMENTS?\s+)?"
    r"|DEMAND\s+(?:FOR\s+(?:INSPECTION|PRODUCTION)\s+(?:OF\s+DOCUMENTS?\s+)?)?)"
    r"(?:NO\.?\s*)?(\d+)\s*[:.)\s]",
    re.IGNORECASE | re.MULTILINE,
)
_RFP_SHORT_PATTERN = re.compile(
    r"^\s*(?:RFP|RFPD|DEMAND)\s+(?:NO\.?\s*)?(\d+)\s*[:.)\s]",
    re.IGNORECASE | re.MULTILINE,
)
_REQUEST_NO_PATTERN = re.compile(
    r"^\s*REQUEST\s+(?:NO\.?\s*)?(\d+)\s*[:.)\s]",
    re.IGNORECASE | re.MULTILINE,
)

# RFA headers
_RFA_LONG_PATTERN = re.compile(
    r"^\s*REQUEST\s+FOR\s+ADMISSION\s+(?:NO\.?\s*)?(\d+)\s*[:.)\s]",
    re.IGNORECASE | re.MULTILINE,
)
_RFA_SHORT_PATTERN = re.compile(
    r"^\s*(?:RFA|ADMISSION)\s+(?:NO\.?\s*)?(\d+)\s*[:.)\s]",
    re.IGNORECASE | re.MULTILINE,
)

# Bare number fallback
_BARE_NUMBER_PATTERN = re.compile(
    r"^\s*(\d+)\s*[.):\s]\s+\S",
    re.MULTILINE,
)

# Response shell detection
_RESPONSE_PATTERN = re.compile(
    r"^\s*RESPONSE\s+TO\s+(?:SPECIAL\s+)?(?:INTERROGATOR(?:Y|IES)|REQUEST|DEMAND|RFA|RFP)"
    r"\s+(?:FOR\s+(?:PRODUCTION|ADMISSION)\s+(?:OF\s+DOCUMENTS?\s+)?)?"
    r"(?:NO\.?\s*)?(\d+)\s*[:.)\s]",
    re.IGNORECASE | re.MULTILINE,
)

# ---------------------------------------------------------------------------
# Metadata extraction patterns
# ---------------------------------------------------------------------------

_PROPOUNDING_PATTERN = re.compile(
    r"PROPOUNDING\s+PARTY\s*:\s*(.+)", re.IGNORECASE
)
_RESPONDING_PATTERN = re.compile(
    r"RESPONDING\s+PARTY\s*:\s*(.+)", re.IGNORECASE
)
_SET_NUMBER_PATTERN = re.compile(
    r"SET\s+(?:NO\.?\s*|NUMBER\s*:?\s*)(\d+)", re.IGNORECASE
)

# Defined terms: ALL CAPS words (3+ chars) per CCP §2030.060(e) convention
_DEFINED_TERM_PATTERN = re.compile(r"\b([A-Z][A-Z\s]{2,}[A-Z])\b")

# Document title patterns for type detection
_TITLE_SROG_PATTERN = re.compile(
    r"(?:SPECIAL\s+)?INTERROGATOR(?:Y|IES)", re.IGNORECASE
)
_TITLE_RFP_PATTERN = re.compile(
    r"REQUEST\S?\s+FOR\s+PRODUCTION|DEMAND\s+FOR\s+(?:INSPECTION|PRODUCTION)",
    re.IGNORECASE,
)
_TITLE_RFA_PATTERN = re.compile(
    r"REQUEST\S?\s+FOR\s+ADMISSION", re.IGNORECASE
)

# Patterns grouped by discovery type for matching
_TYPE_PATTERNS: dict[ResponseDiscoveryType, list[re.Pattern[str]]] = {
    ResponseDiscoveryType.INTERROGATORIES: [_SROG_PATTERN, _SROG_ABBREV_PATTERN],
    ResponseDiscoveryType.RFPS: [_RFP_LONG_PATTERN, _RFP_SHORT_PATTERN, _REQUEST_NO_PATTERN],
    ResponseDiscoveryType.RFAS: [_RFA_LONG_PATTERN, _RFA_SHORT_PATTERN],
}


class RequestParser:
    """Parse discovery requests from unstructured text.

    Structural regex-based pass (V1). LLM-assisted pass for ambiguous
    input deferred to future version.
    """

    def parse_text(
        self,
        text: str,
        discovery_type: ResponseDiscoveryType | None = None,
    ) -> ParseResult:
        """Parse pasted text into individual requests.

        Args:
            text: Raw pasted text, may include caption, definitions,
                  instructions, requests, and proof of service.
            discovery_type: Override auto-detection. None = auto-detect.

        Returns:
            ParseResult with extracted requests, skipped sections, and metadata.
        """
        if not text or not text.strip():
            return ParseResult(
                requests=[],
                skipped_sections=[],
                metadata=ExtractedMetadata(),
                detected_type=discovery_type,
                warnings=["No text provided."],
            )

        warnings: list[str] = []

        # Step 1: Extract metadata
        metadata = self._extract_metadata(text)

        # Step 2: Detect response shell
        is_shell = bool(_RESPONSE_PATTERN.search(text))

        # Step 3: Detect and remove sections (definitions, instructions, etc.)
        text_for_parsing, skipped = self._extract_sections(text)

        # Step 4: Auto-detect discovery type from title/headers
        detected_type = discovery_type or self._detect_type(text)
        if detected_type is None:
            warnings.append(
                "Could not auto-detect discovery type. "
                "Defaulting to Interrogatories."
            )
            detected_type = ResponseDiscoveryType.INTERROGATORIES

        # Step 5: Extract individual requests
        requests = self._extract_requests(text_for_parsing, detected_type)

        if not requests:
            warnings.append(
                "No discovery requests found. This can happen when: "
                "(1) the text is from a scanned image, "
                "(2) the text uses Judicial Council checkbox formatting, or "
                "(3) the requests use unusual numbering."
            )

        logger.info(
            "requests_parsed",
            request_count=len(requests),
            skipped_sections=len(skipped),
            detected_type=detected_type.value,
            is_shell=is_shell,
        )

        return ParseResult(
            requests=requests,
            skipped_sections=skipped,
            metadata=metadata,
            detected_type=detected_type,
            is_response_shell=is_shell,
            warnings=warnings,
        )

    # ── Private methods ───────────────────────────────────────────────────

    def _extract_metadata(self, text: str) -> ExtractedMetadata:
        """Extract propounding party, responding party, and set number."""
        propounding = ""
        responding = ""
        set_number = None

        m = _PROPOUNDING_PATTERN.search(text)
        if m:
            propounding = m.group(1).strip().rstrip(";,")

        m = _RESPONDING_PATTERN.search(text)
        if m:
            responding = m.group(1).strip().rstrip(";,")

        m = _SET_NUMBER_PATTERN.search(text)
        if m:
            try:
                set_number = int(m.group(1))
            except ValueError:
                pass

        return ExtractedMetadata(
            propounding_party=propounding,
            responding_party=responding,
            set_number=set_number,
        )

    def _extract_sections(
        self, text: str
    ) -> tuple[str, list[SkippedSection]]:
        """Detect and remove non-request sections, returning cleaned text and skipped sections."""
        skipped: list[SkippedSection] = []

        # Find all section boundaries
        boundaries: list[tuple[int, int, str]] = []  # (start, end, section_type)
        for section_type, pattern in SECTION_PATTERNS:
            for m in pattern.finditer(text):
                boundaries.append((m.start(), m.end(), section_type))

        if not boundaries:
            return text, skipped

        # Sort by position
        boundaries.sort(key=lambda b: b[0])

        # For each section boundary, extract content until next section or next
        # request header (whichever comes first)
        lines = text.split("\n")
        line_offsets = _compute_line_offsets(text)

        for start, _end, section_type in boundaries:
            # Find the line number of this section header
            section_line = _offset_to_line(start, line_offsets)

            # Find the end: next section boundary, next request header, or end of text
            section_end_line = len(lines)
            for other_start, _, _ in boundaries:
                if other_start > start:
                    other_line = _offset_to_line(other_start, line_offsets)
                    section_end_line = min(section_end_line, other_line)
                    break

            # Also check for request headers (including bare numbers) to end the section
            remaining = "\n".join(lines[section_line + 1:section_end_line])
            all_patterns = [p for ps in _TYPE_PATTERNS.values() for p in ps]
            all_patterns.append(_BARE_NUMBER_PATTERN)
            for pat in all_patterns:
                m = pat.search(remaining)
                if m:
                    # Find the line of the match within remaining
                    match_line = remaining[:m.start()].count("\n")
                    section_end_line = min(
                        section_end_line,
                        section_line + 1 + match_line,
                    )

            content = "\n".join(lines[section_line + 1:section_end_line]).strip()

            # Extract defined terms for definitions sections
            defined_terms: tuple[str, ...] = ()
            if section_type == "definitions":
                terms = set(_DEFINED_TERM_PATTERN.findall(content))
                # Filter out common non-terms
                terms -= {"THE", "AND", "FOR", "NOT", "ALL", "ANY", "YOU", "YOUR",
                           "THIS", "THAT", "WITH", "FROM", "EACH", "SUCH", "HAS",
                           "WAS", "ARE", "WERE", "HAVE", "BEEN", "WILL", "DOES"}
                defined_terms = tuple(sorted(terms))

            skipped.append(SkippedSection(
                section_type=section_type,
                content=content,
                defined_terms=defined_terms,
            ))

            # Blank out the section in the text for parsing
            for i in range(section_line, min(section_end_line, len(lines))):
                lines[i] = ""

        return "\n".join(lines), skipped

    def _detect_type(self, text: str) -> ResponseDiscoveryType | None:
        """Auto-detect discovery type from document title and header patterns."""
        # Check first ~500 chars for title patterns (most reliable)
        header_text = text[:500]

        if _TITLE_RFP_PATTERN.search(header_text):
            return ResponseDiscoveryType.RFPS
        if _TITLE_RFA_PATTERN.search(header_text):
            return ResponseDiscoveryType.RFAS
        if _TITLE_SROG_PATTERN.search(header_text):
            return ResponseDiscoveryType.INTERROGATORIES

        # Count header matches across entire text
        counts: dict[ResponseDiscoveryType, int] = {}
        for dtype, patterns in _TYPE_PATTERNS.items():
            count = sum(len(pat.findall(text)) for pat in patterns)
            if count > 0:
                counts[dtype] = count

        if counts:
            return max(counts, key=counts.get)  # type: ignore[arg-type]

        # Check for "Admit that" pattern (RFA without numbered headers)
        if re.search(r"\bAdmit\s+that\b", text, re.IGNORECASE):
            return ResponseDiscoveryType.RFAS

        return None

    def _extract_requests(
        self,
        text: str,
        discovery_type: ResponseDiscoveryType,
    ) -> list[ParsedRequest]:
        """Extract individual requests using type-specific patterns."""
        # Collect all header matches with positions
        matches: list[tuple[int, int, str, re.Match[str]]] = []
        # start_pos, request_number, pattern_name, match

        # Try type-specific patterns first
        type_patterns = _TYPE_PATTERNS.get(discovery_type, [])
        for pat in type_patterns:
            for m in pat.finditer(text):
                num = int(m.group(1))
                matches.append((m.start(), num, "specific", m))

        # If no type-specific matches, try bare number fallback
        if not matches:
            for m in _BARE_NUMBER_PATTERN.finditer(text):
                num = int(m.group(1))
                # Only accept sequential numbers starting from 1 or continuing a sequence
                matches.append((m.start(), num, "bare", m))

        if not matches:
            return []

        # Sort by position
        matches.sort(key=lambda x: x[0])

        # Deduplicate: if the same request number appears at very close positions
        # (e.g., from overlapping patterns), keep only the first match
        seen_positions: set[int] = set()
        deduped: list[tuple[int, int, str, re.Match[str]]] = []
        for start, num, pname, m in matches:
            # Skip if another match is within 20 chars
            if any(abs(start - p) < 20 for p in seen_positions):
                continue
            seen_positions.add(start)
            deduped.append((start, num, pname, m))

        matches = deduped

        # Extract request text: from end of header to start of next header
        requests: list[ParsedRequest] = []
        for i, (start, num, _pname, m) in enumerate(matches):
            # Body starts after the header match
            body_start = m.end()

            # Body ends at start of next match (or end of text)
            if i + 1 < len(matches):
                body_end = matches[i + 1][0]
            else:
                body_end = len(text)

            body = text[body_start:body_end].strip()

            # Strip response shell content if present
            resp_match = _RESPONSE_PATTERN.search(body)
            if resp_match:
                body = body[:resp_match.start()].strip()

            if not body:
                continue

            requests.append(ParsedRequest(
                id=str(uuid.uuid4()),
                request_number=num,
                request_text=body,
                discovery_type=discovery_type,
            ))

        # Validate: filter bare-number results if they don't look sequential
        if matches and matches[0][2] == "bare":
            requests = self._filter_bare_number_requests(requests)

        return requests

    def _filter_bare_number_requests(
        self, requests: list[ParsedRequest]
    ) -> list[ParsedRequest]:
        """Filter bare-number matches to only sequential sequences."""
        if not requests:
            return requests

        # Must start with 1 or have at least 3 sequential numbers
        numbers = [r.request_number for r in requests]
        if isinstance(numbers[0], int) and numbers[0] != 1:
            # Check if we have at least 3 numbers and they're roughly sequential
            if len(numbers) < 3:
                return []
            sequential = sum(
                1 for i in range(len(numbers) - 1)
                if isinstance(numbers[i], int) and isinstance(numbers[i + 1], int)
                and numbers[i + 1] == numbers[i] + 1
            )
            if sequential < len(numbers) // 2:
                return []

        return requests


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def _compute_line_offsets(text: str) -> list[int]:
    """Compute the character offset of each line start."""
    offsets = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            offsets.append(i + 1)
    return offsets


def _offset_to_line(offset: int, line_offsets: Sequence[int]) -> int:
    """Convert a character offset to a line number (0-indexed)."""
    for i in range(len(line_offsets) - 1, -1, -1):
        if offset >= line_offsets[i]:
            return i
    return 0
