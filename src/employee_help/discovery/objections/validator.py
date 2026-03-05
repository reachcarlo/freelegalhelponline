"""Citation validation for objection drafter.

Three-pass validation:
  Pass 1: Reporter-key matching against knowledge base
  Pass 2: Flag unmatched citations as [unverified]
  Pass 3: Ground-scoped validation (citation attached to correct ground)
"""

from __future__ import annotations

import re

import structlog

from employee_help.discovery.objections.models import (
    CaseCitation,
    GeneratedObjection,
    ObjectionGround,
    StatutoryCitation,
)

logger = structlog.get_logger(__name__)

# Reporter string extraction pattern — matches "16 Cal.4th 1101" style
_REPORTER_PATTERN = re.compile(
    r"(\d+)\s+"
    r"(Cal\.\s*(?:2d|3d|4th|5th|6th|App\.\s*(?:2d|3d|4th|5th|6th))|"
    r"Cal\.Rptr\.\s*(?:2d|3d)?|"
    r"P\.\s*(?:2d|3d)?)"
    r"\s+(\d+)"
)


class CitationValidator:
    """Validate LLM-generated citations against the knowledge base.

    The LLM is instructed to use ONLY citation keys from the knowledge base.
    This validator checks that instruction was followed and flags violations.
    """

    def __init__(
        self,
        reporter_keys: dict[str, tuple[str, str]],
    ) -> None:
        """Initialize with reporter_key → (ground_id, case_name) mapping.

        Args:
            reporter_keys: From ObjectionKnowledgeBase.get_reporter_keys()
        """
        self._reporter_keys = reporter_keys

    def validate_objection(
        self,
        objection: GeneratedObjection,
    ) -> list[str]:
        """Validate citations on a single generated objection.

        Modifies objection.citation_warnings in place and returns warnings.
        """
        warnings: list[str] = []

        # Pass 1 + 2: Validate case citations via reporter-key matching
        for case_cit in objection.case_citations:
            reporter = case_cit.reporter_key
            if reporter not in self._reporter_keys:
                msg = f"[unverified] Citation not in knowledge base: {case_cit.citation}"
                warnings.append(msg)
            # Pass 3: Ground-scoped validation
            elif self._reporter_keys[reporter][0] != objection.ground.ground_id:
                expected_ground = self._reporter_keys[reporter][0]
                msg = (
                    f"Citation '{case_cit.name}' is typically used for "
                    f"[{expected_ground}], not [{objection.ground.ground_id}]."
                )
                warnings.append(msg)

        objection.citation_warnings.extend(warnings)
        return warnings

    def validate_batch(
        self,
        objections: list[GeneratedObjection],
    ) -> list[str]:
        """Validate all objections in a batch. Returns all warnings."""
        all_warnings: list[str] = []
        for obj in objections:
            w = self.validate_objection(obj)
            all_warnings.extend(w)
        return all_warnings

    def resolve_case_citation(
        self,
        reporter_key: str,
        ground: ObjectionGround,
    ) -> CaseCitation | None:
        """Look up a case citation from the ground's citations by reporter key."""
        for case in ground.case_citations:
            if case.reporter_key == reporter_key:
                return case
        return None

    def resolve_statutory_citation(
        self,
        code: str,
        section: str,
        ground: ObjectionGround,
    ) -> StatutoryCitation | None:
        """Look up a statutory citation from the ground's citations."""
        for stat in ground.statutory_citations:
            if stat.code == code and stat.section == section:
                return stat
        return None

    @staticmethod
    def extract_reporter_key(citation_text: str) -> str | None:
        """Extract a reporter key string from a free-text citation.

        E.g., "(1997) 16 Cal.4th 1101, 1108" → "16 Cal.4th 1101"
        """
        m = _REPORTER_PATTERN.search(citation_text)
        if m:
            vol = m.group(1)
            reporter = m.group(2)
            page = m.group(3)
            # Normalize whitespace in reporter name
            reporter = re.sub(r"\s+", " ", reporter)
            return f"{vol} {reporter} {page}"
        return None
