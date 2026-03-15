"""CaseContextBuilder — assembles CaseContext from CaseFact rows."""

from __future__ import annotations

from employee_help.casefile.context import (
    AttorneyView,
    CaseContext,
    ClaimView,
    CourtView,
    DateView,
    EmploymentPeriodView,
    FinancialView,
    PartyView,
)
from employee_help.storage.case_fact_storage import CaseFactStorage
from employee_help.storage.models import CaseFact, FactCategory


def _fact_sort_key(fact: CaseFact) -> tuple[int, float, str]:
    """Sort key: confirmed DESC, confidence DESC, created_at DESC."""
    return (
        -(1 if fact.confirmed else 0),
        -fact.confidence,
        fact.created_at.isoformat(),
    )


def _best_fact(facts: list[CaseFact]) -> CaseFact:
    """Pick the winning fact: confirmed > unconfirmed > highest confidence > most recent."""
    return sorted(facts, key=_fact_sort_key)[0]


class CaseContextBuilder:
    """Assembles CaseContext from CaseFact rows.

    Resolution strategy when multiple facts exist for the same field:
    1. Only current facts (superseded_by IS NULL)
    2. Confirmed facts beat unconfirmed, regardless of confidence score
    3. Among same confirmation status, highest confidence wins
    4. Among same confidence, most recent created_at wins

    Employment and financial facts are NOT deduplicated — they accumulate
    as a history. Only facts like "court" that represent a single current
    value go through the resolution strategy.
    """

    def build(
        self,
        case_id: str,
        case_name: str,
        storage: CaseFactStorage,
    ) -> CaseContext:
        """Build a CaseContext from current facts in storage."""
        facts = storage.list_current_facts(case_id)
        by_cat: dict[FactCategory, list[CaseFact]] = {}
        for f in facts:
            by_cat.setdefault(f.category, []).append(f)

        return CaseContext(
            case_id=case_id,
            case_name=case_name,
            parties=self._build_parties(by_cat.get(FactCategory.PARTY, [])),
            court=self._build_court(by_cat.get(FactCategory.COURT, [])),
            attorneys=self._build_attorneys(by_cat.get(FactCategory.ATTORNEY, [])),
            employment_history=self._build_employment(
                by_cat.get(FactCategory.EMPLOYMENT, [])
            ),
            claims=self._build_claims(by_cat.get(FactCategory.CLAIM, [])),
            key_dates=self._build_dates(by_cat.get(FactCategory.DATE, [])),
            financials=self._build_financials(
                by_cat.get(FactCategory.FINANCIAL, [])
            ),
            fact_count=len(facts),
            confirmed_count=sum(1 for f in facts if f.confirmed),
            extraction_sources=self._build_sources(facts),
        )

    # ── Category builders ──────────────────────────────────────

    @staticmethod
    def _build_parties(facts: list[CaseFact]) -> list[PartyView]:
        """All party facts become PartyViews (accumulate, not deduplicated)."""
        return [
            PartyView(
                name=f.value["name"],
                role=f.value["role"],
                party_type=f.value["party_type"],
                count=f.value.get("count"),
            )
            for f in facts
        ]

    @staticmethod
    def _build_court(facts: list[CaseFact]) -> CourtView | None:
        """Single-value: pick the best court fact via resolution strategy."""
        if not facts:
            return None
        best = _best_fact(facts)
        return CourtView(
            court=best.value["court"],
            county=best.value.get("county"),
            department=best.value.get("department"),
            judge=best.value.get("judge"),
        )

    @staticmethod
    def _build_attorneys(facts: list[CaseFact]) -> list[AttorneyView]:
        """All attorney facts become AttorneyViews."""
        return [
            AttorneyView(
                name=f.value["name"],
                side=f.value["side"],
                bar_number=f.value.get("bar_number"),
                firm=f.value.get("firm"),
                email=f.value.get("email"),
            )
            for f in facts
        ]

    @staticmethod
    def _build_employment(facts: list[CaseFact]) -> list[EmploymentPeriodView]:
        """Employment facts accumulate as ordered history (by start_date)."""
        views = [
            EmploymentPeriodView(
                employer=f.value["employer"],
                position=f.value.get("position"),
                department=f.value.get("department"),
                compensation_rate=f.value.get("compensation_rate"),
                compensation_type=f.value.get("compensation_type"),
                pay_period=f.value.get("pay_period"),
                start_date=f.value.get("start_date"),
                end_date=f.value.get("end_date"),
                change_reason=f.value.get("change_reason"),
            )
            for f in facts
        ]
        return sorted(views, key=lambda v: v.start_date or "")

    @staticmethod
    def _build_claims(facts: list[CaseFact]) -> list[ClaimView]:
        """All claim facts become ClaimViews."""
        return [
            ClaimView(
                claim_type=f.value["claim_type"],
                status=f.value.get("status", "active"),
                protected_class=f.value.get("protected_class"),
                supporting_facts=f.value.get("supporting_facts"),
                reason=f.value.get("reason"),
            )
            for f in facts
        ]

    @staticmethod
    def _build_dates(facts: list[CaseFact]) -> list[DateView]:
        """Date facts accumulate, ordered chronologically by date."""
        views = [
            DateView(
                label=f.value["label"],
                date=f.value["date"],
                date_type=f.value.get("date_type"),
            )
            for f in facts
        ]
        return sorted(views, key=lambda v: v.date)

    @staticmethod
    def _build_financials(facts: list[CaseFact]) -> list[FinancialView]:
        """Financial facts accumulate, ordered chronologically by date."""
        views = [
            FinancialView(
                label=f.value["label"],
                amount=f.value["amount"],
                date=f.value.get("date"),
            )
            for f in facts
        ]
        return sorted(views, key=lambda v: v.date or "")

    @staticmethod
    def _build_sources(facts: list[CaseFact]) -> dict[str, list[str]]:
        """Build category → [source_file_ids] mapping."""
        sources: dict[str, list[str]] = {}
        for f in facts:
            if f.source_file_id:
                cat = f.category.value
                if cat not in sources:
                    sources[cat] = []
                if f.source_file_id not in sources[cat]:
                    sources[cat].append(f.source_file_id)
        return sources
