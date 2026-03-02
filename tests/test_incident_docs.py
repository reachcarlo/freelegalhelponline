"""Unit tests for the incident documentation helper."""

from __future__ import annotations

import pytest

from employee_help.tools.deadlines import ClaimType
from employee_help.tools.incident_docs import (
    COMMON_FIELDS,
    DISCLAIMER,
    INCIDENT_GUIDES,
    DocumentationField,
    EvidenceItem,
    FieldType,
    Importance,
    IncidentType,
    IncidentTypeGuide,
    get_incident_guide,
)


# ── All incident types return guides ─────────────────────────────────


@pytest.mark.parametrize("incident_type", list(IncidentType))
def test_all_incident_types_return_guides(incident_type: IncidentType):
    guide = get_incident_guide(incident_type)
    assert isinstance(guide, IncidentTypeGuide)
    assert guide.incident_type == incident_type


@pytest.mark.parametrize("incident_type", list(IncidentType))
def test_all_incident_types_have_labels(incident_type: IncidentType):
    guide = get_incident_guide(incident_type)
    assert len(guide.label) > 0


# ── Common fields ────────────────────────────────────────────────────


def test_common_fields_count():
    assert len(COMMON_FIELDS) == 8


def test_common_field_names():
    names = [f.name for f in COMMON_FIELDS]
    expected = [
        "incident_date",
        "incident_time",
        "location",
        "witnesses",
        "narrative",
        "quotes",
        "employer_response",
        "impact",
    ]
    assert names == expected


def test_common_field_types():
    field_map = {f.name: f.field_type for f in COMMON_FIELDS}
    assert field_map["incident_date"] == FieldType.date
    assert field_map["incident_time"] == FieldType.time
    assert field_map["location"] == FieldType.text
    assert field_map["witnesses"] == FieldType.textarea
    assert field_map["narrative"] == FieldType.textarea
    assert field_map["quotes"] == FieldType.textarea
    assert field_map["employer_response"] == FieldType.textarea
    assert field_map["impact"] == FieldType.textarea


def test_required_common_fields():
    required = {f.name for f in COMMON_FIELDS if f.required}
    assert required == {"incident_date", "location", "narrative"}


# ── Specific fields per type ─────────────────────────────────────────


@pytest.mark.parametrize("incident_type", list(IncidentType))
def test_all_types_have_at_least_2_specific_fields(incident_type: IncidentType):
    guide = get_incident_guide(incident_type)
    assert len(guide.specific_fields) >= 2, (
        f"{incident_type.value} has only {len(guide.specific_fields)} specific fields"
    )


# ── Prompts ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("incident_type", list(IncidentType))
def test_all_types_have_at_least_3_prompts(incident_type: IncidentType):
    guide = get_incident_guide(incident_type)
    assert len(guide.prompts) >= 3, (
        f"{incident_type.value} has only {len(guide.prompts)} prompts"
    )


# ── Evidence checklist ───────────────────────────────────────────────


@pytest.mark.parametrize("incident_type", list(IncidentType))
def test_all_types_have_at_least_4_evidence_items(incident_type: IncidentType):
    guide = get_incident_guide(incident_type)
    assert len(guide.evidence_checklist) >= 4, (
        f"{incident_type.value} has only {len(guide.evidence_checklist)} evidence items"
    )


@pytest.mark.parametrize("incident_type", list(IncidentType))
def test_all_evidence_items_have_valid_importance(incident_type: IncidentType):
    guide = get_incident_guide(incident_type)
    for item in guide.evidence_checklist:
        assert isinstance(item.importance, Importance)


@pytest.mark.parametrize("incident_type", list(IncidentType))
def test_all_types_have_at_least_1_critical_evidence_item(incident_type: IncidentType):
    guide = get_incident_guide(incident_type)
    critical = [e for e in guide.evidence_checklist if e.importance == Importance.critical]
    assert len(critical) >= 1, (
        f"{incident_type.value} has no critical evidence items"
    )


# ── Key specific fields per type ─────────────────────────────────────


def test_discrimination_has_protected_characteristic():
    guide = get_incident_guide(IncidentType.discrimination)
    names = [f.name for f in guide.specific_fields]
    assert "protected_characteristic" in names


def test_harassment_has_harassment_type():
    guide = get_incident_guide(IncidentType.harassment)
    names = [f.name for f in guide.specific_fields]
    assert "harassment_type" in names


def test_wrongful_termination_has_stated_reason():
    guide = get_incident_guide(IncidentType.wrongful_termination)
    names = [f.name for f in guide.specific_fields]
    assert "stated_reason" in names


def test_unpaid_wages_has_hours_worked():
    guide = get_incident_guide(IncidentType.unpaid_wages)
    names = [f.name for f in guide.specific_fields]
    assert "hours_worked" in names


def test_retaliation_has_protected_activity():
    guide = get_incident_guide(IncidentType.retaliation)
    names = [f.name for f in guide.specific_fields]
    assert "protected_activity" in names


def test_family_medical_leave_has_leave_type():
    guide = get_incident_guide(IncidentType.family_medical_leave)
    names = [f.name for f in guide.specific_fields]
    assert "leave_type" in names


def test_workplace_safety_has_hazard_type():
    guide = get_incident_guide(IncidentType.workplace_safety)
    names = [f.name for f in guide.specific_fields]
    assert "hazard_type" in names


def test_misclassification_has_classification():
    guide = get_incident_guide(IncidentType.misclassification)
    names = [f.name for f in guide.specific_fields]
    assert "classification" in names


def test_meal_rest_breaks_has_break_type():
    guide = get_incident_guide(IncidentType.meal_rest_breaks)
    names = [f.name for f in guide.specific_fields]
    assert "break_type" in names


def test_whistleblower_has_violation_reported():
    guide = get_incident_guide(IncidentType.whistleblower)
    names = [f.name for f in guide.specific_fields]
    assert "violation_reported" in names


# ── Related claim types cross-validation ─────────────────────────────


_VALID_CLAIM_TYPES = {ct.value for ct in ClaimType}


@pytest.mark.parametrize("incident_type", list(IncidentType))
def test_related_claim_types_are_valid(incident_type: IncidentType):
    """related_claim_types values must be valid ClaimType enum values."""
    guide = get_incident_guide(incident_type)
    for claim_type in guide.related_claim_types:
        assert claim_type in _VALID_CLAIM_TYPES, (
            f"{incident_type.value} has invalid related_claim_type: {claim_type}"
        )


# ── Select fields have options ───────────────────────────────────────


@pytest.mark.parametrize("incident_type", list(IncidentType))
def test_select_fields_have_options(incident_type: IncidentType):
    guide = get_incident_guide(incident_type)
    all_fields = list(guide.common_fields) + list(guide.specific_fields)
    for field in all_fields:
        if field.field_type == FieldType.select:
            assert len(field.options) > 0, (
                f"{incident_type.value} field '{field.name}' is a select with no options"
            )


# ── Disclaimer ───────────────────────────────────────────────────────


def test_disclaimer_contains_key_phrases():
    assert "personal record" in DISCLAIMER.lower()
    assert "not" in DISCLAIMER.lower() and "legal" in DISCLAIMER.lower()
    assert "browser" in DISCLAIMER.lower()
    assert "attorney" in DISCLAIMER.lower()


# ── Frozen dataclasses are immutable ─────────────────────────────────


def test_guide_is_frozen():
    guide = get_incident_guide(IncidentType.discrimination)
    with pytest.raises(AttributeError):
        guide.label = "Changed"


def test_field_is_frozen():
    field = COMMON_FIELDS[0]
    with pytest.raises(AttributeError):
        field.name = "changed"


def test_evidence_item_is_frozen():
    guide = get_incident_guide(IncidentType.discrimination)
    item = guide.evidence_checklist[0]
    with pytest.raises(AttributeError):
        item.description = "changed"


# ── No duplicate field names ─────────────────────────────────────────


@pytest.mark.parametrize("incident_type", list(IncidentType))
def test_no_duplicate_field_names(incident_type: IncidentType):
    guide = get_incident_guide(incident_type)
    all_names = [f.name for f in guide.common_fields] + [
        f.name for f in guide.specific_fields
    ]
    assert len(all_names) == len(set(all_names)), (
        f"{incident_type.value} has duplicate field names"
    )
