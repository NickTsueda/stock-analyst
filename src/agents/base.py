"""Base agent class — Claude calling infrastructure with retry and JSON parsing.

All LLM-calling agents extend this class. Provides:
- _call_claude(): sends messages with prompt caching, retries on rate limit/parse failure
- _parse_json_response(): extracts JSON from Claude responses (raw or markdown-fenced)
"""
from __future__ import annotations

import json
import logging
import re
import time

import anthropic

from src.config import settings

logger = logging.getLogger(__name__)

# Sonnet pricing (per million tokens)
_INPUT_COST_PER_M = 3.0
_OUTPUT_COST_PER_M = 15.0
_MAX_RETRIES = 2


class BaseAgent:
    def __init__(self, client: anthropic.Anthropic, model: str | None = None):
        self.client = client
        self.model = model or settings.CLAUDE_MODEL

    def _call_claude(self, system: str, user: str, max_tokens: int = 4096) -> dict:
        """Send message to Claude, parse JSON response.

        Retries up to 2x on rate limit or parse failure.
        Uses prompt caching on system prompts to reduce cost.
        """
        attempt = 0
        while attempt <= _MAX_RETRIES:
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=[{
                        "type": "text",
                        "text": system,
                        "cache_control": {"type": "ephemeral"},
                    }],
                    messages=[{"role": "user", "content": user}],
                )

                usage = response.usage
                input_tokens = usage.input_tokens
                output_tokens = usage.output_tokens
                cost = (input_tokens * _INPUT_COST_PER_M + output_tokens * _OUTPUT_COST_PER_M) / 1_000_000
                logger.info(
                    "Claude call: %d input tokens, %d output tokens, ~$%.4f",
                    input_tokens, output_tokens, cost,
                )

                text = response.content[0].text
                result = self._parse_json_response(text)

                if result:
                    return result

                # Parse failed — retry
                attempt += 1
                if attempt <= _MAX_RETRIES:
                    logger.warning(
                        "JSON parse failed (attempt %d/%d), retrying",
                        attempt, _MAX_RETRIES + 1,
                    )

            except anthropic.RateLimitError:
                attempt += 1
                if attempt <= _MAX_RETRIES:
                    wait = 2 ** attempt
                    logger.warning("Rate limited, waiting %ds before retry", wait)
                    time.sleep(wait)
            except anthropic.APIError as e:
                logger.error("Claude API error: %s", e)
                return {}

        logger.error("All %d attempts failed", _MAX_RETRIES + 1)
        return {}

    def _parse_json_response(self, text: str) -> dict:
        """Extract JSON from response text.

        Handles: raw JSON, ```json fenced, ``` fenced, JSON embedded in prose.
        """
        # Try markdown code fence extraction first
        fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if fence_match:
            try:
                return json.loads(fence_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try parsing the entire text as JSON
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # Try finding a JSON object in the text
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        return {}
