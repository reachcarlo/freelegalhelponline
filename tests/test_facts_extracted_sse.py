"""Tests for V2.1c.7: SSE facts_extracted event after Tier 1 extraction completes."""

from __future__ import annotations

import pytest

from employee_help.casefile.processing import (
    process_file,
    register_sse_client,
    unregister_sse_client,
)
from employee_help.storage.case_fact_storage import CaseFactStorage
from employee_help.storage.case_storage import CaseStorage
from employee_help.storage.models import Case, CaseFile, FileType
from employee_help.storage.storage import Storage


@pytest.fixture()
def db():
    storage = Storage(db_path=":memory:")
    yield storage._conn
    storage.close()


@pytest.fixture()
def case_storage(db):
    return CaseStorage(conn=db)


@pytest.fixture()
def case_fact_storage(db):
    return CaseFactStorage(conn=db)


@pytest.fixture()
def sample_case(case_storage):
    case = Case(name="SSE Test Case", user_id="u1", organization_id="o1")
    return case_storage.create_case(case)


@pytest.fixture(autouse=True)
def _clean_queues():
    from employee_help.casefile import processing

    processing._status_queues.clear()
    yield
    processing._status_queues.clear()


def _create_file(case_storage, case_id, tmp_path, filename="complaint.txt", content=""):
    file_path = tmp_path / filename
    file_path.write_text(content)
    cf = CaseFile(
        case_id=case_id,
        original_filename=filename,
        file_type=FileType.TXT,
        mime_type="text/plain",
        file_size_bytes=len(content.encode()),
        storage_path=str(file_path),
        upload_order=0,
    )
    return case_storage.create_case_file(cf)


# Text with recognisable patterns so Tier 1 extractors find facts
_COMPLAINT_TEXT = """\
SUPERIOR COURT OF THE STATE OF CALIFORNIA
COUNTY OF LOS ANGELES

Jane Doe, Plaintiff,
v.
Acme Corp, Defendant.

Case No. 24STCV12345

Filed: 2026-01-15

COMPLAINT FOR DAMAGES
"""


class TestFactsExtractedSSE:
    """V2.1c.7: facts_extracted SSE event is broadcast after Tier 1 extraction."""

    @pytest.mark.asyncio
    async def test_facts_extracted_event_broadcast(
        self, case_storage, case_fact_storage, sample_case, tmp_path
    ):
        """After processing a file with fact storage, a facts_extracted event is broadcast."""
        cf = _create_file(
            case_storage, sample_case.id, tmp_path,
            filename="complaint.txt",
            content=_COMPLAINT_TEXT,
        )

        q = register_sse_client(sample_case.id)

        await process_file(
            case_storage, cf.id, sample_case.id,
            case_fact_storage=case_fact_storage,
        )

        events = []
        while not q.empty():
            events.append(q.get_nowait())

        facts_events = [e for e in events if e.get("status") == "facts_extracted"]
        assert len(facts_events) == 1, f"Expected 1 facts_extracted event, got {len(facts_events)}: {events}"

        evt = facts_events[0]
        assert evt["file_id"] == cf.id
        assert isinstance(evt["count"], int)
        assert evt["count"] >= 0

        # Verify ordering: facts_extracted comes after processing, before ready
        statuses = [e["status"] for e in events]
        assert statuses.index("processing") < statuses.index("facts_extracted")
        assert statuses.index("facts_extracted") < statuses.index("ready")

        unregister_sse_client(sample_case.id, q)

    @pytest.mark.asyncio
    async def test_no_facts_extracted_event_without_storage(
        self, case_storage, sample_case, tmp_path
    ):
        """Without case_fact_storage, no facts_extracted event is broadcast."""
        cf = _create_file(
            case_storage, sample_case.id, tmp_path,
            filename="complaint.txt",
            content=_COMPLAINT_TEXT,
        )

        q = register_sse_client(sample_case.id)

        # No case_fact_storage → no extraction → no facts_extracted event
        await process_file(case_storage, cf.id, sample_case.id)

        events = []
        while not q.empty():
            events.append(q.get_nowait())

        facts_events = [e for e in events if e.get("status") == "facts_extracted"]
        assert len(facts_events) == 0, f"Expected no facts_extracted event, got: {facts_events}"

        # Should still have processing + ready
        statuses = [e["status"] for e in events]
        assert "processing" in statuses
        assert "ready" in statuses

        unregister_sse_client(sample_case.id, q)
