"""API endpoints for discovery document generation.

Provides endpoints for:
- Suggesting discovery items based on claim types and party role
- Generating filled PDF/DOCX discovery documents
- Retrieving request banks (SROGs, RFPDs, RFAs) with optional role filtering
- Retrieving standard legal definitions
"""

from __future__ import annotations

import io
import re
import time
import uuid

import structlog
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from employee_help.api.schemas import (
    DiscoveryBankCategoryInfo,
    DiscoveryBankItemInfo,
    DiscoveryBankResponse,
    DiscoveryDefinitionInfo,
    DiscoveryDefinitionsResponse,
    DiscoveryGenerateRequest,
    DiscoverySuggestRequest,
    DiscoverySuggestResponse,
    POSGenerateRequest,
    SuggestedCategoryInfo,
    SuggestedSectionInfo,
)

logger = structlog.get_logger(__name__)

discovery_router = APIRouter(prefix="/api/discovery")

# ---------------------------------------------------------------------------
# Content types for file responses
# ---------------------------------------------------------------------------

_PDF_CONTENT_TYPE = "application/pdf"
_DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

# Allowed chars in filenames (strip anything suspicious)
_SAFE_FILENAME_RE = re.compile(r"[^a-zA-Z0-9_\-.]")


def _safe_filename(raw: str) -> str:
    """Sanitize a string for use in Content-Disposition filenames."""
    return _SAFE_FILENAME_RE.sub("_", raw)[:100]


# ---------------------------------------------------------------------------
# Helper: convert API schema to domain models
# ---------------------------------------------------------------------------


def _to_case_info(schema):
    """Convert CaseInfoSchema to discovery.models.CaseInfo."""
    from employee_help.discovery.models import (
        AttorneyInfo,
        CaseInfo,
        PartyInfo,
        PartyRole,
    )

    return CaseInfo(
        case_number=schema.case_number,
        court_county=schema.court_county,
        party_role=PartyRole(schema.party_role),
        plaintiffs=tuple(
            PartyInfo(
                name=p.name,
                is_entity=p.is_entity,
                entity_type=p.entity_type,
            )
            for p in schema.plaintiffs
        ),
        defendants=tuple(
            PartyInfo(
                name=d.name,
                is_entity=d.is_entity,
                entity_type=d.entity_type,
            )
            for d in schema.defendants
        ),
        attorney=AttorneyInfo(
            name=schema.attorney.name,
            sbn=schema.attorney.sbn,
            address=schema.attorney.address,
            city_state_zip=schema.attorney.city_state_zip,
            phone=schema.attorney.phone,
            email=schema.attorney.email,
            firm_name=schema.attorney.firm_name,
            fax=schema.attorney.fax,
            is_pro_per=schema.attorney.is_pro_per,
            attorney_for=schema.attorney.attorney_for,
        ),
        court_name=schema.court_name,
        court_branch=schema.court_branch,
        court_address=schema.court_address,
        court_city_zip=schema.court_city_zip,
        judge_name=schema.judge_name,
        department=schema.department,
        complaint_filed_date=schema.complaint_filed_date,
        trial_date=schema.trial_date,
        does_included=schema.does_included,
        set_number=schema.set_number,
    )


def _to_discovery_requests(schemas):
    """Convert list of DiscoveryRequestSchema to domain DiscoveryRequest list."""
    from employee_help.discovery.models import DiscoveryRequest

    return [
        DiscoveryRequest(
            id=s.id,
            text=s.text,
            category=s.category,
            is_selected=s.is_selected,
            is_custom=s.is_custom,
            order=s.order,
            notes=s.notes,
        )
        for s in schemas
        if s.is_selected
    ]


def _parse_party_role(value: str | None):
    """Parse an optional party_role string into a PartyRole enum or None."""
    if value is None:
        return None
    from employee_help.discovery.models import PartyRole

    try:
        return PartyRole(value)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid party_role: {value!r}. Must be 'plaintiff' or 'defendant'.",
        )


def _default_variable_map(party_role) -> dict[str, str]:
    """Build a default variable map when no case info is available.

    Uses definition-style defaults: EMPLOYEE, EMPLOYER, Plaintiff, Defendant.
    """
    from employee_help.discovery.models import PartyRole

    if party_role == PartyRole.PLAINTIFF:
        return {
            "PROPOUNDING_PARTY": "Plaintiff",
            "RESPONDING_PARTY": "Defendant",
            "PROPOUNDING_DESIGNATION": "Plaintiff",
            "RESPONDING_DESIGNATION": "Defendant",
            "EMPLOYEE": "EMPLOYEE",
            "EMPLOYER": "EMPLOYER",
        }
    else:
        return {
            "PROPOUNDING_PARTY": "Defendant",
            "RESPONDING_PARTY": "Plaintiff",
            "PROPOUNDING_DESIGNATION": "Defendant",
            "RESPONDING_DESIGNATION": "Plaintiff",
            "EMPLOYEE": "EMPLOYEE",
            "EMPLOYER": "EMPLOYER",
        }


def _resolve_bank_item_text(text: str, variables: dict[str, str]) -> str:
    """Resolve template variables in bank item text."""
    from employee_help.discovery.resolver import resolve_text

    return resolve_text(text, variables)


def _filter_and_build_bank(bank, categories_dict, party_role, tool: str):
    """Filter a bank by role and build the API response components.

    Returns (items, categories, filtered_bank) where filtered_bank is
    the list of DiscoveryRequest objects after filtering.
    """
    from employee_help.discovery.filters import filter_by_role

    if party_role is not None:
        filtered = filter_by_role(list(bank), party_role)
        variables = _default_variable_map(party_role)
    else:
        filtered = list(bank)
        variables = None

    # Build items
    items = []
    for r in filtered:
        text = _resolve_bank_item_text(r.text, variables) if variables else r.text
        item_kwargs = {
            "id": r.id,
            "text": text,
            "category": r.category,
            "order": r.order,
            "applicable_roles": list(r.applicable_roles),
            "applicable_claims": list(r.applicable_claims) if r.applicable_claims else None,
        }
        if hasattr(r, "rfa_type"):
            item_kwargs["rfa_type"] = r.rfa_type
        items.append(DiscoveryBankItemInfo(**item_kwargs))

    # Build categories, omitting empty ones after filtering
    filtered_cats = {r.category for r in filtered}
    categories = [
        DiscoveryBankCategoryInfo(
            key=k,
            label=v,
            count=sum(1 for r in filtered if r.category == k),
        )
        for k, v in categories_dict.items()
        if k in filtered_cats
    ]

    return items, categories


# ---------------------------------------------------------------------------
# POST /api/discovery/suggest
# ---------------------------------------------------------------------------


@discovery_router.post("/suggest", response_model=DiscoverySuggestResponse)
async def suggest_discovery(request: DiscoverySuggestRequest):
    """Suggest discovery items based on claim types and party role."""
    from employee_help.discovery.filters import filter_by_claims, filter_by_role
    from employee_help.discovery.models import ClaimType, PartyRole

    claim_types = [ClaimType(ct) for ct in request.claim_types]
    party_role = PartyRole(request.party_role)
    tool = request.tool_type

    if tool == "frogs_general":
        from employee_help.discovery.frogs_general import (
            DISC001_SECTIONS,
            suggest_disc001_sections,
        )

        sections = suggest_disc001_sections(
            claim_types,
            party_role,
            has_rfas=request.has_rfas,
            responding_is_entity=request.responding_is_entity,
        )
        # Build section info with titles
        section_infos = []
        for s in sections:
            # Find the parent group
            group_num = s.split(".")[0]
            group = DISC001_SECTIONS.get(group_num)
            section_infos.append(SuggestedSectionInfo(
                section_number=s,
                title=group.title if group else "",
                description=group.description if group else "",
            ))
        return DiscoverySuggestResponse(
            tool_type=tool,
            party_role=request.party_role,
            suggested_sections=section_infos,
            total_suggested=len(sections),
        )

    elif tool == "frogs_employment":
        from employee_help.discovery.frogs_employment import (
            DISC002_SECTIONS,
            suggest_disc002_sections,
        )

        sections = suggest_disc002_sections(
            claim_types,
            party_role,
            has_rfas=request.has_rfas,
        )
        section_infos = []
        for s in sections:
            group_num = s.split(".")[0]
            group = DISC002_SECTIONS.get(group_num)
            section_infos.append(SuggestedSectionInfo(
                section_number=s,
                title=group.title if group else "",
                description=group.description if group else "",
            ))
        return DiscoverySuggestResponse(
            tool_type=tool,
            party_role=request.party_role,
            suggested_sections=section_infos,
            total_suggested=len(sections),
        )

    elif tool == "srogs":
        from employee_help.discovery.claim_mapping import get_suggestions_for_claims
        from employee_help.discovery.srogs import SROG_CATEGORIES, get_srogs_for_categories

        merged = get_suggestions_for_claims(claim_types)
        categories = merged.categories_for_role("srogs", party_role)
        items = get_srogs_for_categories(categories)
        items = filter_by_role(items, party_role)
        items = filter_by_claims(items, tuple(claim_types))
        cat_infos = [
            SuggestedCategoryInfo(
                category=cat,
                label=SROG_CATEGORIES.get(cat, cat),
                request_count=sum(1 for r in items if r.category == cat),
            )
            for cat in categories
            if any(r.category == cat for r in items)
        ]
        return DiscoverySuggestResponse(
            tool_type=tool,
            party_role=request.party_role,
            suggested_categories=cat_infos,
            total_suggested=len(items),
        )

    elif tool == "rfpds":
        from employee_help.discovery.claim_mapping import get_suggestions_for_claims
        from employee_help.discovery.rfpds import RFPD_CATEGORIES, get_rfpds_for_categories

        merged = get_suggestions_for_claims(claim_types)
        categories = merged.categories_for_role("rfpds", party_role)
        items = get_rfpds_for_categories(categories)
        items = filter_by_role(items, party_role)
        items = filter_by_claims(items, tuple(claim_types))
        cat_infos = [
            SuggestedCategoryInfo(
                category=cat,
                label=RFPD_CATEGORIES.get(cat, cat),
                request_count=sum(1 for r in items if r.category == cat),
            )
            for cat in categories
            if any(r.category == cat for r in items)
        ]
        return DiscoverySuggestResponse(
            tool_type=tool,
            party_role=request.party_role,
            suggested_categories=cat_infos,
            total_suggested=len(items),
        )

    else:  # rfas
        from employee_help.discovery.claim_mapping import get_suggestions_for_claims
        from employee_help.discovery.rfas import RFA_CATEGORIES, get_rfas_for_categories

        merged = get_suggestions_for_claims(claim_types)
        categories = merged.categories_for_role("rfas", party_role)
        items = get_rfas_for_categories(categories)
        items = filter_by_role(items, party_role)
        items = filter_by_claims(items, tuple(claim_types))
        cat_infos = [
            SuggestedCategoryInfo(
                category=cat,
                label=RFA_CATEGORIES.get(cat, cat),
                request_count=sum(1 for r in items if r.category == cat),
            )
            for cat in categories
            if any(r.category == cat for r in items)
        ]
        return DiscoverySuggestResponse(
            tool_type=tool,
            party_role=request.party_role,
            suggested_categories=cat_infos,
            total_suggested=len(items),
        )


# ---------------------------------------------------------------------------
# POST /api/discovery/generate
# ---------------------------------------------------------------------------


@discovery_router.post("/generate")
async def generate_discovery(request: DiscoveryGenerateRequest):
    """Generate a discovery document and return it as a file download."""
    start = time.monotonic()
    generation_id = str(uuid.uuid4())

    case_info = _to_case_info(request.case_info)
    tool = request.tool_type
    case_num = _safe_filename(request.case_info.case_number)

    try:
        if tool in ("frogs_general", "frogs_employment"):
            from employee_help.discovery.generator.pdf_filler import fill_discovery_pdf
            from employee_help.discovery.models import DiscoveryToolType

            tool_enum = DiscoveryToolType(tool)
            kwargs = {}
            if tool == "frogs_employment" and request.adverse_actions:
                kwargs["adverse_actions"] = request.adverse_actions
            if tool == "frogs_general" and request.custom_definitions:
                # DISC-001 custom_definitions is a plain string
                kwargs["custom_definitions"] = "\n".join(
                    f"{k}: {v}" for k, v in request.custom_definitions.items()
                )

            file_bytes = fill_discovery_pdf(
                tool_enum,
                case_info,
                request.selected_sections,
                **kwargs,
            )
            content_type = _PDF_CONTENT_TYPE
            ext = "pdf"
            form_name = "DISC-001" if tool == "frogs_general" else "DISC-002"
            filename = f"{form_name}_{case_num}.{ext}"

        elif tool in ("srogs", "rfpds", "rfas"):
            from employee_help.discovery.generator.docx_builder import (
                build_discovery_docx,
            )
            from employee_help.discovery.models import DiscoveryToolType

            tool_enum = DiscoveryToolType(tool)
            requests = _to_discovery_requests(request.selected_requests)

            if not requests:
                raise HTTPException(
                    status_code=422,
                    detail="No selected requests to generate.",
                )

            file_bytes = build_discovery_docx(
                tool_enum,
                case_info,
                requests,
                include_definitions=request.include_definitions,
                custom_definitions=request.custom_definitions,
            )
            content_type = _DOCX_CONTENT_TYPE
            ext = "docx"
            tool_labels = {
                "srogs": "SROGs",
                "rfpds": "RFPDs",
                "rfas": "RFAs",
            }
            filename = f"{tool_labels[tool]}_{case_num}.{ext}"

        else:
            raise HTTPException(status_code=422, detail=f"Unknown tool_type: {tool}")

        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "discovery_generated",
            generation_id=generation_id,
            tool_type=tool,
            file_size=len(file_bytes),
            duration_ms=duration_ms,
        )

        return StreamingResponse(
            io.BytesIO(file_bytes),
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(file_bytes)),
                "X-Generation-Id": generation_id,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.error(
            "discovery_generation_failed",
            generation_id=generation_id,
            tool_type=tool,
            error=str(e),
            duration_ms=duration_ms,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


# ---------------------------------------------------------------------------
# POST /api/discovery/generate-pos
# ---------------------------------------------------------------------------


@discovery_router.post("/generate-pos")
async def generate_proof_of_service(request: POSGenerateRequest):
    """Generate a Proof of Service DOCX and return it as a file download."""
    start = time.monotonic()
    generation_id = str(uuid.uuid4())

    case_info = _to_case_info(request.case_info)
    case_num = _safe_filename(request.case_info.case_number)

    try:
        from employee_help.discovery.generator.pos_builder import (
            build_proof_of_service,
        )
        from employee_help.discovery.models import ServiceMethod

        file_bytes = build_proof_of_service(
            case_info,
            server_name=request.server_name,
            server_address=request.server_address,
            served_party_name=request.served_party_name,
            served_party_address=request.served_party_address,
            service_method=ServiceMethod(request.service_method),
            service_date=request.service_date,
            documents_served=list(request.documents_served),
        )

        filename = f"POS_{case_num}.docx"
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "pos_generated",
            generation_id=generation_id,
            file_size=len(file_bytes),
            duration_ms=duration_ms,
        )

        return StreamingResponse(
            io.BytesIO(file_bytes),
            media_type=_DOCX_CONTENT_TYPE,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(file_bytes)),
                "X-Generation-Id": generation_id,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.error(
            "pos_generation_failed",
            generation_id=generation_id,
            error=str(e),
            duration_ms=duration_ms,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


# ---------------------------------------------------------------------------
# GET /api/discovery/banks/{tool}
# ---------------------------------------------------------------------------


@discovery_router.get("/banks/{tool}", response_model=DiscoveryBankResponse)
async def get_discovery_bank(tool: str, party_role: str | None = None):
    """Return the request bank for a discovery tool.

    When party_role is provided, filters to role-appropriate items
    and resolves template variables with default labels.
    When omitted, returns the full bank (backwards compatible).
    """
    role = _parse_party_role(party_role)

    if tool == "frogs_general":
        from employee_help.discovery.frogs_general import DISC001_SECTIONS

        items = []
        categories = []
        for group in DISC001_SECTIONS.values():
            categories.append(DiscoveryBankCategoryInfo(
                key=group.number,
                label=group.title,
                count=len(group.subsections),
            ))
            for sub in group.subsections:
                items.append(DiscoveryBankItemInfo(
                    id=sub,
                    text=group.description,
                    category=group.number,
                    order=0,
                ))
        return DiscoveryBankResponse(
            tool_type=tool,
            categories=categories,
            items=items,
            total_items=len(items),
        )

    elif tool == "frogs_employment":
        from employee_help.discovery.frogs_employment import DISC002_SECTIONS

        items = []
        categories = []
        for group in DISC002_SECTIONS.values():
            categories.append(DiscoveryBankCategoryInfo(
                key=group.number,
                label=group.title,
                count=len(group.subsections),
            ))
            for sub in group.subsections:
                items.append(DiscoveryBankItemInfo(
                    id=sub,
                    text=group.description,
                    category=group.number,
                    order=0,
                ))
        return DiscoveryBankResponse(
            tool_type=tool,
            categories=categories,
            items=items,
            total_items=len(items),
        )

    elif tool == "srogs":
        from employee_help.discovery.models import SROG_LIMIT
        from employee_help.discovery.srogs import SROG_BANK, SROG_CATEGORIES

        items, categories = _filter_and_build_bank(
            SROG_BANK, SROG_CATEGORIES, role, tool,
        )
        return DiscoveryBankResponse(
            tool_type=tool,
            categories=categories,
            items=items,
            total_items=len(items),
            limit=SROG_LIMIT,
        )

    elif tool == "rfpds":
        from employee_help.discovery.rfpds import RFPD_BANK, RFPD_CATEGORIES

        items, categories = _filter_and_build_bank(
            RFPD_BANK, RFPD_CATEGORIES, role, tool,
        )
        return DiscoveryBankResponse(
            tool_type=tool,
            categories=categories,
            items=items,
            total_items=len(items),
        )

    elif tool == "rfas":
        from employee_help.discovery.models import RFA_FACT_LIMIT
        from employee_help.discovery.rfas import RFA_BANK, RFA_CATEGORIES

        items, categories = _filter_and_build_bank(
            RFA_BANK, RFA_CATEGORIES, role, tool,
        )
        return DiscoveryBankResponse(
            tool_type=tool,
            categories=categories,
            items=items,
            total_items=len(items),
            limit=RFA_FACT_LIMIT,
        )

    else:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown tool: {tool!r}. Valid: frogs_general, frogs_employment, srogs, rfpds, rfas",
        )


# ---------------------------------------------------------------------------
# GET /api/discovery/definitions
# ---------------------------------------------------------------------------


@discovery_router.get("/definitions", response_model=DiscoveryDefinitionsResponse)
async def get_definitions():
    """Return standard legal definitions and production instructions."""
    from employee_help.discovery.definitions import (
        DEFAULT_DEFINITIONS,
        STANDARD_PRODUCTION_INSTRUCTIONS,
    )

    return DiscoveryDefinitionsResponse(
        definitions=[
            DiscoveryDefinitionInfo(term=term, definition=defn)
            for term, defn in DEFAULT_DEFINITIONS.items()
        ],
        production_instructions=STANDARD_PRODUCTION_INSTRUCTIONS,
    )
