import json
import re

import anthropic
import structlog

logger = structlog.get_logger()


class ClaudeClient:
    MODEL = "claude-sonnet-4-6"

    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def generate(
        self,
        user_prompt: str,
        system_prompt: str | None = None,
        cache_system_prompt: bool = False,
        max_tokens: int = 4096,
    ) -> str:
        kwargs: dict = {"model": self.MODEL, "max_tokens": max_tokens}

        if system_prompt:
            if cache_system_prompt:
                kwargs["system"] = [
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]
            else:
                kwargs["system"] = system_prompt

        kwargs["messages"] = [{"role": "user", "content": user_prompt}]

        try:
            response = await self._client.messages.create(**kwargs)
            return response.content[0].text
        except anthropic.RateLimitError:
            logger.error("claude_rate_limit_error")
            raise
        except anthropic.APIError as e:
            logger.error("claude_api_error", error=str(e))
            raise

    @staticmethod
    def strip_json_fences(text: str) -> str:
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        return text.strip()

    @staticmethod
    def parse_json_response(text: str) -> dict:
        cleaned = ClaudeClient.strip_json_fences(text)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse Claude JSON response: {e}\nRaw: {text}") from e
