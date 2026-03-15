"""CaseContext materialized view and *View value objects for LITIGAGENTv2."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PartyView:
    """Projection of a PARTY fact."""

    name: str
    role: str  # "plaintiff", "defendant", etc.
    party_type: str  # "individual", "entity", "doe"
    count: int | None = None  # for doe defendants


@dataclass(frozen=True)
class EmploymentPeriodView:
    """Projection of an EMPLOYMENT fact."""

    employer: str
    position: str | None = None
    department: str | None = None
    compensation_rate: float | None = None
    compensation_type: str | None = None  # "salary", "hourly"
    pay_period: str | None = None  # "annual", "biweekly", etc.
    start_date: str | None = None
    end_date: str | None = None
    change_reason: str | None = None  # "hired", "promoted", "terminated"


@dataclass(frozen=True)
class ClaimView:
    """Projection of a CLAIM fact."""

    claim_type: str  # "feha_discrimination", "wage_theft", etc.
    status: str = "active"  # "active", "dropped", "settled"
    protected_class: str | None = None
    supporting_facts: str | None = None
    reason: str | None = None  # reason for status change


@dataclass(frozen=True)
class DateView:
    """Projection of a DATE fact."""

    label: str  # "Complaint filed", "Trial date", etc.
    date: str  # ISO date string
    date_type: str | None = None  # "filing", "trial", "discovery_cutoff"


@dataclass(frozen=True)
class FinancialView:
    """Projection of a FINANCIAL fact."""

    label: str  # "Initial demand", "Counter-offer", etc.
    amount: float
    date: str | None = None


@dataclass(frozen=True)
class CourtView:
    """Projection of a COURT fact."""

    court: str
    county: str | None = None
    department: str | None = None
    judge: str | None = None


@dataclass(frozen=True)
class AttorneyView:
    """Projection of an ATTORNEY fact."""

    name: str
    side: str  # "plaintiff", "defendant"
    bar_number: str | None = None
    firm: str | None = None
    email: str | None = None


@dataclass(frozen=True)
class CaseContext:
    """Materialized view of the current case state.

    Assembled by CaseContextBuilder from CaseFact rows.
    Read-only. Never persisted. Rebuilt on every access.
    Tools consume this; they never write to it directly.
    """

    case_id: str
    case_name: str

    # Assembled from facts
    parties: list[PartyView] = field(default_factory=list)
    court: CourtView | None = None
    attorneys: list[AttorneyView] = field(default_factory=list)
    employment_history: list[EmploymentPeriodView] = field(default_factory=list)
    claims: list[ClaimView] = field(default_factory=list)
    key_dates: list[DateView] = field(default_factory=list)
    financials: list[FinancialView] = field(default_factory=list)

    # Provenance summary
    fact_count: int = 0
    confirmed_count: int = 0
    extraction_sources: dict[str, list[str]] = field(default_factory=dict)

    # Convenience accessors for the most common tool needs
    @property
    def plaintiff_names(self) -> list[str]:
        """Active plaintiff names, for variable resolution."""
        return [p.name for p in self.parties if p.role == "plaintiff"]

    @property
    def defendant_names(self) -> list[str]:
        """Active defendant names, for variable resolution."""
        return [p.name for p in self.parties if p.role == "defendant"]

    @property
    def active_claims(self) -> list[ClaimView]:
        """Claims with status 'active', for discovery suggestion."""
        return [c for c in self.claims if c.status == "active"]

    @property
    def current_demand(self) -> FinancialView | None:
        """Most recent demand/offer, for demand letter context."""
        demands = [
            f
            for f in self.financials
            if f.label in ("Initial demand", "Revised demand", "Counter-offer")
        ]
        return demands[-1] if demands else None

    @property
    def all_person_names(self) -> list[str]:
        """All known person names, for obfuscation seeding."""
        names = []
        for p in self.parties:
            if p.party_type == "individual":
                names.append(p.name)
        for a in self.attorneys:
            names.append(a.name)
        return names

    @property
    def all_entity_names(self) -> list[str]:
        """All known org/company names, for obfuscation seeding."""
        names = []
        for p in self.parties:
            if p.party_type == "entity":
                names.append(p.name)
        for a in self.attorneys:
            if a.firm:
                names.append(a.firm)
        for e in self.employment_history:
            names.append(e.employer)
        return list(set(names))
