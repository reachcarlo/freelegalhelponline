"""Answer generation service combining retrieval and LLM for RAG answers.

Orchestrates the full RAG pipeline: retrieve -> build prompt with document
blocks -> generate with Citations API -> validate citations -> return
structured answer.
"""

from __future__ import annotations

import re
import time
from typing import Any, Iterator

import structlog

from employee_help.generation.llm import LLMClient, StreamChunk
from employee_help.generation.models import Answer, AnswerCitation, TokenUsage
from employee_help.generation.prompts import PromptBuilder
from employee_help.retrieval.service import RetrievalResult, RetrievalService

logger = structlog.get_logger()

# Patterns for detecting statute citations in answer text
STATUTE_CITATION_PATTERN = re.compile(
    r"Cal\.\s+(?:Lab|Gov|Bus\.\s*&\s*Prof|Civ\.\s*Proc|Unemp\.\s*Ins)\.\s*Code\s*§\s*[\d]+(?:\.\d+)?(?:\([a-z0-9]+\))*",
    re.IGNORECASE,
)


class AnswerService:
    """Full RAG answer generation pipeline.

    Combines retrieval, prompt building with Citations API document blocks,
    LLM generation, and citation validation into a single service.
    """

    def __init__(
        self,
        retrieval_service: RetrievalService,
        llm_client: LLMClient,
        prompt_builder: PromptBuilder,
        *,
        citation_validation: str = "strict",
    ) -> None:
        self.retrieval_service = retrieval_service
        self.llm_client = llm_client
        self.prompt_builder = prompt_builder
        self.citation_validation = citation_validation
        self.logger = structlog.get_logger(__name__)

    def generate(self, query: str, mode: str = "consumer") -> Answer:
        """Generate a complete RAG answer.

        Pipeline: retrieve -> build prompt with document blocks ->
                  call LLM with Citations API -> validate citations.

        Args:
            query: User's natural language question.
            mode: "consumer" or "attorney".

        Returns:
            Answer with text, citations, and metadata.
        """
        start_time = time.monotonic()

        # 1. Retrieve relevant chunks
        retrieval_results = self.retrieval_service.retrieve(query, mode=mode)

        if not retrieval_results:
            return Answer(
                text=self._no_results_message(mode),
                mode=mode,
                query=query,
                warnings=["No relevant content found in the knowledge base."],
            )

        # 2. Build prompt with Citations API document blocks
        prompt = self.prompt_builder.build_prompt(
            query=query,
            mode=mode,
            retrieval_results=retrieval_results,
        )

        # 3. Call LLM with document blocks for Citations API
        response = self.llm_client.generate(
            system_prompt=prompt.system_prompt,
            user_message=prompt.user_message,
            mode=mode,
            document_blocks=prompt.document_blocks,
        )

        # 4. Extract and validate citations
        warnings: list[str] = []
        answer_text = response.text

        # Build citations from API response
        citations = self._extract_api_citations(
            response.citations, prompt.context_chunks
        )

        # Validate statute citations in attorney mode
        if mode == "attorney":
            answer_text, validation_citations, validation_warnings = (
                self._validate_statute_citations(
                    answer_text,
                    prompt.context_chunks,
                )
            )
            warnings.extend(validation_warnings)
            # Merge validation citations with API citations
            if validation_citations:
                existing_chunks = {c.chunk_id for c in citations}
                for vc in validation_citations:
                    if vc.chunk_id not in existing_chunks:
                        citations.append(vc)

        # If no citations from either source, build from context
        if not citations:
            citations = self._build_citations_from_context(prompt.context_chunks)

        duration_ms = int((time.monotonic() - start_time) * 1000)

        return Answer(
            text=answer_text,
            mode=mode,
            query=query,
            citations=citations,
            retrieval_results=retrieval_results,
            model_used=response.model,
            token_usage=response.token_usage,
            duration_ms=duration_ms,
            warnings=warnings,
        )

    def generate_stream(
        self,
        query: str,
        mode: str = "consumer",
    ) -> tuple[Iterator[str], list[RetrievalResult], list[dict[str, Any]]]:
        """Generate a streaming RAG answer.

        Returns an iterator of text chunks, the retrieval results used for
        context, and a mutable list that will be populated with stream metadata
        (citations, token usage) after streaming completes.

        Args:
            query: User's question.
            mode: "consumer" or "attorney".

        Returns:
            Tuple of (text stream iterator, retrieval results, stream metadata list).
            The metadata list is empty initially; after consuming the stream fully,
            it contains one dict with 'citations', 'input_tokens', 'output_tokens',
            'model' keys.
        """
        # 1. Retrieve
        retrieval_results = self.retrieval_service.retrieve(query, mode=mode)

        if not retrieval_results:
            def empty_stream():
                yield self._no_results_message(mode)

            return empty_stream(), [], []

        # 2. Build prompt with document blocks
        prompt = self.prompt_builder.build_prompt(
            query=query,
            mode=mode,
            retrieval_results=retrieval_results,
        )

        # Shared metadata container for stream results
        stream_metadata: list[dict[str, Any]] = []

        # 3. Stream from LLM with document blocks
        def text_stream():
            for chunk in self.llm_client.generate_stream(
                system_prompt=prompt.system_prompt,
                user_message=prompt.user_message,
                mode=mode,
                document_blocks=prompt.document_blocks,
            ):
                if chunk.text:
                    yield chunk.text
                if chunk.is_final:
                    stream_metadata.append({
                        "citations": chunk.citations,
                        "input_tokens": chunk.input_tokens,
                        "output_tokens": chunk.output_tokens,
                        "model": chunk.model,
                    })

        return text_stream(), retrieval_results, stream_metadata

    def _extract_api_citations(
        self,
        api_citations: list[dict[str, Any]],
        context_chunks: list[RetrievalResult],
    ) -> list[AnswerCitation]:
        """Extract structured citations from the Claude Citations API response.

        Maps document_index from the API response back to the corresponding
        retrieval result / chunk.
        """
        citations = []
        seen_chunks: set[int] = set()

        for api_cit in api_citations:
            doc_idx = api_cit.get("document_index")
            if doc_idx is None or doc_idx >= len(context_chunks):
                continue

            chunk = context_chunks[doc_idx]
            if chunk.chunk_id in seen_chunks:
                continue
            seen_chunks.add(chunk.chunk_id)

            citations.append(
                AnswerCitation(
                    claim_text=api_cit.get("cited_text", ""),
                    chunk_id=chunk.chunk_id,
                    source_url=chunk.source_url,
                    citation=chunk.citation,
                    content_category=chunk.content_category,
                    document_index=doc_idx,
                )
            )

        return citations

    def _validate_statute_citations(
        self,
        answer_text: str,
        context_chunks: list[RetrievalResult],
    ) -> tuple[str, list[AnswerCitation], list[str]]:
        """Validate statute citations in attorney mode answers.

        Checks that every cited statute section exists in the retrieved context.

        Returns:
            Tuple of (processed text, validated citations, warnings).
        """
        warnings: list[str] = []
        citations: list[AnswerCitation] = []

        # Extract all statute citations from the answer
        found_citations = STATUTE_CITATION_PATTERN.findall(answer_text)
        if not found_citations:
            return answer_text, citations, warnings

        # Build a set of citations available in context
        context_citations: set[str] = set()
        citation_to_chunk: dict[str, RetrievalResult] = {}
        for chunk in context_chunks:
            if chunk.citation:
                context_citations.add(chunk.citation)
                citation_to_chunk[chunk.citation] = chunk

        # Validate each citation
        for cite_str in found_citations:
            matched = False
            for ctx_cite in context_citations:
                if self._citation_matches(cite_str, ctx_cite):
                    matched = True
                    chunk = citation_to_chunk.get(ctx_cite)
                    if chunk:
                        citations.append(
                            AnswerCitation(
                                claim_text=cite_str,
                                chunk_id=chunk.chunk_id,
                                source_url=chunk.source_url,
                                citation=ctx_cite,
                                content_category=chunk.content_category,
                            )
                        )
                    break

            if not matched:
                warnings.append(f"Unverified citation: {cite_str}")
                if self.citation_validation == "strict":
                    answer_text = answer_text.replace(
                        cite_str, f"{cite_str} [citation not verified]"
                    )
                else:
                    answer_text = answer_text.replace(
                        cite_str, f"{cite_str} [unverified]"
                    )

        return answer_text, citations, warnings

    def _citation_matches(self, answer_cite: str, context_cite: str) -> bool:
        """Check if a citation in the answer matches a citation in the context.

        Uses flexible matching: extracts the code abbreviation and section
        number from both strings and compares them.
        """
        # Extract section numbers
        section_pattern = re.compile(r"§?\s*(\d+(?:\.\d+)?)")
        answer_match = section_pattern.search(answer_cite)
        context_match = section_pattern.search(context_cite)

        if not (answer_match and context_match):
            return False

        if answer_match.group(1) != context_match.group(1):
            return False

        # Also check code type matches (Lab vs Gov vs Bus & Prof)
        code_pattern = re.compile(
            r"(Lab|Gov|Bus|Civ|Unemp)", re.IGNORECASE
        )
        answer_code = code_pattern.search(answer_cite)
        context_code = code_pattern.search(context_cite)

        if answer_code and context_code:
            return answer_code.group(1).lower() == context_code.group(1).lower()

        # If only one has a code, still match on section number alone
        return True

    def _build_citations_from_context(
        self,
        context_chunks: list[RetrievalResult],
    ) -> list[AnswerCitation]:
        """Build citations from all context chunks used in the answer."""
        return [
            AnswerCitation(
                claim_text="",
                chunk_id=chunk.chunk_id,
                source_url=chunk.source_url,
                citation=chunk.citation,
                content_category=chunk.content_category,
            )
            for chunk in context_chunks
        ]

    def _no_results_message(self, mode: str) -> str:
        """Generate a message when no relevant content is found."""
        if mode == "consumer":
            return (
                "I wasn't able to find relevant information about your question "
                "in the California employment law knowledge base. This could mean "
                "the topic is outside the scope of the current knowledge base, "
                "or the question may need to be rephrased.\n\n"
                "You may want to:\n"
                "- Contact the California Department of Industrial Relations: https://www.dir.ca.gov/\n"
                "- Contact the Civil Rights Department: https://calcivilrights.ca.gov/\n"
                "- Consult a licensed California employment attorney.\n\n"
                "This information is for educational purposes only and is not legal advice. "
                "For advice about your specific situation, consult a licensed California employment attorney."
            )
        else:
            return (
                "No relevant statutory provisions or agency guidance were found "
                "in the knowledge base for this query. The knowledge base covers "
                "California Labor Code, Government Code (FEHA, whistleblower), "
                "Unemployment Insurance Code, Business & Professions Code, and "
                "Code of Civil Procedure, along with guidance from DIR, EDD, and CalHR.\n\n"
                "This AI-generated analysis is based on statutory text and agency guidance "
                "in the knowledge base. It should be independently verified against current "
                "authorities. This does not constitute legal advice."
            )
