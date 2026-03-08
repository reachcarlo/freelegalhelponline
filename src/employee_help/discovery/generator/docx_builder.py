"""DOCX document builder for California pleading paper discovery tools.

Generates filled Word documents for:
- Special Interrogatories (SROGs)
- Requests for Production of Documents (RFPDs)
- Requests for Admission (RFAs — attachment pages)

Uses docxtpl (Jinja2-templated DOCX) on a California 28-line
pleading paper template.

Pure computation — no DB, no ML, no external services.
"""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

from ..case_info import (
    defendant_block,
    document_title,
    plaintiff_block,
    propounding_party_name,
    responding_party_name,
    set_number_label,
)
from ..definitions import (
    STANDARD_PRODUCTION_INSTRUCTIONS,
    standard_definitions,
)
from ..models import (
    CaseInfo,
    DiscoveryRequest,
    DiscoveryToolType,
)
from ..models import RFA_FACT_LIMIT, SROG_LIMIT
from .pleading_template import create_pleading_template

# ---------------------------------------------------------------------------
# Template directory (for caching generated templates)
# ---------------------------------------------------------------------------

TEMPLATE_DIR = Path(__file__).parent / "templates"


def _get_or_create_template() -> Path:
    """Get the pleading paper template, creating it if it doesn't exist."""
    template_path = TEMPLATE_DIR / "pleading_paper.docx"
    if not template_path.exists():
        create_pleading_template(template_path)
    return template_path


# ---------------------------------------------------------------------------
# Request formatting
# ---------------------------------------------------------------------------


def _format_srog_requests(
    requests: list[DiscoveryRequest],
) -> list[dict[str, str]]:
    """Format SROGs for template rendering.

    Special interrogatories use "SPECIAL INTERROGATORY NO. X" labels.
    """
    formatted = []
    for i, req in enumerate(requests, start=1):
        formatted.append({
            "label": f"SPECIAL INTERROGATORY NO. {i}:",
            "text": req.text,
        })
    return formatted


def _format_rfpd_requests(
    requests: list[DiscoveryRequest],
) -> list[dict[str, str]]:
    """Format RFPDs for template rendering.

    Requests for production use "REQUEST FOR PRODUCTION NO. X" labels.
    """
    formatted = []
    for i, req in enumerate(requests, start=1):
        formatted.append({
            "label": f"REQUEST FOR PRODUCTION NO. {i}:",
            "text": req.text,
        })
    return formatted


def _format_rfa_requests(
    requests: list[DiscoveryRequest],
) -> list[dict[str, str]]:
    """Format RFAs for template rendering.

    Requests for admission use "REQUEST FOR ADMISSION NO. X" labels.
    """
    formatted = []
    for i, req in enumerate(requests, start=1):
        formatted.append({
            "label": f"REQUEST FOR ADMISSION NO. {i}:",
            "text": req.text,
        })
    return formatted


# ---------------------------------------------------------------------------
# Heading constants
# ---------------------------------------------------------------------------

TOOL_HEADINGS: dict[DiscoveryToolType, str] = {
    DiscoveryToolType.SROGS: "SPECIAL INTERROGATORIES",
    DiscoveryToolType.RFPDS: "REQUESTS FOR PRODUCTION OF DOCUMENTS AND THINGS",
    DiscoveryToolType.RFAS: "REQUESTS FOR ADMISSION",
}

TOOL_LABELS: dict[DiscoveryToolType, str] = {
    DiscoveryToolType.SROGS: "SPECIAL INTERROGATORIES",
    DiscoveryToolType.RFPDS: "REQUESTS FOR PRODUCTION OF DOCUMENTS AND THINGS",
    DiscoveryToolType.RFAS: "REQUESTS FOR ADMISSION",
}


# ---------------------------------------------------------------------------
# Declaration of Necessity
# ---------------------------------------------------------------------------


def _build_declaration_context(
    tool_type: DiscoveryToolType,
    case_info: CaseInfo,
    requests: list[DiscoveryRequest],
) -> dict[str, str | int] | None:
    """Build the declaration context dict if requests exceed the statutory limit.

    Returns None when no declaration is required.
    """
    attorney_for = (
        case_info.attorney.attorney_for
        or propounding_party_name(case_info)
    )
    justification = (
        "the issues in this litigation are complex and the "
        "information sought is essential to the prosecution of "
        "this action and cannot be obtained by other means"
    )

    if tool_type == DiscoveryToolType.SROGS and len(requests) > SROG_LIMIT:
        return {
            "ccp_section": "2030.050",
            "limit_section": "2030.030",
            "declarant_name": case_info.attorney.name,
            "attorney_for": attorney_for,
            "request_count": len(requests),
            "request_type_plural": "specially prepared interrogatories",
            "request_type_singular": "interrogatory",
            "justification": justification,
        }

    if tool_type == DiscoveryToolType.RFAS and len(requests) > RFA_FACT_LIMIT:
        return {
            "ccp_section": "2033.050",
            "limit_section": "2033.030",
            "declarant_name": case_info.attorney.name,
            "attorney_for": attorney_for,
            "request_count": len(requests),
            "request_type_plural": "requests for admission",
            "request_type_singular": "request for admission",
            "justification": justification,
        }

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_discovery_docx(
    tool_type: DiscoveryToolType,
    case_info: CaseInfo,
    requests: list[DiscoveryRequest],
    *,
    include_definitions: bool = True,
    include_production_instructions: bool | None = None,
    custom_definitions: dict[str, str] | None = None,
) -> bytes:
    """Build a California pleading paper DOCX for the given discovery tool.

    Args:
        tool_type: Which discovery tool (SROGs, RFPDs, or RFAs).
        case_info: Case and attorney information.
        requests: The discovery requests to include.
        include_definitions: Whether to include the definitions section.
        include_production_instructions: Whether to include production
            instructions (defaults to True for RFPDs only).
        custom_definitions: Custom definitions to use instead of standard.

    Returns:
        Filled DOCX as bytes.

    Raises:
        ValueError: If tool_type is not a DOCX-based discovery tool.
    """
    if tool_type not in (DiscoveryToolType.SROGS, DiscoveryToolType.RFPDS, DiscoveryToolType.RFAS):
        raise ValueError(
            f"Tool type {tool_type.value} does not use DOCX output. "
            "Use the PDF filler for FROGs."
        )

    # Determine production instructions
    if include_production_instructions is None:
        include_production_instructions = (tool_type == DiscoveryToolType.RFPDS)

    # Get party names for definitions
    employee_name = (
        case_info.plaintiffs[0].name if case_info.plaintiffs else "[EMPLOYEE NAME]"
    )
    employer_name = (
        case_info.defendants[0].name if case_info.defendants else "[EMPLOYER NAME]"
    )

    # Build definitions
    if include_definitions:
        if custom_definitions:
            definitions = custom_definitions
        else:
            definitions = dict(
                standard_definitions(employee_name, employer_name)
            )
    else:
        definitions = {}

    # Format requests based on tool type
    if tool_type == DiscoveryToolType.SROGS:
        formatted_requests = _format_srog_requests(requests)
    elif tool_type == DiscoveryToolType.RFPDS:
        formatted_requests = _format_rfpd_requests(requests)
    else:
        formatted_requests = _format_rfa_requests(requests)

    # Build the document title
    tool_label = TOOL_LABELS[tool_type]
    doc_title = document_title(case_info, tool_label)

    # Build declaration context if needed (CCP 2030.050 / 2033.050)
    declaration = _build_declaration_context(tool_type, case_info, requests)

    # Build template context
    context = {
        # Caption
        "attorney_name": case_info.attorney.name,
        "attorney_sbn": case_info.attorney.sbn,
        "attorney_firm": case_info.attorney.firm_name or "",
        "attorney_address": case_info.attorney.address,
        "attorney_city_state_zip": case_info.attorney.city_state_zip,
        "attorney_phone": case_info.attorney.phone,
        "attorney_fax": case_info.attorney.fax or "",
        "attorney_email": case_info.attorney.email,
        "attorney_for": (
            case_info.attorney.attorney_for
            or propounding_party_name(case_info)
        ),
        "court_county": case_info.court_county,
        "plaintiff_block": plaintiff_block(case_info),
        "defendant_block": defendant_block(case_info),
        "case_number": case_info.case_number,
        # Document title and parties
        "document_title": doc_title,
        "propounding_party": propounding_party_name(case_info),
        "responding_party": responding_party_name(case_info),
        "set_number": set_number_label(case_info.set_number),
        # Content sections
        "definitions": definitions,
        "production_instructions": (
            STANDARD_PRODUCTION_INSTRUCTIONS if include_production_instructions else ""
        ),
        "requests_heading": TOOL_HEADINGS[tool_type],
        "requests": formatted_requests,
        # Signature
        "date": date.today().strftime("%B %d, %Y"),
        # Declaration of Necessity (None if not needed)
        "declaration": declaration,
    }

    # Render the template
    from docxtpl import DocxTemplate

    template_path = _get_or_create_template()
    tpl = DocxTemplate(str(template_path))
    tpl.render(context)

    # Write to bytes
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tpl.save(tmp.name)
        tmp.seek(0)
        return Path(tmp.name).read_bytes()


def build_srogs(
    case_info: CaseInfo,
    requests: list[DiscoveryRequest],
    **kwargs,
) -> bytes:
    """Convenience wrapper for building Special Interrogatories DOCX."""
    return build_discovery_docx(
        DiscoveryToolType.SROGS, case_info, requests, **kwargs
    )


def build_rfpds(
    case_info: CaseInfo,
    requests: list[DiscoveryRequest],
    **kwargs,
) -> bytes:
    """Convenience wrapper for building RFPDs DOCX."""
    return build_discovery_docx(
        DiscoveryToolType.RFPDS, case_info, requests, **kwargs
    )


def build_rfas(
    case_info: CaseInfo,
    requests: list[DiscoveryRequest],
    **kwargs,
) -> bytes:
    """Convenience wrapper for building RFAs DOCX."""
    return build_discovery_docx(
        DiscoveryToolType.RFAS, case_info, requests, **kwargs
    )
