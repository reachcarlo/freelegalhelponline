"""PDF form filler for Judicial Council discovery forms.

Fills DISC-001 (Form Interrogatories — General), DISC-002 (Form
Interrogatories — Employment Law), and DISC-020 (Requests for
Admission cover sheet) using PyPDFForm.

Pure computation — no DB, no ML, no external services.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PyPDFForm import PdfWrapper

from ..case_info import (
    document_title,
    propounding_party_name,
    responding_party_name,
    set_number_label,
)
from ..models import CaseInfo, DiscoveryToolType
from .field_mapping import (
    DISC001_HEADER_FIELDS,
    DISC001_SECTION_FIELDS,
    DISC002_HEADER_FIELDS,
    DISC002_SECTION_FIELDS,
    DISC020_CHECKBOX_FIELDS,
    DISC020_HEADER_FIELDS,
    DISC020_TEXT_FIELDS,
    FieldValue,
)

# ---------------------------------------------------------------------------
# Template directory
# ---------------------------------------------------------------------------

TEMPLATE_DIR = Path(__file__).parent / "templates"


def _template_path(filename: str) -> Path:
    path = TEMPLATE_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Template PDF not found: {path}")
    return path


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _format_date(d: date | None) -> str:
    """Format a date as MM/DD/YYYY for PDF fields, or empty string."""
    if d is None:
        return ""
    return d.strftime("%m/%d/%Y")


def _format_attorney_block(case_info: CaseInfo) -> str:
    """Build the multi-line attorney info block for DISC-002/DISC-020."""
    atty = case_info.attorney
    lines = []
    if atty.is_pro_per:
        lines.append(f"{atty.name}, In Pro Per")
    else:
        lines.append(f"{atty.name} (SBN {atty.sbn})")
        if atty.firm_name:
            lines.append(atty.firm_name)
    lines.append(atty.address)
    lines.append(atty.city_state_zip)
    return "\n".join(lines)


def _build_case_info_fields_disc001(
    case_info: CaseInfo,
) -> dict[str, FieldValue]:
    """Map CaseInfo to DISC-001 header field values."""
    h = DISC001_HEADER_FIELDS
    atty = case_info.attorney
    return {
        h["court_county"]: f"Superior Court of California, County of {case_info.court_county}",
        h["short_title"]: f"{propounding_party_name(case_info)} vs. {responding_party_name(case_info)}",
        h["asking_party"]: propounding_party_name(case_info),
        h["answering_party"]: responding_party_name(case_info),
        h["set_number"]: set_number_label(case_info.set_number),
        h["case_number"]: case_info.case_number,
        h["attorney_name"]: atty.name,
        h["attorney_sbn"]: atty.sbn,
        h["attorney_firm"]: atty.firm_name or "",
        h["attorney_street"]: atty.address,
        h["attorney_city"]: atty.city_state_zip.split(",")[0].strip() if "," in atty.city_state_zip else atty.city_state_zip,
        h["attorney_state"]: "CA",
        h["attorney_zip"]: atty.city_state_zip.split()[-1] if atty.city_state_zip else "",
        h["attorney_phone"]: atty.phone,
        h["attorney_fax"]: atty.fax or "",
        h["attorney_email"]: atty.email,
        h["attorney_for"]: atty.attorney_for or propounding_party_name(case_info),
        h["date"]: _format_date(date.today()),
    }


def _build_case_info_fields_disc002(
    case_info: CaseInfo,
    adverse_actions: list[str] | None = None,
) -> dict[str, FieldValue]:
    """Map CaseInfo to DISC-002 header field values."""
    h = DISC002_HEADER_FIELDS
    return {
        h["attorney_info"]: _format_attorney_block(case_info),
        h["attorney_phone"]: case_info.attorney.phone,
        h["attorney_fax"]: case_info.attorney.fax or "",
        h["attorney_email"]: case_info.attorney.email,
        h["set_number"]: set_number_label(case_info.set_number),
        h["case_number"]: case_info.case_number,
        h["answering_party"]: responding_party_name(case_info),
        h["date"]: _format_date(date.today()),
        h["adverse_actions_list"]: "; ".join(adverse_actions) if adverse_actions else "",
    }


def _build_case_info_fields_disc020(
    case_info: CaseInfo,
) -> dict[str, FieldValue]:
    """Map CaseInfo to DISC-020 header field values."""
    h = DISC020_HEADER_FIELDS
    return {
        h["attorney_info"]: _format_attorney_block(case_info),
        h["attorney_phone"]: case_info.attorney.phone,
        h["attorney_fax"]: case_info.attorney.fax or "",
        h["attorney_email"]: case_info.attorney.email,
        h["attorney_for"]: case_info.attorney.attorney_for or propounding_party_name(case_info),
        h["court_county"]: case_info.court_county,
        h["court_street"]: case_info.court_address or "",
        h["court_mailing"]: "",
        h["court_city_zip"]: case_info.court_city_zip or "",
        h["court_branch"]: case_info.court_branch or "",
        h["case_number"]: case_info.case_number,
        h["short_title"]: f"{propounding_party_name(case_info)} vs. {responding_party_name(case_info)}",
        h["requesting_party"]: propounding_party_name(case_info),
        h["answering_party"]: responding_party_name(case_info),
        h["set_number"]: set_number_label(case_info.set_number),
        h["date"]: _format_date(date.today()),
        h["typed_name"]: case_info.attorney.name,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fill_disc001(
    case_info: CaseInfo,
    selected_sections: list[str],
    *,
    custom_definitions: str | None = None,
) -> bytes:
    """Fill DISC-001 (Form Interrogatories — General) and return PDF bytes.

    Args:
        case_info: Case and attorney information.
        selected_sections: List of section numbers to check
            (e.g. ["1.1", "2.1", "6.1", "6.2"]).
        custom_definitions: Optional custom definition text for
            Section 4(a)(2) INCIDENT definition override.

    Returns:
        Filled PDF as bytes.
    """
    field_data: dict[str, FieldValue] = {}

    # Header fields
    field_data.update(_build_case_info_fields_disc001(case_info))

    # Custom definitions
    if custom_definitions:
        field_data[DISC001_HEADER_FIELDS["custom_definitions"]] = custom_definitions

    # Section checkboxes
    for section in selected_sections:
        field_name = DISC001_SECTION_FIELDS.get(section)
        if field_name:
            field_data[field_name] = True

    # Check the "Definitions" checkbox if any sections are selected
    if selected_sections:
        field_data["Definitions[0]"] = True

    template = _template_path("disc001.pdf")
    wrapper = PdfWrapper(str(template))
    filled = wrapper.fill(field_data)
    return filled.read()


def fill_disc002(
    case_info: CaseInfo,
    selected_sections: list[str],
    *,
    adverse_actions: list[str] | None = None,
) -> bytes:
    """Fill DISC-002 (Form Interrogatories — Employment Law) and return PDF bytes.

    Args:
        case_info: Case and attorney information.
        selected_sections: List of section numbers to check
            (e.g. ["200.1", "201.1", "202.1"]).
        adverse_actions: List of adverse employment actions for
            section 201.3's text field.

    Returns:
        Filled PDF as bytes.
    """
    field_data: dict[str, FieldValue] = {}

    # Header fields
    field_data.update(
        _build_case_info_fields_disc002(case_info, adverse_actions)
    )

    # Section checkboxes
    for section in selected_sections:
        field_name = DISC002_SECTION_FIELDS.get(section)
        if field_name:
            field_data[field_name] = True

    template = _template_path("disc002.pdf")
    wrapper = PdfWrapper(str(template))
    filled = wrapper.fill(field_data)
    return filled.read()


def fill_disc020(
    case_info: CaseInfo,
    *,
    truth_of_facts: bool = True,
    genuineness_of_documents: bool = False,
    facts_text: str = "",
    facts_continued: bool = False,
    docs_text: str = "",
    docs_continued: bool = False,
) -> bytes:
    """Fill DISC-020 (Requests for Admission cover) and return PDF bytes.

    Args:
        case_info: Case and attorney information.
        truth_of_facts: Check the "Truth of Facts" checkbox.
        genuineness_of_documents: Check the "Genuineness of Documents" checkbox.
        facts_text: Text listing facts for admission.
        facts_continued: Whether facts continue on an attachment.
        docs_text: Text listing documents for genuineness.
        docs_continued: Whether documents continue on an attachment.

    Returns:
        Filled PDF as bytes.
    """
    field_data: dict[str, FieldValue] = {}

    # Header fields
    field_data.update(_build_case_info_fields_disc020(case_info))

    # Type checkboxes
    cb = DISC020_CHECKBOX_FIELDS
    if truth_of_facts:
        field_data[cb["truth_of_facts"]] = True
        field_data[cb["facts_listed"]] = True
    if genuineness_of_documents:
        field_data[cb["genuineness_of_documents"]] = True
        field_data[cb["docs_genuine"]] = True
    if facts_continued:
        field_data[cb["facts_continued_attachment"]] = True
    if docs_continued:
        field_data[cb["docs_continued_attachment"]] = True

    # Text content
    txt = DISC020_TEXT_FIELDS
    if facts_text:
        field_data[txt["facts_text"]] = facts_text
    if docs_text:
        field_data[txt["docs_text"]] = docs_text

    template = _template_path("disc020.pdf")
    wrapper = PdfWrapper(str(template))
    filled = wrapper.fill(field_data)
    return filled.read()


def fill_discovery_pdf(
    tool_type: DiscoveryToolType,
    case_info: CaseInfo,
    selected_sections: list[str],
    **kwargs,
) -> bytes:
    """Dispatch to the appropriate form filler based on tool type.

    Args:
        tool_type: Which discovery tool to generate.
        case_info: Case and attorney information.
        selected_sections: Section numbers to check.
        **kwargs: Additional keyword arguments passed to the specific filler.

    Returns:
        Filled PDF as bytes.

    Raises:
        ValueError: If tool_type is not a PDF-based discovery tool.
    """
    if tool_type == DiscoveryToolType.FROGS_GENERAL:
        return fill_disc001(case_info, selected_sections, **kwargs)
    elif tool_type == DiscoveryToolType.FROGS_EMPLOYMENT:
        return fill_disc002(case_info, selected_sections, **kwargs)
    elif tool_type == DiscoveryToolType.RFAS:
        return fill_disc020(case_info, **kwargs)
    else:
        raise ValueError(
            f"Tool type {tool_type.value} does not use PDF output. "
            "Use the DOCX builder for SROGs and RFPDs."
        )
