"""Tests for the BaseAgent class — Claude calling infrastructure."""
import json
from unittest.mock import MagicMock, patch

import pytest

from src.agents.base import BaseAgent


class TestParseJsonResponse:
    """Test JSON extraction from various Claude response formats."""

    def test_parses_raw_json(self, mock_claude_client):
        agent = BaseAgent(mock_claude_client)
        result = agent._parse_json_response('{"key": "value", "num": 42}')
        assert result == {"key": "value", "num": 42}

    def test_parses_markdown_fenced_json(self, mock_claude_client):
        agent = BaseAgent(mock_claude_client)
        text = '```json\n{"key": "value"}\n```'
        result = agent._parse_json_response(text)
        assert result == {"key": "value"}

    def test_parses_json_with_surrounding_text(self, mock_claude_client):
        agent = BaseAgent(mock_claude_client)
        text = 'Here is the analysis:\n```json\n{"recommendation": "BUY"}\n```\nDone.'
        result = agent._parse_json_response(text)
        assert result == {"recommendation": "BUY"}

    def test_parses_bare_fenced_json(self, mock_claude_client):
        """Handles ``` fences without json language tag."""
        agent = BaseAgent(mock_claude_client)
        text = '```\n{"key": "value"}\n```'
        result = agent._parse_json_response(text)
        assert result == {"key": "value"}

    def test_returns_empty_dict_on_invalid_json(self, mock_claude_client):
        agent = BaseAgent(mock_claude_client)
        result = agent._parse_json_response("not json at all")
        assert result == {}

    def test_parses_nested_json(self, mock_claude_client):
        agent = BaseAgent(mock_claude_client)
        data = {"outer": {"inner": [1, 2, 3]}, "flag": True}
        result = agent._parse_json_response(json.dumps(data))
        assert result == data


class TestCallClaude:
    """Test Claude API calling with retry logic."""

    def test_successful_call(self, mock_claude_client):
        response_data = {"recommendation": "BUY", "confidence": 75}
        mock_claude_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text=json.dumps(response_data))],
            usage=MagicMock(input_tokens=100, output_tokens=50),
        )

        agent = BaseAgent(mock_claude_client)
        result = agent._call_claude("You are an analyst.", "Analyze AAPL")
        assert result == response_data

    def test_retries_on_parse_failure_then_succeeds(self, mock_claude_client):
        """Retries up to 2x when JSON parsing fails."""
        bad_response = MagicMock(
            content=[MagicMock(text="not json")],
            usage=MagicMock(input_tokens=100, output_tokens=50),
        )
        good_response = MagicMock(
            content=[MagicMock(text='{"key": "value"}')],
            usage=MagicMock(input_tokens=100, output_tokens=50),
        )
        mock_claude_client.messages.create.side_effect = [bad_response, good_response]

        agent = BaseAgent(mock_claude_client)
        result = agent._call_claude("system", "user")
        assert result == {"key": "value"}
        assert mock_claude_client.messages.create.call_count == 2

    def test_returns_empty_after_all_retries_fail(self, mock_claude_client):
        """Returns empty dict after exhausting retries."""
        bad_response = MagicMock(
            content=[MagicMock(text="still not json")],
            usage=MagicMock(input_tokens=100, output_tokens=50),
        )
        mock_claude_client.messages.create.return_value = bad_response

        agent = BaseAgent(mock_claude_client)
        result = agent._call_claude("system", "user")
        assert result == {}
        # Initial + 2 retries = 3 calls
        assert mock_claude_client.messages.create.call_count == 3

    def test_retries_on_rate_limit_error(self, mock_claude_client):
        """Retries on rate limit (429) errors."""
        import anthropic

        rate_limit_error = anthropic.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429),
            body={"error": {"message": "rate limited"}},
        )
        good_response = MagicMock(
            content=[MagicMock(text='{"key": "value"}')],
            usage=MagicMock(input_tokens=100, output_tokens=50),
        )
        mock_claude_client.messages.create.side_effect = [rate_limit_error, good_response]

        agent = BaseAgent(mock_claude_client)
        result = agent._call_claude("system", "user")
        assert result == {"key": "value"}

    def test_uses_prompt_caching(self, mock_claude_client):
        """System prompt should use cache_control for prompt caching."""
        mock_claude_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text='{"key": "value"}')],
            usage=MagicMock(input_tokens=100, output_tokens=50),
        )

        agent = BaseAgent(mock_claude_client)
        agent._call_claude("You are an analyst.", "Analyze this")

        call_kwargs = mock_claude_client.messages.create.call_args[1]
        system = call_kwargs["system"]
        # System should be structured for caching
        assert isinstance(system, list)
        assert system[0]["cache_control"] == {"type": "ephemeral"}

    def test_uses_configured_model(self, mock_claude_client):
        mock_claude_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text='{}')],
            usage=MagicMock(input_tokens=0, output_tokens=0),
        )

        agent = BaseAgent(mock_claude_client, model="claude-test-model")
        agent._call_claude("sys", "user")

        call_kwargs = mock_claude_client.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-test-model"

    def test_logs_token_usage(self, mock_claude_client, caplog):
        """Should log token counts for cost tracking."""
        mock_claude_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text='{"key": "value"}')],
            usage=MagicMock(input_tokens=1500, output_tokens=300),
        )

        agent = BaseAgent(mock_claude_client)
        import logging
        with caplog.at_level(logging.INFO, logger="src.agents.base"):
            agent._call_claude("system", "user")
        assert "1500" in caplog.text or "input" in caplog.text.lower()
