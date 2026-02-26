"""Retrieval quality evaluation test suite.

Runs retrieval for each evaluation question and asserts aggregate metrics
meet quality thresholds. Requires embedded data in the vector store.

Marked with @pytest.mark.evaluation -- not run in fast CI.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from employee_help.evaluation.retrieval_metrics import (
    citation_hit_at_k,
    mean_reciprocal_rank,
    precision_at_k,
    recall_at_k,
)

pytestmark = pytest.mark.evaluation


@pytest.fixture(scope="module")
def retrieval_service():
    """Build a retrieval service connected to the real vector store."""
    # This import will fail if RAG dependencies aren't installed
    pytest.importorskip("sentence_transformers")
    pytest.importorskip("lancedb")

    from employee_help.retrieval.embedder import EmbeddingService
    from employee_help.retrieval.query import QueryPreprocessor
    from employee_help.retrieval.service import RetrievalService
    from employee_help.retrieval.vector_store import VectorStore

    vector_store = VectorStore(db_path="data/lancedb")
    if vector_store.table is None:
        pytest.skip("Vector store not populated. Run 'employee-help embed --all' first.")

    embedding_service = EmbeddingService()
    return RetrievalService(
        vector_store=vector_store,
        embedding_service=embedding_service,
        query_preprocessor=QueryPreprocessor(),
        reranker=None,  # Skip reranking for faster evaluation
        reranker_enabled=False,
    )


@pytest.fixture(scope="module")
def consumer_questions():
    path = Path("tests/evaluation/consumer_questions.yaml")
    if not path.exists():
        pytest.skip("Consumer evaluation dataset not found")
    with open(path) as f:
        return yaml.safe_load(f)["questions"]


@pytest.fixture(scope="module")
def attorney_questions():
    path = Path("tests/evaluation/attorney_questions.yaml")
    if not path.exists():
        pytest.skip("Attorney evaluation dataset not found")
    with open(path) as f:
        return yaml.safe_load(f)["questions"]


class TestConsumerRetrievalQuality:
    """Consumer mode retrieval quality tests."""

    def test_consumer_precision(self, retrieval_service, consumer_questions):
        precisions = []
        for q in consumer_questions:
            results = retrieval_service.retrieve(q["question"], mode="consumer")
            expected = set(q.get("expected_categories", []))
            prec = precision_at_k(results, expected, k=5)
            precisions.append(prec)

        avg_precision = sum(precisions) / len(precisions) if precisions else 0
        assert avg_precision >= 0.6, f"Consumer precision@5 = {avg_precision:.3f} < 0.6"

    def test_consumer_all_return_results(self, retrieval_service, consumer_questions):
        for q in consumer_questions:
            results = retrieval_service.retrieve(q["question"], mode="consumer")
            assert len(results) > 0, f"No results for: {q['question']}"


class TestAttorneyRetrievalQuality:
    """Attorney mode retrieval quality tests."""

    def test_attorney_precision(self, retrieval_service, attorney_questions):
        precisions = []
        for q in attorney_questions:
            results = retrieval_service.retrieve(q["question"], mode="attorney")
            expected = set(q.get("expected_categories", []))
            prec = precision_at_k(results, expected, k=5)
            precisions.append(prec)

        avg_precision = sum(precisions) / len(precisions) if precisions else 0
        assert avg_precision >= 0.7, f"Attorney precision@5 = {avg_precision:.3f} < 0.7"

    def test_citation_queries_top1(self, retrieval_service, attorney_questions):
        citation_questions = [
            q for q in attorney_questions if q.get("expected_citations")
        ]
        if not citation_questions:
            pytest.skip("No citation-specific questions in dataset")

        hits = 0
        for q in citation_questions:
            results = retrieval_service.retrieve(q["question"], mode="attorney")
            for expected_cite in q["expected_citations"]:
                if citation_hit_at_k(results, expected_cite, k=1):
                    hits += 1
                    break

        accuracy = hits / len(citation_questions)
        assert accuracy >= 0.9, f"Citation top-1 accuracy = {accuracy:.3f} < 0.9"

    def test_attorney_all_return_results(self, retrieval_service, attorney_questions):
        for q in attorney_questions:
            results = retrieval_service.retrieve(q["question"], mode="attorney")
            assert len(results) > 0, f"No results for: {q['question']}"
