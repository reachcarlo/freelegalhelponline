"""Tests for the FeedbackStore — query logging and user feedback."""

from __future__ import annotations

import uuid

import pytest

from employee_help.feedback.models import CitationAuditEntry, FeedbackEntry, QueryLogEntry
from employee_help.feedback.store import FeedbackStore


@pytest.fixture
def store(tmp_path):
    """Create a FeedbackStore with a temp database."""
    db_path = tmp_path / "feedback.db"
    s = FeedbackStore(db_path)
    yield s
    s.close()


def _make_entry(mode: str = "consumer", **kwargs) -> QueryLogEntry:
    defaults = {
        "query_id": str(uuid.uuid4()),
        "query_hash": "abc123",
        "mode": mode,
        "model": "claude-haiku-4-5-20251001",
        "input_tokens": 100,
        "output_tokens": 20,
        "cost_estimate": 0.006,
        "duration_ms": 1500,
        "source_count": 3,
    }
    defaults.update(kwargs)
    return QueryLogEntry(**defaults)


class TestLogQuery:
    def test_log_and_retrieve(self, store):
        entry = _make_entry()
        result = store.log_query(entry)
        assert result.query_id == entry.query_id

    def test_duplicate_query_id_rejected(self, store):
        entry = _make_entry()
        store.log_query(entry)
        with pytest.raises(Exception):
            store.log_query(entry)

    def test_log_with_error(self, store):
        entry = _make_entry(error="Model timeout")
        result = store.log_query(entry)
        assert result.error == "Model timeout"


class TestFeedback:
    def test_add_and_get_feedback(self, store):
        entry = _make_entry()
        store.log_query(entry)

        fb = FeedbackEntry(query_id=entry.query_id, rating=1)
        store.add_feedback(fb)

        result = store.get_feedback(entry.query_id)
        assert result is not None
        assert result.rating == 1

    def test_add_feedback_unknown_query_id_raises(self, store):
        fb = FeedbackEntry(query_id="nonexistent", rating=1)
        with pytest.raises(ValueError, match="Unknown query_id"):
            store.add_feedback(fb)

    def test_get_feedback_returns_none_when_empty(self, store):
        entry = _make_entry()
        store.log_query(entry)
        assert store.get_feedback(entry.query_id) is None

    def test_multiple_feedback_returns_latest(self, store):
        entry = _make_entry()
        store.log_query(entry)

        store.add_feedback(FeedbackEntry(query_id=entry.query_id, rating=1))
        store.add_feedback(FeedbackEntry(query_id=entry.query_id, rating=-1))

        result = store.get_feedback(entry.query_id)
        assert result is not None
        assert result.rating == -1


class TestDailyStats:
    def test_empty_store_returns_empty(self, store):
        assert store.get_daily_stats() == []

    def test_groups_by_day(self, store):
        store.log_query(_make_entry(mode="consumer"))
        store.log_query(_make_entry(mode="attorney"))
        store.log_query(_make_entry(mode="consumer"))

        stats = store.get_daily_stats()
        assert len(stats) == 1
        assert stats[0]["total"] == 3
        assert stats[0]["consumer"] == 2
        assert stats[0]["attorney"] == 1


class TestModeDistribution:
    def test_empty_store(self, store):
        assert store.get_mode_distribution() == {}

    def test_counts_by_mode(self, store):
        store.log_query(_make_entry(mode="consumer"))
        store.log_query(_make_entry(mode="consumer"))
        store.log_query(_make_entry(mode="attorney"))

        dist = store.get_mode_distribution()
        assert dist == {"consumer": 2, "attorney": 1}


class TestFeedbackSummary:
    def test_empty_store(self, store):
        summary = store.get_feedback_summary()
        assert summary["total_feedback"] == 0
        assert summary["thumbs_up"] == 0
        assert summary["thumbs_down"] == 0
        assert summary["approval_rate"] == 0.0
        assert summary["feedback_rate"] == 0.0

    def test_with_feedback(self, store):
        e1 = _make_entry()
        e2 = _make_entry()
        e3 = _make_entry()
        store.log_query(e1)
        store.log_query(e2)
        store.log_query(e3)

        store.add_feedback(FeedbackEntry(query_id=e1.query_id, rating=1))
        store.add_feedback(FeedbackEntry(query_id=e2.query_id, rating=1))
        store.add_feedback(FeedbackEntry(query_id=e3.query_id, rating=-1))

        summary = store.get_feedback_summary()
        assert summary["thumbs_up"] == 2
        assert summary["thumbs_down"] == 1
        assert summary["total_feedback"] == 3
        assert summary["total_queries"] == 3
        assert summary["approval_rate"] == pytest.approx(0.667, abs=0.001)
        assert summary["feedback_rate"] == 1.0


class TestTopRepeatedQueries:
    def test_empty_store(self, store):
        assert store.get_top_repeated_queries() == []

    def test_groups_by_hash(self, store):
        # Same hash asked 3 times
        for _ in range(3):
            store.log_query(_make_entry(query_hash="repeated_hash"))

        # Unique hash asked once
        store.log_query(_make_entry(query_hash="unique_hash"))

        repeated = store.get_top_repeated_queries()
        assert len(repeated) == 1
        assert repeated[0]["query_hash"] == "repeated_hash"
        assert repeated[0]["count"] == 3

    def test_respects_limit(self, store):
        for i in range(5):
            for _ in range(2):
                store.log_query(_make_entry(query_hash=f"hash_{i}"))

        repeated = store.get_top_repeated_queries(limit=3)
        assert len(repeated) == 3


class TestCitationAudit:
    """Tests for the citation_audit table operations."""

    def _make_audit(self, **kwargs) -> CitationAuditEntry:
        defaults = {
            "query_id": str(uuid.uuid4()),
            "citation_text": "Cal. Lab. Code § 1102.5",
            "citation_type": "statute",
            "verification_status": "verified",
            "confidence": "verified",
            "detail": "Verified in knowledge base",
            "model_used": "claude-sonnet-4-6",
        }
        defaults.update(kwargs)
        return CitationAuditEntry(**defaults)

    def test_log_and_stats(self, store):
        entries = [
            self._make_audit(confidence="verified"),
            self._make_audit(confidence="verified"),
            self._make_audit(confidence="unverified"),
            self._make_audit(confidence="suspicious"),
        ]
        store.log_citation_audit(entries)

        stats = store.get_citation_audit_stats()
        assert stats["total"] == 4
        assert stats["verified"] == 2
        assert stats["unverified"] == 1
        assert stats["suspicious"] == 1

    def test_empty_store_stats(self, store):
        stats = store.get_citation_audit_stats()
        assert stats["total"] == 0
        assert stats["verified"] == 0

    def test_log_empty_list(self, store):
        store.log_citation_audit([])  # Should not raise
        assert store.get_citation_audit_stats()["total"] == 0

    def test_by_type(self, store):
        entries = [
            self._make_audit(citation_type="case", confidence="verified"),
            self._make_audit(citation_type="case", confidence="suspicious"),
            self._make_audit(citation_type="statute", confidence="verified"),
        ]
        store.log_citation_audit(entries)

        by_type = store.get_citation_audit_by_type()
        assert len(by_type) == 3  # case/verified, case/suspicious, statute/verified
        types = {(r["citation_type"], r["confidence"]) for r in by_type}
        assert ("case", "verified") in types
        assert ("case", "suspicious") in types
        assert ("statute", "verified") in types

    def test_by_session(self, store):
        sid = "session-123"
        entries = [
            self._make_audit(session_id=sid),
            self._make_audit(session_id=sid),
            self._make_audit(session_id="other"),
        ]
        store.log_citation_audit(entries)

        rows = store.get_citation_audit_by_session(sid)
        assert len(rows) == 2

    def test_by_session_empty(self, store):
        rows = store.get_citation_audit_by_session("nonexistent")
        assert rows == []

    def test_rows_for_csv(self, store):
        entries = [
            self._make_audit(confidence="verified"),
            self._make_audit(confidence="suspicious"),
        ]
        store.log_citation_audit(entries)

        rows = store.get_citation_audit_rows()
        assert len(rows) == 2
        assert "query_id" in rows[0]
        assert "citation_text" in rows[0]

    def test_rows_filtered_by_confidence(self, store):
        entries = [
            self._make_audit(confidence="verified"),
            self._make_audit(confidence="suspicious"),
        ]
        store.log_citation_audit(entries)

        rows = store.get_citation_audit_rows(confidence="suspicious")
        assert len(rows) == 1
        assert rows[0]["confidence"] == "suspicious"


class TestContextManager:
    def test_context_manager(self, tmp_path):
        db_path = tmp_path / "feedback.db"
        with FeedbackStore(db_path) as store:
            store.log_query(_make_entry())
        # Should not raise after close
