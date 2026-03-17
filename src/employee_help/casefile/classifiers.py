"""DocumentClassifier — classifies case files by structural cues."""

from __future__ import annotations

import re
from enum import Enum


class DocumentType(str, Enum):
    """Classification of a litigation document."""

    COMPLAINT = "complaint"
    ANSWER = "answer"
    DEMAND_LETTER = "demand_letter"
    PAY_STUB = "pay_stub"
    PERSONNEL = "personnel"
    EMAIL = "email"
    DISCOVERY = "discovery"
    GENERIC = "generic"


# ── Keyword patterns per document type ──────────────────────────────

# Each entry: (compiled regex, weight).
# We scan the first ~3000 chars for heading-level cues, then full text
# for keyword density.

_COMPLAINT_HEADINGS = re.compile(
    r"(?i)\b(?:complaint|cause\s+of\s+action|prayer\s+for\s+relief"
    r"|general\s+allegations|factual\s+allegations"
    r"|first\s+amended\s+complaint|second\s+amended\s+complaint"
    r"|third\s+amended\s+complaint)\b"
)

_COMPLAINT_KEYWORDS = re.compile(
    r"(?i)\b(?:plaintiff\s+alleges|hereby\s+complains|comes\s+now"
    r"|cause\s+of\s+action\s+for|prayer\s+for\s+relief"
    r"|DOES\s+\d+\s+through\s+\d+"
    r"|incorporated\s+by\s+reference"
    r"|general\s+damages|special\s+damages|punitive\s+damages"
    r"|superior\s+court\s+of\s+(?:the\s+state\s+of\s+)?california)\b"
)

_ANSWER_HEADINGS = re.compile(
    r"(?i)\b(?:answer\s+to\s+complaint|answer\s+to.*amended\s+complaint"
    r"|affirmative\s+defenses?|general\s+denial)\b"
)

_ANSWER_KEYWORDS = re.compile(
    r"(?i)\b(?:defendant\s+(?:hereby\s+)?answers"
    r"|denies\s+(?:each\s+and\s+every|generally\s+and\s+specifically)"
    r"|affirmative\s+defense"
    r"|admits?\s+(?:the\s+)?allegations?"
    r"|lacks\s+(?:sufficient\s+)?information"
    r"|answering\s+(?:defendant|party))\b"
)

_DEMAND_HEADINGS = re.compile(
    r"(?i)\b(?:demand\s+letter|settlement\s+demand"
    r"|pre-?litigation\s+demand|demand\s+for\s+(?:payment|settlement))\b"
)

_DEMAND_KEYWORDS = re.compile(
    r"(?i)\b(?:demand\s+(?:that\s+you|payment|settlement)"
    r"|hereby\s+demands?"
    r"|settlement\s+(?:offer|demand|proposal)"
    r"|pre-?litigation"
    r"|we\s+(?:are\s+)?(?:prepared|willing)\s+to\s+(?:settle|accept)"
    r"|in\s+lieu\s+of\s+(?:litigation|filing)"
    r"|statutory\s+(?:damages|penalties))\b"
)

_PAY_STUB_HEADINGS = re.compile(
    r"(?i)\b(?:earnings?\s+statement|pay\s+stub|paycheck|payroll"
    r"|wage\s+statement|pay\s+(?:period|date))\b"
)

_PAY_STUB_KEYWORDS = re.compile(
    r"(?i)\b(?:gross\s+pay|net\s+pay|ytd|year\s+to\s+date"
    r"|federal\s+(?:tax|withholding)|state\s+(?:tax|withholding)"
    r"|fica|social\s+security|medicare"
    r"|hours?\s+worked|regular\s+(?:hours?|rate)"
    r"|overtime\s+(?:hours?|rate|pay)"
    r"|deductions?|garnishment"
    r"|pay\s+period|check\s+(?:date|number))\b"
)

_PERSONNEL_HEADINGS = re.compile(
    r"(?i)\b(?:offer\s+(?:of\s+)?(?:employment|letter)"
    r"|employment\s+(?:agreement|contract|offer)"
    r"|termination\s+(?:letter|notice)"
    r"|separation\s+(?:agreement|notice)"
    r"|performance\s+(?:review|evaluation|improvement)"
    r"|employee\s+handbook"
    r"|warning\s+notice|written\s+warning"
    r"|disciplinary\s+(?:action|notice))\b"
)

_PERSONNEL_KEYWORDS = re.compile(
    r"(?i)\b(?:position\s+of|base\s+salary|annual\s+(?:salary|compensation)"
    r"|start\s+date|reporting\s+to|at-?will\s+employ"
    r"|hereby\s+terminated|last\s+day\s+of\s+employment"
    r"|severance|non-?compete|non-?disclosure"
    r"|performance\s+(?:rating|score|goals)"
    r"|improvement\s+plan|corrective\s+action"
    r"|employee\s+(?:name|id|number))\b"
)

_EMAIL_HEADINGS = re.compile(
    r"(?i)^(?:from|to|subject|date|sent|cc|bcc)\s*:", re.MULTILINE
)

_DISCOVERY_HEADINGS = re.compile(
    r"(?i)\b(?:interrogator(?:y|ies)|request\s+for\s+(?:production|admission)"
    r"|demand\s+for\s+inspection"
    r"|special\s+interrogator(?:y|ies)"
    r"|form\s+interrogator(?:y|ies)"
    r"|request\s+for\s+(?:production\s+of\s+)?documents"
    r"|propounding\s+party|responding\s+party)\b"
)

_DISCOVERY_KEYWORDS = re.compile(
    r"(?i)\b(?:propounding\s+party|responding\s+party"
    r"|set\s+(?:no\.\s*|number\s*)\d+"
    r"|(?:please\s+)?identify\s+(?:all|each|every)"
    r"|produce\s+(?:all|each|any)\s+documents?"
    r"|admit\s+(?:or\s+deny|that)"
    r"|objection|without\s+waiving"
    r"|code\s+of\s+civil\s+procedure\s+(?:section|§)\s*20[123]\d)\b"
)

# Caption block pattern — "v." or "vs." between party names
_CAPTION_PATTERN = re.compile(
    r"(?i)(?:plaintiff|petitioner)s?\s*[,\n].*?\bv[s]?\.?\s+", re.DOTALL
)


class DocumentClassifier:
    """Classifies extracted text into a DocumentType.

    Classification uses a weighted scoring approach:
    1. Heading-level cues in the first ~3000 chars (high weight)
    2. Keyword density across the full text (moderate weight)
    3. Structural cues like caption blocks (bonus)
    """

    # Weights for heading matches vs keyword matches
    _HEADING_WEIGHT = 3.0
    _KEYWORD_WEIGHT = 1.0
    _CAPTION_BONUS = 2.0

    # Minimum score to beat "generic"
    _MIN_SCORE = 2.0

    def classify(self, text: str, filename: str = "") -> DocumentType:
        """Classify a document based on its extracted text and filename.

        Args:
            text: The extracted text content of the file.
            filename: Original filename (used for hint signals).

        Returns:
            The most likely DocumentType.
        """
        if not text or not text.strip():
            return DocumentType.GENERIC

        # Email detection is special — structural (headers at top)
        if self._is_email(text, filename):
            return DocumentType.EMAIL

        scores: dict[DocumentType, float] = {dt: 0.0 for dt in DocumentType}

        head = text[:3000]

        # Score each document type
        self._score_type(
            scores, DocumentType.COMPLAINT, head, text,
            _COMPLAINT_HEADINGS, _COMPLAINT_KEYWORDS,
        )
        self._score_type(
            scores, DocumentType.ANSWER, head, text,
            _ANSWER_HEADINGS, _ANSWER_KEYWORDS,
        )
        self._score_type(
            scores, DocumentType.DEMAND_LETTER, head, text,
            _DEMAND_HEADINGS, _DEMAND_KEYWORDS,
        )
        self._score_type(
            scores, DocumentType.PAY_STUB, head, text,
            _PAY_STUB_HEADINGS, _PAY_STUB_KEYWORDS,
        )
        self._score_type(
            scores, DocumentType.PERSONNEL, head, text,
            _PERSONNEL_HEADINGS, _PERSONNEL_KEYWORDS,
        )
        self._score_type(
            scores, DocumentType.DISCOVERY, head, text,
            _DISCOVERY_HEADINGS, _DISCOVERY_KEYWORDS,
        )

        # Caption block bonus for complaint/answer
        if _CAPTION_PATTERN.search(head):
            scores[DocumentType.COMPLAINT] += self._CAPTION_BONUS
            scores[DocumentType.ANSWER] += self._CAPTION_BONUS * 0.5

        # Filename hints (low weight, tiebreaker)
        self._apply_filename_hints(scores, filename)

        # Pick the winner
        best_type = max(scores, key=lambda dt: scores[dt])
        if scores[best_type] < self._MIN_SCORE:
            return DocumentType.GENERIC

        return best_type

    def _score_type(
        self,
        scores: dict[DocumentType, float],
        doc_type: DocumentType,
        head: str,
        full_text: str,
        heading_re: re.Pattern[str],
        keyword_re: re.Pattern[str],
    ) -> None:
        """Add heading + keyword scores for a document type."""
        heading_hits = len(heading_re.findall(head))
        keyword_hits = len(keyword_re.findall(full_text))

        scores[doc_type] += heading_hits * self._HEADING_WEIGHT
        scores[doc_type] += keyword_hits * self._KEYWORD_WEIGHT

    @staticmethod
    def _is_email(text: str, filename: str) -> bool:
        """Detect email by structural headers at the top."""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in ("eml", "msg", "mbox"):
            return True

        # Check for email header lines in the first 500 chars
        head = text[:500]
        header_count = len(_EMAIL_HEADINGS.findall(head))
        return header_count >= 3

    @staticmethod
    def _apply_filename_hints(
        scores: dict[DocumentType, float], filename: str,
    ) -> None:
        """Apply small filename-based score boosts."""
        if not filename:
            return
        fn = filename.lower()
        hints: list[tuple[str, DocumentType]] = [
            ("complaint", DocumentType.COMPLAINT),
            ("amended_complaint", DocumentType.COMPLAINT),
            ("answer", DocumentType.ANSWER),
            ("demand", DocumentType.DEMAND_LETTER),
            ("pay_stub", DocumentType.PAY_STUB),
            ("paystub", DocumentType.PAY_STUB),
            ("paycheck", DocumentType.PAY_STUB),
            ("earnings", DocumentType.PAY_STUB),
            ("offer_letter", DocumentType.PERSONNEL),
            ("termination", DocumentType.PERSONNEL),
            ("separation", DocumentType.PERSONNEL),
            ("handbook", DocumentType.PERSONNEL),
            ("performance", DocumentType.PERSONNEL),
            ("interrogator", DocumentType.DISCOVERY),
            ("rfpd", DocumentType.DISCOVERY),
            ("rfa", DocumentType.DISCOVERY),
            ("production", DocumentType.DISCOVERY),
        ]
        for hint, doc_type in hints:
            if hint in fn:
                scores[doc_type] += 1.0
