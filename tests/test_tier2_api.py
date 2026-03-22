"""Tests for POST /api/cases/{case_id}/extract — Tier 2 LLM extraction API (V2.2c.3).

Tests the endpoint logic by mocking the LLM client and storage dependencies.
Uses FastAPI TestClient with mocked auth and services.
"""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

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
def storage(tmp_path: Path) -> Storage:
    db_path = tmp_path / "test.db"
    s = Storage(db_path=db_path)
    s.close()
    # Reopen with check_same_thread=False for TestClient (runs in separate thread)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    s._conn = conn
    yield s
    conn.close()


@pytest.fixture
def case_storage(storage: Storage) -> CaseStorage:
    return CaseStorage(conn=storage._conn)


@pytest.fixture
def fact_storage(storage: Storage):
    from employee_help.storage.case_fact_storage import CaseFactStorage

    return CaseFactStorage(conn=storage._conn)


@pytest.fixture
def user_claims():
    return SimpleNamespace(sub="test-user", org="test-org", role="member", email="test@law.com")


@pytest.fixture
def sample_case(case_storage) -> Case:
    case = Case(name="Tier2 Test Case", user_id="test-user", organization_id="test-org")
    return case_storage.create_case(case)


@pytest.fixture
def complaint_file(case_storage, sample_case, tmp_path) -> CaseFile:
    """A ready complaint file with extracted text."""
    file_path = tmp_path / "complaint.pdf"
    file_path.write_bytes(b"fake pdf")

    cf = CaseFile(
        case_id=sample_case.id,
        original_filename="complaint.pdf",
        file_type=FileType.PDF,
        mime_type="application/pdf",
        file_size_bytes=8,
        storage_path=str(file_path),
        upload_order=0,
        processing_status=ProcessingStatus.READY,
        extracted_text=(
            "COMPLAINT FOR DAMAGES\n\n"
            "SUPERIOR COURT OF CALIFORNIA, COUNTY OF LOS ANGELES\n\n"
            "FIRST CAUSE OF ACTION\n"
            "FEHA Discrimination\n"
            "Plaintiff alleges age-based discrimination.\n"
        ),
    )
    return case_storage.create_case_file(cf)


@pytest.fixture
def email_file(case_storage, sample_case, tmp_path) -> CaseFile:
    """A ready email file (non-complaint)."""
    file_path = tmp_path / "message.eml"
    file_path.write_bytes(b"fake email")

    cf = CaseFile(
        case_id=sample_case.id,
        original_filename="message.eml",
        file_type=FileType.EML,
        mime_type="message/rfc822",
        file_size_bytes=10,
        storage_path=str(file_path),
        upload_order=1,
        processing_status=ProcessingStatus.READY,
        extracted_text="From: alice@corp.com\nTo: bob@corp.com\nSubject: Meeting\nDate: 2025-01-01\n\nHello!",
    )
    return case_storage.create_case_file(cf)


@pytest.fixture
def queued_file(case_storage, sample_case, tmp_path) -> CaseFile:
    """A file still being processed."""
    file_path = tmp_path / "processing.pdf"
    file_path.write_bytes(b"not ready")

    cf = CaseFile(
        case_id=sample_case.id,
        original_filename="processing.pdf",
        file_type=FileType.PDF,
        mime_type="application/pdf",
        file_size_bytes=9,
        storage_path=str(file_path),
        upload_order=2,
        processing_status=ProcessingStatus.PROCESSING,
    )
    return case_storage.create_case_file(cf)


def _mock_tier2_result(case_id: str, file_id: str):
    """Build a mock Tier2Result with realistic facts."""
    from employee_help.casefile.extractors.tier2 import Tier2Result

    facts = [
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
            category=FactCategory.PARTY,
            fact_type="plaintiff",
            value={"name": "Jane Doe", "role": "plaintiff", "party_type": "individual"},
            source_file_id=file_id,
            extraction_method=ExtractionMethod.LLM,
            confidence=0.85,
        ),
    ]
    return Tier2Result(
        facts=facts,
        factual_summary="Plaintiff alleges age-based discrimination by employer.",
        input_tokens=1200,
        output_tokens=350,
    )


@pytest.fixture
def client(case_storage, fact_storage, user_claims):
    """TestClient with mocked auth and services."""
    from employee_help.api.main import app

    mock_llm = MagicMock()

    with (
        patch("employee_help.api.casefile_routes._get_case_storage", return_value=case_storage),
        patch("employee_help.api.casefile_routes._get_case_fact_storage", return_value=fact_storage),
        patch("employee_help.api.casefile_routes._require_user", return_value=user_claims),
        patch("employee_help.api.deps.get_llm_client", return_value=mock_llm),
        patch("employee_help.api.casefile_routes._audit"),
        patch("employee_help.api.main._requires_auth", return_value=False),
    ):
        yield TestClient(app, raise_server_exceptions=False), mock_llm


# ── Tests ──────────────────────────────────────────────────────────


class TestTier2ExtractEndpoint:
    def test_extract_single_file_creates_facts(
        self, client, sample_case, complaint_file, fact_storage,
    ):
        """POST /extract with file_id extracts from that file and creates facts."""
        test_client, mock_llm = client
        result = _mock_tier2_result(sample_case.id, complaint_file.id)

        with patch(
            "employee_help.casefile.extractors.tier2.Tier2Extractor"
        ) as MockExtractor:
            instance = MockExtractor.return_value
            instance.can_extract.return_value = True
            instance.extract.return_value = result

            resp = test_client.post(
                f"/api/cases/{sample_case.id}/extract",
                json={"file_id": complaint_file.id},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["facts_created"] == 2
        assert data["files_processed"] == 1
        assert data["factual_summary"] == "Plaintiff alleges age-based discrimination by employer."
        assert len(data["facts"]) == 2

        # Verify facts were persisted
        stored = fact_storage.list_current_facts(sample_case.id)
        llm_facts = [f for f in stored if f.extraction_method == ExtractionMethod.LLM]
        assert len(llm_facts) == 2

    def test_extract_all_key_documents(
        self, client, sample_case, complaint_file, email_file, fact_storage,
    ):
        """POST /extract without file_id processes only key documents (complaints etc)."""
        test_client, mock_llm = client
        result = _mock_tier2_result(sample_case.id, complaint_file.id)

        with patch(
            "employee_help.casefile.extractors.tier2.Tier2Extractor"
        ) as MockExtractor:
            instance = MockExtractor.return_value
            # complaint → can extract; email → cannot
            instance.can_extract.side_effect = lambda dt: dt.value in ("complaint", "answer", "demand_letter")
            instance.extract.return_value = result

            resp = test_client.post(
                f"/api/cases/{sample_case.id}/extract",
                json={},
            )

        assert resp.status_code == 200
        data = resp.json()
        # Only complaint should be processed, not email
        assert data["files_processed"] == 1
        assert data["facts_created"] == 2

    def test_extract_rejects_unready_file(
        self, client, sample_case, queued_file,
    ):
        """POST /extract with file_id for a non-ready file returns 400."""
        test_client, _ = client

        resp = test_client.post(
            f"/api/cases/{sample_case.id}/extract",
            json={"file_id": queued_file.id},
        )

        assert resp.status_code == 400
        assert "not ready" in resp.json()["detail"].lower()

    def test_extract_unknown_file_returns_404(
        self, client, sample_case,
    ):
        """POST /extract with nonexistent file_id returns 404."""
        test_client, _ = client

        resp = test_client.post(
            f"/api/cases/{sample_case.id}/extract",
            json={"file_id": "nonexistent-file-id"},
        )

        assert resp.status_code == 404

    def test_extract_llm_failure_returns_502(
        self, client, sample_case, complaint_file,
    ):
        """POST /extract returns 502 when LLM extraction fails on single file."""
        from employee_help.casefile.extractors.tier2 import Tier2ExtractionError

        test_client, mock_llm = client

        with patch(
            "employee_help.casefile.extractors.tier2.Tier2Extractor"
        ) as MockExtractor:
            instance = MockExtractor.return_value
            instance.can_extract.return_value = True
            instance.extract.side_effect = Tier2ExtractionError("API timeout")

            resp = test_client.post(
                f"/api/cases/{sample_case.id}/extract",
                json={"file_id": complaint_file.id},
            )

        assert resp.status_code == 502
        assert "Extraction failed" in resp.json()["detail"]
