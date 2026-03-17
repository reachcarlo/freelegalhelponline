"""ExtractionOrchestrator — classifier → extractors → CaseFact pipeline.

Runs DocumentClassifier to determine document type, dispatches to the
appropriate Tier 1 extractors, and converts results into CaseFact objects
ready for storage.
"""

from __future__ import annotations

from employee_help.casefile.classifiers import DocumentClassifier, DocumentType
from employee_help.casefile.extractors.caption import CaptionExtractor
from employee_help.casefile.extractors.dates import DateExtractor
from employee_help.casefile.extractors.employment import EmploymentExtractor
from employee_help.casefile.extractors.financial import FinancialExtractor
from employee_help.storage.models import (
    CaseFact,
    ExtractionMethod,
    FactCategory,
)

# Document types that contain court caption blocks
_CAPTION_DOC_TYPES = frozenset({
    DocumentType.COMPLAINT,
    DocumentType.ANSWER,
    DocumentType.DISCOVERY,
})

# Confidence levels for Tier 1 (regex) extraction
_CAPTION_CONFIDENCE = 0.7
_DATE_CONFIDENCE = 0.65
_FINANCIAL_CONFIDENCE = 0.7
_EMPLOYMENT_CONFIDENCE = 0.65


class ExtractionOrchestrator:
    """Runs classifier → dispatches to extractors → creates CaseFact objects.

    Integrated into the file processing pipeline as a post-extraction hook.
    After text is extracted from a file, this orchestrator:
    1. Classifies the document type
    2. Runs the appropriate Tier 1 extractors
    3. Converts extractor results into CaseFact objects
    """

    def __init__(self) -> None:
        self._classifier = DocumentClassifier()
        self._caption_extractor = CaptionExtractor()
        self._date_extractor = DateExtractor()
        self._financial_extractor = FinancialExtractor()
        self._employment_extractor = EmploymentExtractor()

    def extract_facts(
        self,
        text: str,
        filename: str,
        case_id: str,
        file_id: str,
    ) -> tuple[DocumentType, list[CaseFact]]:
        """Classify document and extract all Tier 1 facts.

        Args:
            text: Extracted text content of the file.
            filename: Original filename (used for classification hints).
            case_id: The case this file belongs to.
            file_id: The file these facts are sourced from.

        Returns:
            Tuple of (document_type, list_of_facts).
            Facts are not yet persisted — caller is responsible for storage.
        """
        if not text or not text.strip():
            return DocumentType.GENERIC, []

        doc_type = self._classifier.classify(text, filename)
        facts: list[CaseFact] = []

        # Caption extraction for court filings
        if doc_type in _CAPTION_DOC_TYPES:
            self._extract_caption_facts(text, case_id, file_id, facts)

        # Date extraction — all document types
        self._extract_date_facts(text, case_id, file_id, facts)

        # Financial extraction — all document types
        self._extract_financial_facts(text, case_id, file_id, facts)

        # Employment extraction — all document types
        self._extract_employment_facts(text, case_id, file_id, facts)

        return doc_type, facts

    def _extract_caption_facts(
        self,
        text: str,
        case_id: str,
        file_id: str,
        facts: list[CaseFact],
    ) -> None:
        """Extract party, court, and attorney facts from caption blocks."""
        result = self._caption_extractor.extract(text)

        # Party facts
        for party in result.parties:
            value: dict = {
                "name": party.name,
                "role": party.role,
                "party_type": party.party_type,
            }
            if party.count is not None:
                value["count"] = party.count
            facts.append(CaseFact(
                case_id=case_id,
                category=FactCategory.PARTY,
                fact_type="party_identified",
                value=value,
                source_file_id=file_id,
                extraction_method=ExtractionMethod.REGEX,
                confidence=_CAPTION_CONFIDENCE,
            ))

        # Court fact (single composite fact)
        if result.court or result.county or result.department or result.judge:
            court_value: dict = {}
            if result.court:
                court_value["court"] = result.court
            if result.county:
                court_value["county"] = result.county
            if result.department:
                court_value["department"] = result.department
            if result.judge:
                court_value["judge"] = result.judge
            if result.case_number:
                court_value["case_number"] = result.case_number
            facts.append(CaseFact(
                case_id=case_id,
                category=FactCategory.COURT,
                fact_type="court_identified",
                value=court_value,
                source_file_id=file_id,
                extraction_method=ExtractionMethod.REGEX,
                confidence=_CAPTION_CONFIDENCE,
            ))

        # Attorney facts
        for atty in result.attorneys:
            atty_value: dict = {"name": atty.name, "side": atty.side}
            if atty.bar_number:
                atty_value["bar_number"] = atty.bar_number
            if atty.firm:
                atty_value["firm"] = atty.firm
            if atty.email:
                atty_value["email"] = atty.email
            facts.append(CaseFact(
                case_id=case_id,
                category=FactCategory.ATTORNEY,
                fact_type="attorney_identified",
                value=atty_value,
                source_file_id=file_id,
                extraction_method=ExtractionMethod.REGEX,
                confidence=_CAPTION_CONFIDENCE,
            ))

    def _extract_date_facts(
        self,
        text: str,
        case_id: str,
        file_id: str,
        facts: list[CaseFact],
    ) -> None:
        """Extract date facts."""
        for dr in self._date_extractor.extract(text):
            facts.append(CaseFact(
                case_id=case_id,
                category=FactCategory.DATE,
                fact_type="date_identified",
                value={
                    "label": dr.label,
                    "date": dr.date,
                    "date_type": dr.date_type,
                },
                source_file_id=file_id,
                extraction_method=ExtractionMethod.REGEX,
                confidence=_DATE_CONFIDENCE,
                effective_date=dr.date,
            ))

    def _extract_financial_facts(
        self,
        text: str,
        case_id: str,
        file_id: str,
        facts: list[CaseFact],
    ) -> None:
        """Extract financial facts."""
        for fr in self._financial_extractor.extract(text):
            facts.append(CaseFact(
                case_id=case_id,
                category=FactCategory.FINANCIAL,
                fact_type="amount_identified",
                value={
                    "label": fr.label,
                    "amount": fr.amount,
                    "amount_type": fr.amount_type,
                },
                source_file_id=file_id,
                extraction_method=ExtractionMethod.REGEX,
                confidence=_FINANCIAL_CONFIDENCE,
            ))

    def _extract_employment_facts(
        self,
        text: str,
        case_id: str,
        file_id: str,
        facts: list[CaseFact],
    ) -> None:
        """Extract employment facts.

        Groups related employment results (employer, position, department,
        compensation) into composite facts where possible. Individual
        results that can't be grouped are stored as standalone facts.
        """
        results = self._employment_extractor.extract(text)

        # Collect by field for grouping
        employers = [r for r in results if r.field == "employer"]
        positions = [r for r in results if r.field == "position"]
        departments = [r for r in results if r.field == "department"]
        compensations = [r for r in results if r.field == "compensation"]

        # Build composite employment fact from first of each
        composite: dict = {}
        if employers:
            composite["employer"] = employers[0].value
        if positions:
            composite["position"] = positions[0].value
        if departments:
            composite["department"] = departments[0].value
        if compensations:
            comp = compensations[0]
            if comp.compensation_rate is not None:
                composite["compensation_rate"] = comp.compensation_rate
            if comp.compensation_type is not None:
                composite["compensation_type"] = comp.compensation_type
            if comp.pay_period is not None:
                composite["pay_period"] = comp.pay_period

        if composite:
            facts.append(CaseFact(
                case_id=case_id,
                category=FactCategory.EMPLOYMENT,
                fact_type="employment_detail",
                value=composite,
                source_file_id=file_id,
                extraction_method=ExtractionMethod.REGEX,
                confidence=_EMPLOYMENT_CONFIDENCE,
            ))

        # Additional employers beyond the first → separate facts
        for emp in employers[1:]:
            facts.append(CaseFact(
                case_id=case_id,
                category=FactCategory.EMPLOYMENT,
                fact_type="employment_detail",
                value={"employer": emp.value},
                source_file_id=file_id,
                extraction_method=ExtractionMethod.REGEX,
                confidence=_EMPLOYMENT_CONFIDENCE,
            ))

        # Additional positions beyond the first
        for pos in positions[1:]:
            facts.append(CaseFact(
                case_id=case_id,
                category=FactCategory.EMPLOYMENT,
                fact_type="employment_detail",
                value={"position": pos.value},
                source_file_id=file_id,
                extraction_method=ExtractionMethod.REGEX,
                confidence=_EMPLOYMENT_CONFIDENCE,
            ))

        # Additional compensations beyond the first
        for comp in compensations[1:]:
            comp_val: dict = {}
            if comp.compensation_rate is not None:
                comp_val["compensation_rate"] = comp.compensation_rate
            if comp.compensation_type is not None:
                comp_val["compensation_type"] = comp.compensation_type
            if comp.pay_period is not None:
                comp_val["pay_period"] = comp.pay_period
            if comp_val:
                facts.append(CaseFact(
                    case_id=case_id,
                    category=FactCategory.EMPLOYMENT,
                    fact_type="employment_detail",
                    value=comp_val,
                    source_file_id=file_id,
                    extraction_method=ExtractionMethod.REGEX,
                    confidence=_EMPLOYMENT_CONFIDENCE,
                ))
