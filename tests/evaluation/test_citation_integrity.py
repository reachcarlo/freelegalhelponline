"""Citation integrity test suite for attorney mode.

Verifies that the answer generation pipeline does not produce
hallucinated statute citations.

Marked with @pytest.mark.evaluation -- not run in fast CI.
Requires live LLM API key.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from employee_help.evaluation.answer_metrics import extract_statute_citations

pytestmark = [pytest.mark.evaluation, pytest.mark.llm]


@pytest.fixture(scope="module")
def answer_service():
    """Build a complete answer service for testing."""
    pytest.importorskip("sentence_transformers")
    pytest.importorskip("lancedb")
    pytest.importorskip("anthropic")

    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    from employee_help.generation.llm import LLMClient
    from employee_help.generation.prompts import PromptBuilder
    from employee_help.generation.service import AnswerService
    from employee_help.retrieval.embedder import EmbeddingService
    from employee_help.retrieval.query import QueryPreprocessor
    from employee_help.retrieval.service import RetrievalService
    from employee_help.retrieval.vector_store import VectorStore

    vector_store = VectorStore(db_path="data/lancedb")
    if vector_store.table is None:
        pytest.skip("Vector store not populated")

    embedding_service = EmbeddingService()
    retrieval_service = RetrievalService(
        vector_store=vector_store,
        embedding_service=embedding_service,
        query_preprocessor=QueryPreprocessor(),
        reranker=None,
        reranker_enabled=False,
    )

    llm_client = LLMClient()
    prompt_builder = PromptBuilder()

    return AnswerService(
        retrieval_service=retrieval_service,
        llm_client=llm_client,
        prompt_builder=prompt_builder,
        citation_validation="strict",
    )


@pytest.fixture(scope="module")
def knowledge_base_citations():
    """Get all citations from the knowledge base."""
    from employee_help.storage.storage import Storage

    storage = Storage("data/employee_help.db")
    chunks = storage.get_all_chunks()
    citations = {c.citation for c in chunks if c.citation and c.is_active}
    storage.close()
    return citations


@pytest.fixture(scope="module")
def attorney_questions():
    path = Path("tests/evaluation/attorney_questions.yaml")
    if not path.exists():
        pytest.skip("Attorney evaluation dataset not found")
    with open(path) as f:
        return yaml.safe_load(f)["questions"]


class TestCitationIntegrity:
    """Verify no hallucinated citations in attorney mode answers."""

    def test_no_hallucinated_citations(
        self, answer_service, knowledge_base_citations, attorney_questions
    ):
        """Every statute citation in attorney answers must exist in the KB."""
        hallucinated = []

        for q in attorney_questions[:10]:  # Test first 10 for speed
            answer = answer_service.generate(q["question"], mode="attorney")
            cited = extract_statute_citations(answer.text)

            for cite_str in cited:
                # Check if this citation matches any KB citation
                import re

                section_match = re.search(r"(\d+(?:\.\d+)?)", cite_str)
                if section_match:
                    section_num = section_match.group(1)
                    found = any(
                        section_num in kbc for kbc in knowledge_base_citations
                    )
                    if not found:
                        hallucinated.append(
                            {
                                "question": q["question"],
                                "citation": cite_str,
                                "section": section_num,
                            }
                        )

        assert (
            len(hallucinated) == 0
        ), f"Found {len(hallucinated)} hallucinated citations: {hallucinated}"

    def test_answers_include_disclaimer(self, answer_service, attorney_questions):
        """All attorney answers should include a disclaimer."""
        for q in attorney_questions[:5]:
            answer = answer_service.generate(q["question"], mode="attorney")
            assert (
                "independently verified" in answer.text.lower()
                or "does not constitute" in answer.text.lower()
                or "not legal advice" in answer.text.lower()
            ), f"Missing disclaimer for: {q['question']}"
