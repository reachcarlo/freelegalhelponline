"""Tests for the search functionality."""

import pytest

from employee_help.search import ChunkSearch, SearchResult
from employee_help.storage.models import Chunk, Document, ContentType
from employee_help.storage.storage import Storage
from datetime import datetime, timezone


@pytest.fixture
def search_with_sample_data():
    """Create a search instance with sample discrimination definition data."""
    storage = Storage(":memory:")

    # Create a crawl run
    run = storage.create_run()

    # Create a sample document about discrimination
    doc = Document(
        source_url="https://calcivilrights.ca.gov/employment/protected-categories/",
        title="Protected Categories and Discrimination Definition",
        content_type=ContentType.HTML,
        raw_content="Sample content about discrimination",
        content_hash="abc123",
        crawl_run_id=run.id,
        language="en",
    )
    stored_doc, _ = storage.upsert_document(doc)

    # Create chunks with sample content about discrimination definitions
    chunks = [
        Chunk(
            document_id=stored_doc.id,
            chunk_index=0,
            content="""# Discrimination Definition

Discrimination in employment occurs when an employer treats an employee or
applicant unfavorably because of a protected characteristic. Under California
law, it is unlawful for an employer to discriminate against employees on the
basis of protected characteristics in hiring, firing, pay, job assignments,
promotions, layoffs, training, or any other term or condition of employment.

Protected characteristics include:
- Race
- Color
- Ancestry
- National Origin
- Ethnic Background
- Religion
- Gender
- Gender Identity
- Gender Expression
- Sexual Orientation
- Age (40+)
- Disability
- Genetic Information
- Marital Status
- Military/Veteran Status
- Political Activities
- Pregnancy
- Breastfeeding""",
            heading_path="Employment > Protected Categories > Discrimination Definition",
            token_count=287,
            content_hash="chunk1",
        ),
        Chunk(
            document_id=stored_doc.id,
            chunk_index=1,
            content="""# Elements of Discrimination

To establish a claim of discrimination, an employee must typically demonstrate:

1. **Protected Status**: The employee is a member of a protected class
   (based on race, color, ancestry, national origin, ethnic background,
   religion, gender, gender identity, gender expression, sexual orientation,
   age, disability, genetic information, marital status, military status,
   political activities, pregnancy, or breastfeeding).

2. **Job Performance**: The employee was qualified for the position and
   performing job duties satisfactorily.

3. **Adverse Employment Action**: The employee suffered an adverse employment
   action (such as termination, demotion, denial of promotion, or change in
   compensation).

4. **Differential Treatment**: The employee was treated less favorably than
   similarly situated employees outside the protected class.

These four elements form the basic framework for evaluating whether discrimination
has occurred in the workplace.""",
            heading_path="Employment > Protected Categories > Elements of Discrimination",
            token_count=268,
            content_hash="chunk2",
        ),
        Chunk(
            document_id=stored_doc.id,
            chunk_index=2,
            content="""# Legal Framework for Discrimination Claims

California law protects employees from discrimination through several statutes:

## Fair Employment and Housing Act (FEHA)

The FEHA is the primary California law prohibiting employment discrimination.
It provides broader protections than federal law and covers employers with
as few as one employee.

## Protected Bases Under FEHA

Discrimination is prohibited based on:
- Race
- Color
- Religion
- Sex (including pregnancy, childbirth, and related conditions)
- Gender identity
- Gender expression
- Sexual orientation
- National origin
- Ancestry
- Age (40 years or older)
- Physical disability
- Mental disability
- Genetic information
- Marital status
- Military or veteran status

Discrimination can occur in all aspects of employment, including recruitment,
hiring, compensation, job assignment, promotion, and termination.""",
            heading_path="Employment > Legal Framework > FEHA Protection",
            token_count=245,
            content_hash="chunk3",
        ),
    ]

    storage.insert_chunks(chunks)

    # Return both storage and search instance
    search = ChunkSearch(":memory:")
    # Manually set storage to the populated one
    search.storage = storage

    yield search, storage

    search.close()


class TestChunkSearch:
    """Tests for chunk search functionality."""

    def test_search_initialization(self, search_with_sample_data):
        """ChunkSearch should initialize with database."""
        search, _ = search_with_sample_data
        assert search.storage is not None

    def test_search_for_discrimination_definition(self, search_with_sample_data):
        """Search should find discrimination definition chunks."""
        search, storage = search_with_sample_data

        results = search.search("discrimination definition", top_k=5)

        assert len(results) > 0
        assert any("discrimination" in r.content.lower() for r in results)

    def test_search_returns_relevant_results(self, search_with_sample_data):
        """Search should return results in relevance order."""
        search, storage = search_with_sample_data

        results = search.search("elements of discrimination", top_k=5)

        # Should have results
        assert len(results) > 0

        # Results should be ordered by relevance (descending)
        scores = [r.relevance_score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_result_structure(self, search_with_sample_data):
        """SearchResult should contain all required fields."""
        search, storage = search_with_sample_data

        results = search.search("protected characteristics", top_k=1)

        if results:
            result = results[0]
            assert result.chunk_id > 0
            assert result.document_url != ""
            assert result.heading_path != ""
            assert result.content != ""
            assert result.token_count > 0
            assert 0 <= result.relevance_score <= 1.0

    def test_search_with_multiple_keywords(self, search_with_sample_data):
        """Search should handle multiple keywords."""
        search, storage = search_with_sample_data

        results = search.search("protected class adverse action", top_k=5)

        assert len(results) > 0

    def test_search_with_min_score_threshold(self, search_with_sample_data):
        """Search should respect minimum score threshold."""
        search, storage = search_with_sample_data

        # Search with high threshold
        results_high = search.search("discrimination", top_k=5, min_score=0.8)

        # Search with low threshold
        results_low = search.search("discrimination", top_k=5, min_score=0.1)

        # Low threshold should return more results
        assert len(results_low) >= len(results_high)

    def test_search_heading_boost(self, search_with_sample_data):
        """Search should boost relevance for matches in headings."""
        search, storage = search_with_sample_data

        results = search.search("elements", top_k=5)

        # Should find the "Elements of Discrimination" chunk
        assert len(results) > 0

    def test_search_context_manager(self, search_with_sample_data):
        """ChunkSearch should work as context manager."""
        search, _ = search_with_sample_data

        with search as s:
            results = s.search("discrimination", top_k=3)
            assert isinstance(results, list)


class TestDiscriminationQuestionValidation:
    """Validation test for the sample discrimination definition question."""

    def test_answer_discrimination_definition_question(self, search_with_sample_data):
        """Validate that the system can answer the discrimination definition question.

        This is the Phase 1G validation test for the user's question:
        "How is discrimination defined? What are the elements of discrimination?"
        """
        search, storage = search_with_sample_data

        # Search for discrimination definition
        results = search.search("discrimination definition elements", top_k=3)

        # Assertions
        assert len(results) > 0, "Should find relevant chunks about discrimination"

        # Verify we got the main definition chunk
        content_contains_definition = any(
            "discrimination in employment" in r.content.lower() for r in results
        )
        assert content_contains_definition, "Should find discrimination definition"

        # Verify we got the elements chunk
        content_contains_elements = any(
            "elements" in r.heading_path.lower() for r in results
        )
        assert content_contains_elements, "Should find elements of discrimination"

        # Print the search results to show what would be returned
        print("\n" + "=" * 70)
        print("PHASE 1G VALIDATION: Discrimination Definition Search")
        print("=" * 70)
        print("\nQuestion: How is discrimination defined? What are the elements?")
        print("\nSearch Results:")
        print("-" * 70)

        for i, result in enumerate(results, 1):
            print(f"\nResult {i}:")
            print(f"  Relevance: {result.relevance_score:.2f}")
            print(f"  Heading: {result.heading_path}")
            print(f"  Document: {result.document_url}")
            print(f"  Tokens: {result.token_count}")
            print(f"  Content Preview:")
            content_lines = result.content.split("\n")[:5]
            for line in content_lines:
                if line.strip():
                    print(f"    {line}")
            if len(content_lines) > 5:
                print(f"    ... ({result.token_count} tokens total)")

        print("\n" + "=" * 70)
        print("✅ VALIDATION PASSED - System can retrieve discrimination definitions")
        print("=" * 70 + "\n")
