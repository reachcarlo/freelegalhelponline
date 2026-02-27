"""Prompt builder for assembling system prompts with Citations API document blocks.

Generates structured document content blocks for the Claude Citations API,
where each retrieved chunk becomes a citable document. This enables the model
to return structured citations pointing back to specific source chunks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from employee_help.retrieval.service import RetrievalResult

logger = structlog.get_logger()

# Rough token estimation: ~4 chars per token
CHARS_PER_TOKEN = 4


@dataclass
class PromptBundle:
    """Assembled prompt ready for LLM call.

    Contains:
    - system_prompt: The mode-specific system instructions
    - user_message: The user's question (without context)
    - document_blocks: Citation API document blocks for each retrieved chunk
    - context_chunks: The retrieval results used (for post-processing)
    - messages: Pre-built messages array for multi-turn (None for single-turn)
    """

    system_prompt: str
    user_message: str
    document_blocks: list[dict[str, Any]] = field(default_factory=list)
    context_chunks: list[RetrievalResult] = field(default_factory=list)
    total_tokens_estimate: int = 0
    messages: list[dict[str, Any]] | None = None


class PromptBuilder:
    """Builds prompts from Jinja2 templates and retrieval results.

    Generates Citations API document blocks from retrieved chunks, enabling
    structured citation tracking in the Claude API response.
    """

    def __init__(
        self,
        prompts_dir: str = "config/prompts",
        max_context_tokens: int = 6000,
        rag_config: dict | None = None,
    ) -> None:
        self.prompts_dir = Path(prompts_dir)
        self.max_context_tokens = max_context_tokens
        self._templates: dict[str, str] = {}
        self._jinja_env = None
        self._rag_config = rag_config or {}
        self.logger = structlog.get_logger(__name__)

    def _get_jinja_env(self):
        """Get or create a cached Jinja2 environment."""
        if self._jinja_env is not None:
            return self._jinja_env

        try:
            import jinja2
        except ImportError:
            raise ImportError(
                "jinja2 is required for prompt rendering. "
                "Install with: uv pip install -e '.[rag]'"
            )

        self._jinja_env = jinja2.Environment(
            undefined=jinja2.StrictUndefined,
            autoescape=False,
        )
        return self._jinja_env

    def _load_template(self, name: str) -> str:
        """Load a template file, with caching."""
        if name in self._templates:
            return self._templates[name]

        path = self.prompts_dir / name
        if not path.exists():
            raise FileNotFoundError(f"Prompt template not found: {path}")

        template_text = path.read_text()
        self._templates[name] = template_text
        return template_text

    def _render_template(self, template_text: str, **kwargs) -> str:
        """Render a Jinja2 template with the given context."""
        env = self._get_jinja_env()
        template = env.from_string(template_text)
        return template.render(**kwargs)

    def _get_tone_config(self, mode: str) -> dict:
        """Get tone/response format config for a mode."""
        tone = self._rag_config.get("tone", {})
        return tone.get(mode, {})

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for a text."""
        return max(1, len(text) // CHARS_PER_TOKEN)

    def build_prompt(
        self,
        query: str,
        mode: str,
        retrieval_results: list[RetrievalResult],
    ) -> PromptBundle:
        """Build a complete prompt bundle with Citations API document blocks.

        Each retrieved chunk becomes a document content block that the Claude
        Citations API can reference in its response. This enables structured
        citation tracking without post-hoc regex-based citation validation.

        Args:
            query: User's question.
            mode: "consumer" or "attorney".
            retrieval_results: Ranked retrieval results for context.

        Returns:
            PromptBundle with system prompt, user message, and document blocks.
        """
        # Load and render system prompt template
        template_name = f"{mode}_system.j2"
        system_template = self._load_template(template_name)
        tone_config = self._get_tone_config(mode)
        system_prompt = self._render_template(system_template, tone=tone_config)

        # Select chunks that fit within the token budget
        context_chunks = self._fit_to_budget(retrieval_results)

        # Build Citations API document blocks
        document_blocks = self._build_document_blocks(context_chunks)

        # Build user message (just the question; context is in document blocks)
        user_message = query

        total_estimate = (
            self._estimate_tokens(system_prompt)
            + self._estimate_tokens(user_message)
            + sum(self._estimate_tokens(c.content) for c in context_chunks)
        )

        self.logger.debug(
            "prompt_built",
            mode=mode,
            context_chunks=len(context_chunks),
            document_blocks=len(document_blocks),
            total_tokens_estimate=total_estimate,
        )

        return PromptBundle(
            system_prompt=system_prompt,
            user_message=user_message,
            document_blocks=document_blocks,
            context_chunks=context_chunks,
            total_tokens_estimate=total_estimate,
        )

    def _build_document_blocks(
        self,
        results: list[RetrievalResult],
    ) -> list[dict[str, Any]]:
        """Build Citations API document content blocks from retrieval results.

        Each chunk becomes a document with:
        - type: "document"
        - source: content block with the chunk text
        - title: citation or heading path for identification
        - context: metadata (category, URL) for the model's reference
        - citations: enabled for citation tracking
        """
        blocks: list[dict[str, Any]] = []

        for i, result in enumerate(results):
            # Build a descriptive title
            title = result.citation or result.heading_path or f"Source {i + 1}"

            # Build metadata context string
            meta_parts = [f"Category: {result.content_category}"]
            if result.citation:
                meta_parts.append(f"Citation: {result.citation}")
            if result.source_url:
                meta_parts.append(f"URL: {result.source_url}")

            # Content with metadata prefix
            content_with_meta = (
                f"[{' | '.join(meta_parts)}]\n\n{result.content}"
            )

            block: dict[str, Any] = {
                "type": "document",
                "source": {
                    "type": "content",
                    "content": [{"type": "text", "text": content_with_meta}],
                },
                "title": title,
                "citations": {"enabled": True},
            }

            blocks.append(block)

        return blocks

    def build_prompt_multiturn(
        self,
        query: str,
        mode: str,
        retrieval_results: list[RetrievalResult],
        conversation_history: list[dict[str, str]],
        turn_number: int,
        max_turns: int,
        history_token_budget: int = 2000,
    ) -> PromptBundle:
        """Build a multi-turn prompt with conversation history and fresh retrieval.

        Historical turns are sent as plain text (no document blocks).
        Only the current turn gets fresh document blocks from retrieval.
        History is trimmed to fit within history_token_budget.

        Args:
            query: Current user question.
            mode: "consumer" or "attorney".
            retrieval_results: Fresh retrieval results for the current turn.
            conversation_history: List of {"role": "user"|"assistant", "content": str}.
            turn_number: Current turn (1-based).
            max_turns: Maximum allowed turns for this mode.
            history_token_budget: Token budget for conversation history.

        Returns:
            PromptBundle with messages array populated for multi-turn.
        """
        turns_remaining = max(0, max_turns - turn_number)

        # Render system prompt with turn context and tone config
        template_name = f"{mode}_system.j2"
        system_template = self._load_template(template_name)
        tone_config = self._get_tone_config(mode)
        system_prompt = self._render_template(
            system_template,
            turn_number=turn_number,
            max_turns=max_turns,
            turns_remaining=turns_remaining,
            tone=tone_config,
        )

        # Fit retrieval results to budget
        context_chunks = self._fit_to_budget(retrieval_results)
        document_blocks = self._build_document_blocks(context_chunks)

        # Trim history to fit token budget (keep first turn + most recent)
        trimmed_history = self._trim_history(conversation_history, history_token_budget)

        # Build messages array: historical turns as plain text, current with doc blocks
        messages: list[dict[str, Any]] = []
        for turn in trimmed_history:
            messages.append({
                "role": turn["role"],
                "content": turn["content"],
            })

        # Current turn: document blocks + user query
        current_content: list[dict[str, Any]] = []
        current_content.extend(document_blocks)
        current_content.append({"type": "text", "text": query})
        messages.append({"role": "user", "content": current_content})

        total_estimate = (
            self._estimate_tokens(system_prompt)
            + sum(self._estimate_tokens(t["content"]) for t in trimmed_history)
            + self._estimate_tokens(query)
            + sum(self._estimate_tokens(c.content) for c in context_chunks)
        )

        self.logger.debug(
            "multiturn_prompt_built",
            mode=mode,
            turn_number=turn_number,
            max_turns=max_turns,
            history_turns=len(trimmed_history),
            context_chunks=len(context_chunks),
            total_tokens_estimate=total_estimate,
        )

        return PromptBundle(
            system_prompt=system_prompt,
            user_message=query,
            document_blocks=document_blocks,
            context_chunks=context_chunks,
            total_tokens_estimate=total_estimate,
            messages=messages,
        )

    def _trim_history(
        self,
        history: list[dict[str, str]],
        token_budget: int,
    ) -> list[dict[str, str]]:
        """Trim conversation history to fit within token budget.

        Strategy: always keep the first user/assistant pair, then add
        the most recent pairs until the budget is exhausted.
        """
        if not history:
            return []

        total_tokens = sum(self._estimate_tokens(t["content"]) for t in history)
        if total_tokens <= token_budget:
            return list(history)

        # Keep first pair (turns 0-1) + most recent pairs
        first_pair = history[:2] if len(history) >= 2 else list(history)
        first_pair_tokens = sum(self._estimate_tokens(t["content"]) for t in first_pair)

        if first_pair_tokens >= token_budget:
            # Even the first pair is too large; truncate content
            return first_pair

        remaining_budget = token_budget - first_pair_tokens
        remaining = history[2:]

        # Add from the end (most recent)
        kept_tail: list[dict[str, str]] = []
        for turn in reversed(remaining):
            turn_tokens = self._estimate_tokens(turn["content"])
            if turn_tokens > remaining_budget:
                break
            kept_tail.insert(0, turn)
            remaining_budget -= turn_tokens

        return first_pair + kept_tail

    def _fit_to_budget(
        self,
        results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        """Select results that fit within the context token budget.

        Results are already sorted by relevance (most relevant first).
        We add results until we exceed the token budget.
        """
        selected: list[RetrievalResult] = []
        total_tokens = 0

        for result in results:
            chunk_tokens = self._estimate_tokens(result.content)
            # Add overhead for metadata in document block (~50 tokens per chunk)
            chunk_tokens += 50

            if total_tokens + chunk_tokens > self.max_context_tokens:
                # If we have no results yet, include at least one
                if not selected:
                    selected.append(result)
                break

            selected.append(result)
            total_tokens += chunk_tokens

        return selected
