"""Tests for V2.1c.5: CaseContext name properties verified for ObfuscationEngine compatibility."""

from __future__ import annotations

from employee_help.casefile.context import (
    AttorneyView,
    CaseContext,
    EmploymentPeriodView,
    PartyView,
)
from employee_help.privacy.context import ObfuscationContext


def _build_context() -> CaseContext:
    """Build a CaseContext with a mix of parties, attorneys, and employment."""
    return CaseContext(
        case_id="ctx-obf",
        case_name="Obfuscation Compat",
        parties=[
            PartyView(name="Jane Doe", role="plaintiff", party_type="individual"),
            PartyView(name="John Smith", role="plaintiff", party_type="individual"),
            PartyView(name="Acme Corp", role="defendant", party_type="entity"),
            PartyView(name="Beta LLC", role="defendant", party_type="entity"),
            PartyView(name="Does 1-50", role="defendant", party_type="doe"),
        ],
        attorneys=[
            AttorneyView(name="Lisa Ray", side="plaintiff", firm="Ray & Associates"),
            AttorneyView(name="Mark Chen", side="defendant", firm="Acme Corp"),
        ],
        employment_history=[
            EmploymentPeriodView(employer="Acme Corp", position="Manager"),
            EmploymentPeriodView(employer="Gamma Inc", position="Analyst"),
        ],
    )


class TestAllPersonNamesObfuscationCompat:
    """all_person_names returns list[str] in deterministic order for ObfuscationEngine seeding."""

    def test_person_names_deterministic_order(self):
        """all_person_names includes individual parties + attorneys, stable across calls."""
        ctx = _build_context()
        names = ctx.all_person_names
        assert isinstance(names, list)
        assert all(isinstance(n, str) for n in names)
        # Individual parties first, then attorneys, in insertion order
        assert names == ["Jane Doe", "John Smith", "Lisa Ray", "Mark Chen"]
        # Deterministic: repeated calls return same order
        assert ctx.all_person_names == names

    def test_entity_names_deterministic_order_deduped(self):
        """all_entity_names deduplicates while preserving insertion order."""
        ctx = _build_context()
        names = ctx.all_entity_names
        assert isinstance(names, list)
        assert all(isinstance(n, str) for n in names)
        # Entity parties, then attorney firms, then employers — deduped
        # "Acme Corp" appears as party, attorney firm, and employer — only once
        assert names == ["Acme Corp", "Beta LLC", "Ray & Associates", "Gamma Inc"]
        # Deterministic: repeated calls return same order
        assert ctx.all_entity_names == names

    def test_names_seed_into_obfuscation_context(self):
        """Both name lists can seed an ObfuscationContext without errors."""
        ctx = _build_context()
        obf_ctx = ObfuscationContext()

        for name in ctx.all_person_names:
            obf_ctx.seed("PERSON", name)
        for name in ctx.all_entity_names:
            obf_ctx.seed("COMPANY", name)

        # Verify seeded entities produce placeholders
        text = "Jane Doe worked at Acme Corp with attorney Lisa Ray."
        result = obf_ctx.obfuscate(text)
        assert "Jane Doe" not in result
        assert "Acme Corp" not in result
        assert "Lisa Ray" not in result

        # Deobfuscate round-trips back
        restored = obf_ctx.deobfuscate(result)
        assert "Jane Doe" in restored
        assert "Acme Corp" in restored
        assert "Lisa Ray" in restored
