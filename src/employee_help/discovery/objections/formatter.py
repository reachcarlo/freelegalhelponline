"""Template-driven objection formatter.

Uses str.format_map() with a SafeFormatMap fallback for missing keys.
No Jinja2 — no conditional logic needed, simpler and safer.
"""

from __future__ import annotations

import structlog

from employee_help.discovery.objections.models import (
    AnalysisResult,
    DISCOVERY_TYPE_SINGULAR,
    DEFAULT_TEMPLATE,
    DISCLAIMER,
    GeneratedObjection,
    ObjectionTemplate,
    ResponseDiscoveryType,
    WAIVER_PREAMBLE,
)

logger = structlog.get_logger(__name__)


class SafeFormatMap(dict):
    """Dict subclass that returns '{key}' for missing keys instead of raising KeyError."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


class ObjectionFormatter:
    """Format generated objections using variable-tag templates."""

    def format_objection(
        self,
        objection: GeneratedObjection,
        template: ObjectionTemplate = DEFAULT_TEMPLATE,
        request_number: int | str = "",
        discovery_type: ResponseDiscoveryType = ResponseDiscoveryType.INTERROGATORIES,
    ) -> str:
        """Format a single objection using the template."""
        # Build the primary statutory citation (first one)
        statutory_citation = ""
        if objection.statutory_citations:
            c = objection.statutory_citations[0]
            statutory_citation = f"{c.code} {c.section}"

        # Build primary case citation (first one)
        case_citation = ""
        if objection.case_citations:
            c = objection.case_citations[0]
            case_citation = f"{c.name} {c.citation}"

        # Build all statutory citations
        all_statutory = "; ".join(
            f"{c.code} {c.section}" for c in objection.statutory_citations
        )

        # Build all case citations (italic case names)
        all_cases = "; ".join(
            f"{c.name} {c.citation}" for c in objection.case_citations
        )

        # Build the format map
        values = SafeFormatMap({
            "OBJECTION": objection.ground.label,
            "EXPLANATION": objection.explanation,
            "STATUTORY_CITATION": statutory_citation,
            "CASE_CITATION": case_citation,
            "ALL_STATUTORY_CITATIONS": all_statutory,
            "ALL_CASE_CITATIONS": all_cases,
            "REQUEST_NUMBER": str(request_number),
            "DISCOVERY_TYPE": DISCOVERY_TYPE_SINGULAR.get(
                discovery_type, "Request"
            ),
        })

        return template.template.format_map(values)

    def format_request(
        self,
        result: AnalysisResult,
        template: ObjectionTemplate = DEFAULT_TEMPLATE,
        include_request_text: bool = False,
        include_waiver_language: bool = False,
    ) -> str:
        """Format all objections for a single request."""
        parts: list[str] = []

        # Optionally include the request text
        if include_request_text:
            type_label = DISCOVERY_TYPE_SINGULAR.get(
                result.request.discovery_type, "REQUEST"
            ).upper()
            parts.append(
                f"{type_label} NO. {result.request.request_number}:\n"
                f"{result.request.request_text}"
            )
            parts.append("")  # blank line
            parts.append(
                f"RESPONSE TO {type_label} NO. {result.request.request_number}:"
            )

        if result.no_objections_rationale:
            parts.append(result.no_objections_rationale)
        elif result.objections:
            formatted_objections = [
                self.format_objection(
                    obj,
                    template=template,
                    request_number=result.request.request_number,
                    discovery_type=result.request.discovery_type,
                )
                for obj in result.objections
            ]
            parts.append(template.separator.join(formatted_objections))

            if include_waiver_language:
                parts.append("")
                parts.append(WAIVER_PREAMBLE)

        return "\n".join(parts)

    def format_batch(
        self,
        results: list[AnalysisResult],
        template: ObjectionTemplate = DEFAULT_TEMPLATE,
        include_request_text: bool = False,
        include_waiver_language: bool = False,
    ) -> str:
        """Format all results in a batch, separated by double newlines."""
        formatted = [
            self.format_request(
                r,
                template=template,
                include_request_text=include_request_text,
                include_waiver_language=include_waiver_language,
            )
            for r in results
        ]

        output = "\n\n".join(formatted)

        # Append disclaimer
        output += f"\n\n---\n{DISCLAIMER}"

        return output
