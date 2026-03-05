"""LLM client wrapper for Claude API with Citations API and streaming support."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Iterator

import structlog

from employee_help.generation.models import TokenUsage

logger = structlog.get_logger()

# Default model mapping by mode
DEFAULT_MODELS = {
    "consumer": "claude-haiku-4-5-20251001",
    "attorney": "claude-sonnet-4-6",
}


@dataclass
class LLMResponse:
    """Response from a single LLM call."""

    text: str
    citations: list[dict[str, Any]] = field(default_factory=list)
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0

    @property
    def token_usage(self) -> TokenUsage:
        return TokenUsage(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            model=self.model,
        )


@dataclass
class StreamChunk:
    """A chunk from a streaming response."""

    text: str = ""
    is_final: bool = False
    citations: list[dict[str, Any]] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""


class LLMClient:
    """Wrapper around the Anthropic Claude API with Citations API and streaming.

    Supports document-based citation tracking via the Claude Citations API.
    Each retrieved chunk is passed as a document content block, enabling
    the model to return structured citations pointing back to source chunks.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        consumer_model: str | None = None,
        attorney_model: str | None = None,
        default_model: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is required. "
                "Set it with: export ANTHROPIC_API_KEY=your-key-here"
            )

        self._model_map = {
            "consumer": consumer_model or DEFAULT_MODELS["consumer"],
            "attorney": attorney_model or DEFAULT_MODELS["attorney"],
        }
        self.default_model = default_model
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = None
        self.logger = structlog.get_logger(__name__)

    def _get_client(self):
        """Lazy-initialize the Anthropic client."""
        if self._client is not None:
            return self._client

        try:
            import anthropic

            self._client = anthropic.Anthropic(
                api_key=self.api_key,
                timeout=self.timeout,
                max_retries=self.max_retries,
            )
            return self._client
        except ImportError:
            raise ImportError(
                "anthropic is required for answer generation. "
                "Install with: uv pip install -e '.[rag]'"
            )

    def model_for_mode(self, mode: str) -> str:
        """Get the appropriate model for a given mode."""
        if self.default_model:
            return self.default_model
        return self._model_map.get(mode, self._model_map["consumer"])

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        *,
        model: str | None = None,
        mode: str = "consumer",
        max_tokens: int = 2000,
        temperature: float = 0.0,
        document_blocks: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Generate a response synchronously with optional Citations API support.

        When document_blocks are provided, they are included in the user message
        content array as document content blocks. The Claude Citations API will
        return structured citations pointing to these documents.

        Args:
            system_prompt: System prompt text.
            user_message: User question text (without context -- context is in documents).
            model: Specific model to use (overrides mode-based selection).
            mode: "consumer" or "attorney" for model selection.
            max_tokens: Maximum output tokens.
            temperature: Sampling temperature (0.0 for factual/legal).
            document_blocks: List of Citation API document content blocks.

        Returns:
            LLMResponse with text, citations, and usage info.
        """
        client = self._get_client()
        selected_model = model or self.model_for_mode(mode)

        # Build user message content
        user_content = self._build_user_content(user_message, document_blocks)

        start_time = time.monotonic()

        try:
            response = client.messages.create(
                model=selected_model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
            )
        except Exception as e:
            self._handle_api_error(e)
            raise

        duration_ms = int((time.monotonic() - start_time) * 1000)

        # Extract text and citations from response
        text_parts = []
        citations = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
                # Extract citations from Citations API response
                if hasattr(block, "citations") and block.citations:
                    for cit in block.citations:
                        citations.append(self._parse_citation(cit))

        result = LLMResponse(
            text="\n".join(text_parts),
            citations=citations,
            model=selected_model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            duration_ms=duration_ms,
        )

        self.logger.info(
            "llm_response",
            model=selected_model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            citations_count=len(citations),
            duration_ms=duration_ms,
        )

        return result

    def generate_stream(
        self,
        system_prompt: str,
        user_message: str,
        *,
        model: str | None = None,
        mode: str = "consumer",
        max_tokens: int = 2000,
        temperature: float = 0.0,
        document_blocks: list[dict[str, Any]] | None = None,
    ) -> Iterator[StreamChunk]:
        """Generate a streaming response with Citations API support.

        Yields StreamChunk objects as tokens arrive. The final chunk
        has is_final=True and includes token usage and accumulated citations.

        Args:
            system_prompt: System prompt text.
            user_message: User question text.
            model: Specific model to use.
            mode: "consumer" or "attorney".
            max_tokens: Maximum output tokens.
            temperature: Sampling temperature.
            document_blocks: Citation API document content blocks.

        Yields:
            StreamChunk objects with incremental text.
        """
        client = self._get_client()
        selected_model = model or self.model_for_mode(mode)

        user_content = self._build_user_content(user_message, document_blocks)

        try:
            with client.messages.stream(
                model=selected_model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
            ) as stream:
                for text in stream.text_stream:
                    yield StreamChunk(text=text)

                # Get final message with full content and usage
                final_message = stream.get_final_message()

                # Extract citations from final message
                citations = []
                for block in final_message.content:
                    if block.type == "text":
                        if hasattr(block, "citations") and block.citations:
                            for cit in block.citations:
                                citations.append(self._parse_citation(cit))

                yield StreamChunk(
                    text="",
                    is_final=True,
                    citations=citations,
                    input_tokens=final_message.usage.input_tokens,
                    output_tokens=final_message.usage.output_tokens,
                    model=selected_model,
                )
        except Exception as e:
            self._handle_api_error(e)
            raise

    def generate_stream_multiturn(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        mode: str = "consumer",
        max_tokens: int = 2000,
        temperature: float = 0.0,
    ) -> Iterator[StreamChunk]:
        """Generate a streaming response from a pre-built messages array.

        Used for multi-turn conversations where the messages array includes
        conversation history and the current turn with document blocks.

        Args:
            system_prompt: System prompt text.
            messages: Pre-built messages array with alternating user/assistant turns.
            model: Specific model to use.
            mode: "consumer" or "attorney".
            max_tokens: Maximum output tokens.
            temperature: Sampling temperature.

        Yields:
            StreamChunk objects with incremental text.
        """
        client = self._get_client()
        selected_model = model or self.model_for_mode(mode)

        try:
            with client.messages.stream(
                model=selected_model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield StreamChunk(text=text)

                final_message = stream.get_final_message()

                citations = []
                for block in final_message.content:
                    if block.type == "text":
                        if hasattr(block, "citations") and block.citations:
                            for cit in block.citations:
                                citations.append(self._parse_citation(cit))

                yield StreamChunk(
                    text="",
                    is_final=True,
                    citations=citations,
                    input_tokens=final_message.usage.input_tokens,
                    output_tokens=final_message.usage.output_tokens,
                    model=selected_model,
                )
        except Exception as e:
            self._handle_api_error(e)
            raise

    def generate_with_tools(
        self,
        system_prompt: str,
        user_message: str,
        tools: list[dict[str, Any]],
        *,
        model: str | None = None,
        mode: str = "consumer",
        max_tokens: int = 4096,
        temperature: float = 0.0,
        tool_choice: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Generate a response using Claude tool_use for structured output.

        Forces the model to call a tool, returning guaranteed valid JSON.
        Used by the objection analyzer for structured analysis results.

        Args:
            system_prompt: System prompt text.
            user_message: User message text.
            tools: Tool definitions (name, description, input_schema).
            model: Specific model to use.
            mode: "consumer" or "attorney" for model selection.
            max_tokens: Maximum output tokens.
            temperature: Sampling temperature.
            tool_choice: Tool choice constraint. Defaults to {"type": "any"}.

        Returns:
            Dict with keys: tool_name, tool_input, input_tokens, output_tokens,
            model, duration_ms.
        """
        client = self._get_client()
        selected_model = model or self.model_for_mode(mode)

        if tool_choice is None:
            tool_choice = {"type": "any"}

        start_time = time.monotonic()

        try:
            response = client.messages.create(
                model=selected_model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
                tools=tools,
                tool_choice=tool_choice,
            )
        except Exception as e:
            self._handle_api_error(e)
            raise

        duration_ms = int((time.monotonic() - start_time) * 1000)

        # Extract tool use block
        tool_name = ""
        tool_input: dict[str, Any] = {}
        for block in response.content:
            if block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input
                break

        self.logger.info(
            "llm_tool_response",
            model=selected_model,
            tool_name=tool_name,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            duration_ms=duration_ms,
        )

        return {
            "tool_name": tool_name,
            "tool_input": tool_input,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "model": selected_model,
            "duration_ms": duration_ms,
        }

    def _build_user_content(
        self,
        user_message: str,
        document_blocks: list[dict[str, Any]] | None,
    ) -> str | list[dict[str, Any]]:
        """Build the user content for the API call.

        If document_blocks are provided, returns a list of content blocks
        (documents + text question) for the Citations API.
        Otherwise, returns the user message as plain text.
        """
        if not document_blocks:
            return user_message

        # Documents come first, then the user question
        content: list[dict[str, Any]] = []
        content.extend(document_blocks)
        content.append({"type": "text", "text": user_message})
        return content

    def _parse_citation(self, citation) -> dict[str, Any]:
        """Parse a citation object from the Claude API response."""
        result: dict[str, Any] = {
            "type": getattr(citation, "type", "unknown"),
            "cited_text": getattr(citation, "cited_text", ""),
        }

        # char_location citations
        if hasattr(citation, "document_index"):
            result["document_index"] = citation.document_index
        if hasattr(citation, "start_char_index"):
            result["start_char_index"] = citation.start_char_index
        if hasattr(citation, "end_char_index"):
            result["end_char_index"] = citation.end_char_index

        # content_block_location citations
        if hasattr(citation, "content_block_index"):
            result["content_block_index"] = citation.content_block_index

        return result

    def _handle_api_error(self, error: Exception) -> None:
        """Log API errors with appropriate severity."""
        try:
            import anthropic
        except ImportError:
            self.logger.error("llm_error", error=str(error))
            return

        if isinstance(error, anthropic.AuthenticationError):
            self.logger.error(
                "llm_auth_error",
                error="Invalid API key. Check ANTHROPIC_API_KEY.",
            )
        elif isinstance(error, anthropic.RateLimitError):
            self.logger.warning("llm_rate_limited", error=str(error))
        elif isinstance(error, anthropic.APIConnectionError):
            self.logger.error(
                "llm_connection_error",
                error="Cannot connect to Anthropic API. Check network.",
            )
        elif isinstance(error, anthropic.APITimeoutError):
            self.logger.error(
                "llm_timeout",
                error=f"Request timed out after {self.timeout}s.",
            )
        elif isinstance(error, anthropic.BadRequestError):
            self.logger.error("llm_bad_request", error=str(error))
        else:
            self.logger.error("llm_error", error=str(error), type=type(error).__name__)
