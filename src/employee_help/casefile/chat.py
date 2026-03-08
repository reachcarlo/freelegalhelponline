"""CaseChatService: dual-context retrieval combining case files with KB.

Searches both the case-scoped vector store (uploaded documents) and the
knowledge base vector store (employment law), then builds a unified prompt
with case file context, legal research context, and attorney notes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterator

import structlog

if TYPE_CHECKING:
    from employee_help.casefile.case_vector_store import CaseVectorStore
    from employee_help.generation.llm import LLMClient
    from employee_help.generation.prompts import PromptBuilder
    from employee_help.retrieval.embedder import EmbeddingService
    from employee_help.retrieval.service import RetrievalResult, RetrievalService
    from employee_help.storage.case_storage import CaseStorage

logger = structlog.get_logger(__name__)

# Default retrieval limits
CASE_TOP_K = 10
KB_TOP_K = 5


@dataclass
class CaseRetrievalResult:
    """A retrieval result from case file embeddings."""

    chunk_id: str
    file_id: str
    case_id: str
    content: str
    heading_path: str
    file_type: str
    original_filename: str
    relevance_score: float
    content_hash: str = ""


class CaseChatService:
    """Dual-context chat service for LITIGAGENT case conversations.

    Combines case file retrieval (uploaded documents) with knowledge base
    retrieval (employment law) and attorney notes to provide contextual
    answers grounded in both case facts and legal authority.
    """

    def __init__(
        self,
        case_vector_store: CaseVectorStore,
        embedding_service: EmbeddingService,
        retrieval_service: RetrievalService,
        llm_client: LLMClient,
        prompt_builder: PromptBuilder,
        case_storage: CaseStorage,
        *,
        case_top_k: int = CASE_TOP_K,
        kb_top_k: int = KB_TOP_K,
    ) -> None:
        self.case_vector_store = case_vector_store
        self.embedding_service = embedding_service
        self.retrieval_service = retrieval_service
        self.llm_client = llm_client
        self.prompt_builder = prompt_builder
        self.case_storage = case_storage
        self.case_top_k = case_top_k
        self.kb_top_k = kb_top_k
        self.logger = structlog.get_logger(__name__)

    # ── Retrieval ───────────────────────────────────────────────

    def retrieve_for_case(
        self,
        query: str,
        case_id: str,
    ) -> tuple[list[CaseRetrievalResult], list[RetrievalResult]]:
        """Search both case files and knowledge base.

        Embeds the query once and reuses the vector for both searches.
        Case files are searched in attorney mode with case_id scoping.
        KB is searched in attorney mode (always for LITIGAGENT).

        Returns:
            Tuple of (case_results, kb_results).
        """
        # Embed the query once (reused for both searches)
        query_embedding = self.embedding_service.embed_query(query)

        # 1. Search case embeddings (case-scoped)
        raw_case_results = self.case_vector_store.search_hybrid(
            case_id=case_id,
            query_text=query,
            query_vector=query_embedding.dense_vector,
            top_k=self.case_top_k,
        )
        case_results = self._to_case_results(raw_case_results)

        # 2. Search knowledge base (attorney mode)
        kb_results = self.retrieval_service.retrieve(
            query=query,
            mode="attorney",
            top_k=self.kb_top_k,
        )

        self.logger.info(
            "dual_retrieval_complete",
            query=query[:80],
            case_id=case_id,
            case_results=len(case_results),
            kb_results=len(kb_results),
        )

        return case_results, kb_results

    # ── Notes ───────────────────────────────────────────────────

    def get_case_notes(self, case_id: str) -> list[dict[str, Any]]:
        """Fetch all notes for a case, with linked filename if applicable."""
        notes = self.case_storage.list_notes(case_id)
        result = []
        for note in notes:
            entry: dict[str, Any] = {
                "content": note.content,
                "file_id": note.file_id,
                "filename": None,
            }
            if note.file_id:
                cf = self.case_storage.get_case_file(note.file_id)
                if cf is not None:
                    entry["filename"] = cf.original_filename
            result.append(entry)
        return result

    # ── Prompt building ─────────────────────────────────────────

    def build_case_document_blocks(
        self,
        case_results: list[CaseRetrievalResult],
        kb_results: list[RetrievalResult],
    ) -> tuple[list[dict[str, Any]], list[Any]]:
        """Build Citations API document blocks for both case files and KB.

        Case file blocks come first (primary context), then KB blocks
        (legal research context). Returns the combined block list and
        the ordered context list for citation mapping.
        """
        blocks: list[dict[str, Any]] = []
        context_order: list[Any] = []

        # Case file blocks (primary context)
        for result in case_results:
            title = result.original_filename
            if result.heading_path:
                title += f" — {result.heading_path}"

            meta = (
                f"[Case File | {result.original_filename} | "
                f"Type: {result.file_type}]"
            )
            content_with_meta = f"{meta}\n\n{result.content}"

            blocks.append({
                "type": "document",
                "source": {
                    "type": "content",
                    "content": [{"type": "text", "text": content_with_meta}],
                },
                "title": title,
                "citations": {"enabled": True},
            })
            context_order.append(result)

        # KB blocks (legal research context) — reuse PromptBuilder logic
        kb_blocks = self.prompt_builder._build_document_blocks(kb_results)
        blocks.extend(kb_blocks)
        context_order.extend(kb_results)

        return blocks, context_order

    def build_case_system_prompt(
        self,
        case_notes: list[dict[str, Any]],
    ) -> str:
        """Build the system prompt for case chat.

        Uses the casefile_system.j2 template if available,
        otherwise falls back to an inline prompt.
        """
        try:
            template_text = self.prompt_builder._load_template(
                "casefile_system.j2"
            )
            return self.prompt_builder._render_template(
                template_text,
                case_notes=case_notes,
            )
        except FileNotFoundError:
            return self._fallback_system_prompt(case_notes)

    def _fallback_system_prompt(
        self, case_notes: list[dict[str, Any]]
    ) -> str:
        """Inline system prompt when casefile_system.j2 is not yet created."""
        lines = [
            "You are LITIGAGENT, an AI legal associate reviewing case files "
            "for a California litigation attorney.",
            "",
            "## Your Knowledge",
            "You have access to two types of sources:",
            "1. **Case Files**: Documents uploaded by the attorney for this "
            "specific case.",
            "2. **Legal Research**: California employment law statutes, "
            "regulations, agency guidance, CACI jury instructions, and "
            "case law.",
            "",
        ]

        if case_notes:
            lines.append("## Attorney Notes")
            lines.append(
                "The attorney has provided the following context and "
                "annotations:"
            )
            lines.append("")
            for note in case_notes:
                if note.get("filename"):
                    lines.append(f"[Note for: {note['filename']}]")
                else:
                    lines.append("[General Case Note]")
                lines.append(note["content"])
                lines.append("")

        lines.extend([
            "## Instructions",
            "- When citing case files, reference the specific document "
            "name and page/section.",
            "- When citing legal authority, provide full statutory citations.",
            "- Distinguish clearly between what the case files say (facts) "
            "and what the law says (legal analysis).",
            "- The attorney's notes represent their professional judgment "
            "— incorporate them into your analysis.",
            "- If asked to draft work product, use the case files as factual "
            "foundation and the legal research for legal authority.",
            "- This AI-generated analysis should be independently verified. "
            "It does not constitute legal advice.",
        ])

        return "\n".join(lines)

    # ── Generation ──────────────────────────────────────────────

    def generate_stream(
        self,
        query: str,
        case_id: str,
    ) -> tuple[
        Iterator[str],
        list[CaseRetrievalResult],
        list[RetrievalResult],
        list[dict[str, Any]],
    ]:
        """Full streaming pipeline: retrieve -> prompt -> generate.

        Returns:
            Tuple of (text_stream, case_results, kb_results, stream_metadata).
            stream_metadata is populated after consuming the stream.
        """
        from employee_help.retrieval.service import RetrievalResult as RR

        # 1. Retrieve from both sources
        case_results, kb_results = self.retrieve_for_case(query, case_id)

        if not case_results and not kb_results:
            def empty_stream() -> Iterator[str]:
                yield (
                    "I couldn't find relevant information in either the "
                    "case files or the legal knowledge base for this query. "
                    "Please try rephrasing your question or ensure that "
                    "relevant documents have been uploaded and processed."
                )

            empty_kb: list[RR] = []
            return empty_stream(), [], empty_kb, []

        # 2. Get case notes
        case_notes = self.get_case_notes(case_id)

        # 3. Build system prompt
        system_prompt = self.build_case_system_prompt(case_notes)

        # 4. Build document blocks
        document_blocks, _context_order = self.build_case_document_blocks(
            case_results, kb_results,
        )

        # 5. Stream from LLM (always attorney mode)
        stream_metadata: list[dict[str, Any]] = []

        def text_stream() -> Iterator[str]:
            for chunk in self.llm_client.generate_stream(
                system_prompt=system_prompt,
                user_message=query,
                mode="attorney",
                document_blocks=document_blocks,
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

        return text_stream(), case_results, kb_results, stream_metadata

    def generate_stream_multiturn(
        self,
        query: str,
        case_id: str,
        conversation_history: list[dict[str, str]] | None = None,
        turn_number: int = 1,
        max_turns: int = 5,
    ) -> tuple[
        Iterator[str],
        list[CaseRetrievalResult],
        list[RetrievalResult],
        list[dict[str, Any]],
    ]:
        """Multi-turn streaming with dual-context retrieval.

        Supports conversation history with fresh retrieval on each turn.
        Short follow-up queries are expanded with the original question.
        """
        from employee_help.retrieval.service import RetrievalResult as RR

        history = conversation_history or []

        # Expand short follow-ups for better retrieval
        retrieval_query = query
        if turn_number > 1 and len(query.split()) < 6 and history:
            for turn in history:
                if turn["role"] == "user":
                    retrieval_query = f"{turn['content']} {query}"
                    break

        # 1. Retrieve
        case_results, kb_results = self.retrieve_for_case(
            retrieval_query, case_id
        )

        if not case_results and not kb_results:
            def empty_stream() -> Iterator[str]:
                yield (
                    "I couldn't find relevant information for this query. "
                    "Please try rephrasing your question."
                )

            empty_kb: list[RR] = []
            return empty_stream(), [], empty_kb, []

        # 2. Build context
        case_notes = self.get_case_notes(case_id)
        system_prompt = self.build_case_system_prompt(case_notes)
        document_blocks, _context_order = self.build_case_document_blocks(
            case_results, kb_results,
        )

        # 3. Build multi-turn messages
        trimmed_history = self.prompt_builder._trim_history(history, 2000)
        messages: list[dict[str, Any]] = []
        for turn in trimmed_history:
            messages.append({"role": turn["role"], "content": turn["content"]})

        # Current turn with document blocks
        current_content: list[dict[str, Any]] = list(document_blocks)
        current_content.append({"type": "text", "text": query})
        messages.append({"role": "user", "content": current_content})

        # 4. Stream
        stream_metadata: list[dict[str, Any]] = []

        def text_stream() -> Iterator[str]:
            for chunk in self.llm_client.generate_stream_multiturn(
                system_prompt=system_prompt,
                messages=messages,
                mode="attorney",
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

        return text_stream(), case_results, kb_results, stream_metadata

    # ── Internals ───────────────────────────────────────────────

    def _to_case_results(
        self, raw_results: list[dict[str, Any]]
    ) -> list[CaseRetrievalResult]:
        """Convert raw LanceDB results to CaseRetrievalResult objects."""
        results = []
        for row in raw_results:
            score = row.get("_relevance_score") or row.get("_distance")
            if score is None:
                score = 0.0
            # LanceDB _distance is cosine distance; convert to similarity
            if "_distance" in row and "_relevance_score" not in row:
                score = max(0.0, 1.0 - float(score))
            else:
                score = float(score)

            results.append(
                CaseRetrievalResult(
                    chunk_id=row.get("chunk_id", ""),
                    file_id=row.get("file_id", ""),
                    case_id=row.get("case_id", ""),
                    content=row.get("content", ""),
                    heading_path=row.get("heading_path", ""),
                    file_type=row.get("file_type", ""),
                    original_filename=row.get("original_filename", ""),
                    relevance_score=score,
                    content_hash=row.get("content_hash", ""),
                )
            )
        return results
