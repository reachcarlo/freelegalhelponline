"""Tests for the LLM client wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from employee_help.generation.llm import LLMClient, LLMResponse, StreamChunk


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_token_usage(self):
        resp = LLMResponse(
            text="test",
            model="claude-haiku-4-5-20251001",
            input_tokens=100,
            output_tokens=50,
        )
        assert resp.token_usage.input_tokens == 100
        assert resp.token_usage.output_tokens == 50
        assert resp.token_usage.total_tokens == 150

    def test_cost_estimate(self):
        resp = LLMResponse(
            text="test",
            model="claude-sonnet-4-6",
            input_tokens=1000,
            output_tokens=500,
        )
        # Cost should be positive
        assert resp.token_usage.cost_estimate > 0


class TestStreamChunk:
    """Tests for StreamChunk dataclass."""

    def test_creation(self):
        chunk = StreamChunk(text="hello")
        assert chunk.text == "hello"
        assert chunk.is_final is False

    def test_final_chunk(self):
        chunk = StreamChunk(
            text="",
            is_final=True,
            input_tokens=100,
            output_tokens=50,
        )
        assert chunk.is_final is True
        assert chunk.input_tokens == 100


class TestLLMClient:
    """Tests for LLMClient with mocked Anthropic SDK."""

    def test_requires_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            # Remove ANTHROPIC_API_KEY if it exists
            import os
            env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
            with patch.dict("os.environ", env, clear=True):
                with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                    LLMClient()

    def test_accepts_explicit_api_key(self):
        client = LLMClient(api_key="test-key")
        assert client.api_key == "test-key"

    def test_model_for_mode_consumer(self):
        client = LLMClient(api_key="test-key")
        model = client.model_for_mode("consumer")
        assert "haiku" in model

    def test_model_for_mode_attorney(self):
        client = LLMClient(api_key="test-key")
        model = client.model_for_mode("attorney")
        assert "sonnet" in model

    def test_model_override(self):
        client = LLMClient(api_key="test-key", default_model="custom-model")
        assert client.model_for_mode("consumer") == "custom-model"
        assert client.model_for_mode("attorney") == "custom-model"

    def test_generate_calls_api(self):
        client = LLMClient(api_key="test-key")

        # Mock the anthropic client
        mock_anthropic = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Test answer")]
        mock_response.content[0].citations = None
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)
        mock_anthropic.messages.create.return_value = mock_response
        client._client = mock_anthropic

        response = client.generate(
            system_prompt="You are helpful.",
            user_message="What is FEHA?",
            mode="consumer",
        )

        assert isinstance(response, LLMResponse)
        assert response.text == "Test answer"
        assert response.input_tokens == 100
        assert response.output_tokens == 50
        mock_anthropic.messages.create.assert_called_once()

    def test_generate_extracts_citations(self):
        client = LLMClient(api_key="test-key")

        mock_anthropic = MagicMock()
        mock_citation = MagicMock()
        mock_citation.type = "char_location"
        mock_citation.cited_text = "test citation"
        mock_citation.document_index = 0
        mock_citation.start_char_index = 10
        mock_citation.end_char_index = 20

        mock_block = MagicMock()
        mock_block.type = "text"
        mock_block.text = "Answer with citation"
        mock_block.citations = [mock_citation]

        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_response.usage = MagicMock(input_tokens=50, output_tokens=30)
        mock_anthropic.messages.create.return_value = mock_response
        client._client = mock_anthropic

        response = client.generate(
            system_prompt="test",
            user_message="test",
        )

        assert len(response.citations) == 1
        assert response.citations[0]["cited_text"] == "test citation"
