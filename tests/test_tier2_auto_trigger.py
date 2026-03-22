"""Tests for Tier 2 auto-trigger in process_file pipeline (V2.2c.4).

Verifies that Tier 2 LLM extraction runs automatically when a file is
classified as complaint/answer/demand_letter, and that it doesn't run
for other document types or when llm_client is None.
"""

from __future__ import annotations

import asyncio
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from employee_help.casefile.processing import process_file
from employee_help.storage.case_storage import CaseStorage
from employee_help.storage.models import (
    Case,
    CaseFact,
    CaseFile,
    ExtractionMethod,
    FactCategory,
    FileType,
    ProcessingStatus,
)
from employee_help.storage.storage import Storage


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def tmp_dir(tmp_path):
    return tmp_path


@pytest.fixture
def storage(tmp_dir) -> Storage:
    db_path = tmp_dir / "test.db"
    s = Storage(db_path=db_path)
    yield s
    s.close()


@pytest.fixture
def case_storage(storage: Storage) -> CaseStorage:
    return CaseStorage(conn=storage._conn)


@pytest.fixture
def fact_storage(storage: Storage):
    from employee_help.storage.case_fact_storage import CaseFactStorage

    return CaseFactStorage(conn=storage._conn)


@pytest.fixture
def sample_case(case_storage) -> Case:
    return case_storage.create_case(
        Case(name="Auto-Trigger Test", user_id="u1", organization_id="o1")
    )


def _write_complaint_file(case_storage, sample_case, tmp_dir, filename="complaint.pdf") -> CaseFile:
    """Create a PDF file on disk and register it in the DB."""
    file_path = tmp_dir / filename
    # Write a minimal PDF-like file so the PDFExtractor will be resolved
    # We'll mock the extractor anyway, but the file must exist on disk
    file_path.write_bytes(b"fake file content")

    cf = CaseFile(
        case_id=sample_case.id,
        original_filename=filename,
        file_type=FileType.PDF,
        mime_type="application/pdf",
        file_size_bytes=len(b"fake file content"),
        storage_path=str(file_path),
        upload_order=0,
        processing_status=ProcessingStatus.QUEUED,
    )
    return case_storage.create_case_file(cf)


def _mock_tier2_facts(case_id: str, file_id: str) -> list[CaseFact]:
    """Build mock Tier 2 facts."""
    return [
        CaseFact(
            case_id=case_id,
            category=FactCategory.CLAIM,
            fact_type="claim",
            value={"claim_type": "feha_discrimination", "status": "active", "protected_class": "age"},
            source_file_id=file_id,
            extraction_method=ExtractionMethod.LLM,
            confidence=0.92,
        ),
        CaseFact(
            case_id=case_id,
            category=FactCategory.EMPLOYMENT,
            fact_type="employment_period",
            value={"employer": "Acme Corp", "position": "Engineer"},
            source_file_id=file_id,
            extraction_method=ExtractionMethod.LLM,
            confidence=0.80,
        ),
    ]


# ── Tests ──────────────────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="function")
class TestTier2AutoTrigger:
    async def test_tier2_runs_automatically_for_complaint(
        self, case_storage, fact_storage, sample_case, tmp_dir,
    ):
        """When a file is classified as a complaint and llm_client is provided,
        Tier 2 extraction runs automatically after Tier 1."""
        cf = _write_complaint_file(case_storage, sample_case, tmp_dir)
        mock_llm = MagicMock()

        complaint_text = (
            "COMPLAINT FOR DAMAGES\n\n"
            "SUPERIOR COURT OF CALIFORNIA, COUNTY OF LOS ANGELES\n\n"
            "FIRST CAUSE OF ACTION — FEHA Discrimination\n"
            "Plaintiff alleges age-based discrimination."
        )

        # Mock the file extractor to return complaint text
        mock_extraction_result = MagicMock()
        mock_extraction_result.text = complaint_text
        mock_extraction_result.page_count = 3
        mock_extraction_result.ocr_confidence = None
        mock_extraction_result.warnings = []
        mock_extraction_result.metadata = {}

        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = mock_extraction_result

        mock_registry = MagicMock()
        mock_registry.get_extractor.return_value = mock_extractor

        # Mock Tier2Extractor
        tier2_facts = _mock_tier2_facts(sample_case.id, cf.id)

        from employee_help.casefile.extractors.tier2 import Tier2Result

        mock_tier2_result = Tier2Result(
            facts=tier2_facts,
            factual_summary="Age discrimination complaint.",
            input_tokens=1000,
            output_tokens=300,
        )

        with (
            patch("employee_help.casefile.processing.get_registry", return_value=mock_registry),
            patch(
                "employee_help.casefile.extractors.tier2.Tier2Extractor"
            ) as MockTier2Class,
        ):
            mock_tier2_instance = MockTier2Class.return_value
            mock_tier2_instance.extract.return_value = mock_tier2_result

            await process_file(
                case_storage, cf.id, sample_case.id,
                case_fact_storage=fact_storage,
                llm_client=mock_llm,
            )

        # Verify Tier2Extractor was constructed with the llm_client
        MockTier2Class.assert_called_once_with(
            mock_llm, obfuscation_engine=None,
        )

        # Verify Tier2Extractor.extract was called
        mock_tier2_instance.extract.assert_called_once()
        call_args = mock_tier2_instance.extract.call_args
        assert call_args[0][0] == complaint_text  # text
        assert call_args[0][1] == sample_case.id  # case_id
        assert call_args[0][2] == cf.id  # file_id

        # Verify Tier 2 facts were persisted
        all_facts = fact_storage.list_current_facts(sample_case.id)
        llm_facts = [f for f in all_facts if f.extraction_method == ExtractionMethod.LLM]
        assert len(llm_facts) == 2

        # File should be READY
        updated = case_storage.get_case_file(cf.id)
        assert updated.processing_status == ProcessingStatus.READY

    async def test_tier2_skipped_for_email(
        self, case_storage, fact_storage, sample_case, tmp_dir,
    ):
        """Tier 2 does NOT run for email documents (not in TIER2_DOC_TYPES)."""
        file_path = tmp_dir / "message.eml"
        email_text = "From: alice@corp.com\nTo: bob@corp.com\nSubject: Meeting\nDate: 2025-01-01\n\nHello!"
        file_path.write_bytes(email_text.encode())

        cf = CaseFile(
            case_id=sample_case.id,
            original_filename="message.eml",
            file_type=FileType.EML,
            mime_type="message/rfc822",
            file_size_bytes=len(email_text),
            storage_path=str(file_path),
            upload_order=0,
            processing_status=ProcessingStatus.QUEUED,
        )
        cf = case_storage.create_case_file(cf)

        mock_llm = MagicMock()

        mock_extraction_result = MagicMock()
        mock_extraction_result.text = email_text
        mock_extraction_result.page_count = None
        mock_extraction_result.ocr_confidence = None
        mock_extraction_result.warnings = []
        mock_extraction_result.metadata = {}

        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = mock_extraction_result

        mock_registry = MagicMock()
        mock_registry.get_extractor.return_value = mock_extractor

        with (
            patch("employee_help.casefile.processing.get_registry", return_value=mock_registry),
            patch(
                "employee_help.casefile.extractors.tier2.Tier2Extractor"
            ) as MockTier2Class,
        ):
            await process_file(
                case_storage, cf.id, sample_case.id,
                case_fact_storage=fact_storage,
                llm_client=mock_llm,
            )

        # Tier2Extractor should NOT have been instantiated
        MockTier2Class.assert_not_called()

        # No LLM facts should exist
        all_facts = fact_storage.list_current_facts(sample_case.id)
        llm_facts = [f for f in all_facts if f.extraction_method == ExtractionMethod.LLM]
        assert len(llm_facts) == 0

    async def test_tier2_skipped_when_no_llm_client(
        self, case_storage, fact_storage, sample_case, tmp_dir,
    ):
        """Tier 2 does NOT run when llm_client is None (not configured)."""
        cf = _write_complaint_file(case_storage, sample_case, tmp_dir)

        complaint_text = (
            "COMPLAINT FOR DAMAGES\n\n"
            "SUPERIOR COURT OF CALIFORNIA\n\n"
            "Plaintiff alleges discrimination."
        )

        mock_extraction_result = MagicMock()
        mock_extraction_result.text = complaint_text
        mock_extraction_result.page_count = 2
        mock_extraction_result.ocr_confidence = None
        mock_extraction_result.warnings = []
        mock_extraction_result.metadata = {}

        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = mock_extraction_result

        mock_registry = MagicMock()
        mock_registry.get_extractor.return_value = mock_extractor

        with (
            patch("employee_help.casefile.processing.get_registry", return_value=mock_registry),
            patch(
                "employee_help.casefile.extractors.tier2.Tier2Extractor"
            ) as MockTier2Class,
        ):
            # llm_client=None — Tier 2 should be skipped
            await process_file(
                case_storage, cf.id, sample_case.id,
                case_fact_storage=fact_storage,
                llm_client=None,
            )

        # Tier2Extractor should NOT have been instantiated
        MockTier2Class.assert_not_called()

        # Only Tier 1 (regex) facts should exist
        all_facts = fact_storage.list_current_facts(sample_case.id)
        for f in all_facts:
            assert f.extraction_method == ExtractionMethod.REGEX
