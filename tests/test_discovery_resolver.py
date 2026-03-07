"""Tests for discovery variable resolver (Phase D.1.2).

Covers:
- build_variable_map for both party roles
- resolve_text with known, unknown, and mixed variables
- resolve_request returns new frozen dataclass with resolved text
- Edge cases: empty parties, multiple variables, no variables
"""

from __future__ import annotations

import pytest

from employee_help.discovery.models import (
    AttorneyInfo,
    CaseInfo,
    DiscoveryRequest,
    PartyInfo,
    PartyRole,
)
from employee_help.discovery.resolver import (
    VARIABLE_NAMES,
    build_variable_map,
    resolve_request,
    resolve_text,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _attorney() -> AttorneyInfo:
    return AttorneyInfo(
        name="Test Attorney",
        sbn="123456",
        address="123 Main St",
        city_state_zip="Los Angeles, CA 90001",
        phone="(213) 555-0100",
        email="test@example.com",
    )


def _case_info(role: PartyRole) -> CaseInfo:
    return CaseInfo(
        case_number="24STCV00001",
        court_county="Los Angeles",
        party_role=role,
        plaintiffs=(PartyInfo(name="Jane Doe"),),
        defendants=(PartyInfo(name="Acme Corp", is_entity=True),),
        attorney=_attorney(),
    )


# ---------------------------------------------------------------------------
# build_variable_map
# ---------------------------------------------------------------------------


class TestBuildVariableMap:
    def test_plaintiff_propounding(self):
        vm = build_variable_map(_case_info(PartyRole.PLAINTIFF))
        assert vm["PROPOUNDING_PARTY"] == "Jane Doe"
        assert vm["RESPONDING_PARTY"] == "Acme Corp"
        assert vm["PROPOUNDING_DESIGNATION"] == "Plaintiff"
        assert vm["RESPONDING_DESIGNATION"] == "Defendant"
        assert vm["EMPLOYEE"] == "Jane Doe"
        assert vm["EMPLOYER"] == "Acme Corp"

    def test_defendant_propounding(self):
        vm = build_variable_map(_case_info(PartyRole.DEFENDANT))
        assert vm["PROPOUNDING_PARTY"] == "Acme Corp"
        assert vm["RESPONDING_PARTY"] == "Jane Doe"
        assert vm["PROPOUNDING_DESIGNATION"] == "Defendant"
        assert vm["RESPONDING_DESIGNATION"] == "Plaintiff"
        assert vm["EMPLOYEE"] == "Jane Doe"
        assert vm["EMPLOYER"] == "Acme Corp"

    def test_employee_always_plaintiff(self):
        """EMPLOYEE always resolves to plaintiff name regardless of role."""
        for role in PartyRole:
            vm = build_variable_map(_case_info(role))
            assert vm["EMPLOYEE"] == "Jane Doe"

    def test_employer_always_defendant(self):
        """EMPLOYER always resolves to defendant name regardless of role."""
        for role in PartyRole:
            vm = build_variable_map(_case_info(role))
            assert vm["EMPLOYER"] == "Acme Corp"

    def test_all_six_variables_present(self):
        vm = build_variable_map(_case_info(PartyRole.PLAINTIFF))
        assert set(vm.keys()) == VARIABLE_NAMES

    def test_empty_plaintiffs(self):
        ci = CaseInfo(
            case_number="X",
            court_county="X",
            party_role=PartyRole.PLAINTIFF,
            plaintiffs=(),
            defendants=(PartyInfo(name="D"),),
            attorney=_attorney(),
        )
        vm = build_variable_map(ci)
        assert vm["EMPLOYEE"] == ""
        assert vm["PROPOUNDING_PARTY"] == ""

    def test_empty_defendants(self):
        ci = CaseInfo(
            case_number="X",
            court_county="X",
            party_role=PartyRole.DEFENDANT,
            plaintiffs=(PartyInfo(name="P"),),
            defendants=(),
            attorney=_attorney(),
        )
        vm = build_variable_map(ci)
        assert vm["EMPLOYER"] == ""
        assert vm["PROPOUNDING_PARTY"] == ""

    def test_individual_names(self):
        ci = CaseInfo(
            case_number="X",
            court_county="X",
            party_role=PartyRole.PLAINTIFF,
            plaintiffs=(PartyInfo(name="John Smith"),),
            defendants=(PartyInfo(name="Robert Jones"),),
            attorney=_attorney(),
        )
        vm = build_variable_map(ci)
        assert vm["EMPLOYEE"] == "John Smith"
        assert vm["EMPLOYER"] == "Robert Jones"


# ---------------------------------------------------------------------------
# resolve_text
# ---------------------------------------------------------------------------


class TestResolveText:
    def test_single_variable(self):
        result = resolve_text(
            "State whether {EMPLOYER} provided notice.",
            {"EMPLOYER": "Acme Corp"},
        )
        assert result == "State whether Acme Corp provided notice."

    def test_multiple_variables(self):
        result = resolve_text(
            "{PROPOUNDING_PARTY} requests {RESPONDING_PARTY} to admit.",
            {"PROPOUNDING_PARTY": "Jane Doe", "RESPONDING_PARTY": "Acme Corp"},
        )
        assert result == "Jane Doe requests Acme Corp to admit."

    def test_unknown_variable_passes_through(self):
        result = resolve_text(
            "State {UNKNOWN_VAR} facts.",
            {"EMPLOYER": "Acme Corp"},
        )
        assert result == "State {UNKNOWN_VAR} facts."

    def test_mixed_known_and_unknown(self):
        result = resolve_text(
            "{EMPLOYEE} alleges {CUSTOM_PLACEHOLDER} occurred.",
            {"EMPLOYEE": "Jane Doe"},
        )
        assert result == "Jane Doe alleges {CUSTOM_PLACEHOLDER} occurred."

    def test_no_variables(self):
        result = resolve_text(
            "State all facts supporting each claim.",
            {"EMPLOYEE": "Jane Doe"},
        )
        assert result == "State all facts supporting each claim."

    def test_empty_template(self):
        assert resolve_text("", {"EMPLOYEE": "X"}) == ""

    def test_empty_variables(self):
        result = resolve_text("Hello {EMPLOYEE}", {})
        assert result == "Hello {EMPLOYEE}"

    def test_repeated_variable(self):
        result = resolve_text(
            "{EMPLOYEE} told {EMPLOYEE}'s supervisor.",
            {"EMPLOYEE": "Jane"},
        )
        assert result == "Jane told Jane's supervisor."

    def test_all_six_variables(self):
        variables = {
            "PROPOUNDING_PARTY": "A",
            "RESPONDING_PARTY": "B",
            "PROPOUNDING_DESIGNATION": "C",
            "RESPONDING_DESIGNATION": "D",
            "EMPLOYEE": "E",
            "EMPLOYER": "F",
        }
        template = "{PROPOUNDING_PARTY} {RESPONDING_PARTY} {PROPOUNDING_DESIGNATION} {RESPONDING_DESIGNATION} {EMPLOYEE} {EMPLOYER}"
        assert resolve_text(template, variables) == "A B C D E F"


# ---------------------------------------------------------------------------
# resolve_request
# ---------------------------------------------------------------------------


class TestResolveRequest:
    def test_returns_new_instance(self):
        req = DiscoveryRequest(
            id="test_001",
            text="State whether {EMPLOYER} provided {EMPLOYEE} with a handbook.",
            category="test",
        )
        ci = _case_info(PartyRole.PLAINTIFF)
        resolved = resolve_request(req, ci)

        assert resolved is not req
        assert resolved.text == "State whether Acme Corp provided Jane Doe with a handbook."
        assert resolved.id == "test_001"
        assert resolved.category == "test"

    def test_preserves_all_fields(self):
        req = DiscoveryRequest(
            id="test_002",
            text="{EMPLOYEE} text",
            category="cat",
            is_selected=False,
            is_custom=True,
            order=42,
            notes="some note",
            applicable_roles=("plaintiff",),
            applicable_claims=("wage_theft",),
        )
        resolved = resolve_request(req, _case_info(PartyRole.PLAINTIFF))

        assert resolved.is_selected is False
        assert resolved.is_custom is True
        assert resolved.order == 42
        assert resolved.notes == "some note"
        assert resolved.applicable_roles == ("plaintiff",)
        assert resolved.applicable_claims == ("wage_theft",)

    def test_frozen_dataclass_preserved(self):
        req = DiscoveryRequest(id="x", text="{EMPLOYEE}", category="c")
        resolved = resolve_request(req, _case_info(PartyRole.PLAINTIFF))
        with pytest.raises(AttributeError):
            resolved.text = "mutated"  # type: ignore[misc]

    def test_static_text_unchanged(self):
        """Existing requests with static EMPLOYEE/EMPLOYER text pass through."""
        req = DiscoveryRequest(
            id="existing",
            text="State EMPLOYEE's compensation at each stage of the EMPLOYMENT.",
            category="employment_relationship",
        )
        resolved = resolve_request(req, _case_info(PartyRole.PLAINTIFF))
        assert resolved.text == req.text

    def test_defendant_role_resolution(self):
        req = DiscoveryRequest(
            id="def_001",
            text="{PROPOUNDING_DESIGNATION} requests {RESPONDING_PARTY} to state all facts.",
            category="test",
        )
        resolved = resolve_request(req, _case_info(PartyRole.DEFENDANT))
        assert resolved.text == "Defendant requests Jane Doe to state all facts."
