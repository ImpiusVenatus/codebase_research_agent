from __future__ import annotations

import json
from typing import Any

from openai import APIConnectionError, APIStatusError, AuthenticationError, OpenAI, RateLimitError

from agent.providers.base import CompletionResult, RetryableProviderError, ToolCallRequest, ToolUseFailedError
from agent.providers.tools import openai_function_tools


class OpenAICompatibleProvider:
    def __init__(
        self,
        name: str,
        api_key: str,
        model: str,
        base_url: str | None = None,
    ) -> None:
        self.name = name
        self.model = model
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def create_completion(
        self,
        messages: list[dict[str, Any]],
        allow_tools: bool,
    ) -> CompletionResult:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }
        if allow_tools:
            kwargs["tools"] = openai_function_tools()
            kwargs["tool_choice"] = "auto"
            kwargs["parallel_tool_calls"] = False

        try:
            response = self._client.chat.completions.create(**kwargs)
        except RateLimitError as exc:
            raise RetryableProviderError(self.name, str(exc)) from exc
        except (AuthenticationError, APIConnectionError) as exc:
            raise RetryableProviderError(self.name, str(exc)) from exc
        except APIStatusError as exc:
            if _is_tool_use_failed(exc):
                raise ToolUseFailedError(str(exc), _failed_generation_text(exc)) from exc
            if exc.status_code in {408, 429, 500, 502, 503, 504}:
                raise RetryableProviderError(self.name, str(exc)) from exc
            raise

        message = response.choices[0].message
        tool_calls = [
            ToolCallRequest(
                id=tool_call.id,
                name=tool_call.function.name,
                arguments=tool_call.function.arguments or "{}",
            )
            for tool_call in getattr(message, "tool_calls", None) or []
        ]
        usage = getattr(response, "usage", None)
        return CompletionResult(
            content=message.content or "",
            tool_calls=tool_calls,
            input_tokens=_usage_value(usage, "prompt_tokens"),
            output_tokens=_usage_value(usage, "completion_tokens"),
        )


def _usage_value(usage: Any, name: str) -> int:
    if usage is None:
        return 0
    value = getattr(usage, name, None)
    return int(value) if value is not None else 0


def _is_tool_use_failed(exc: APIStatusError) -> bool:
    body = getattr(exc, "body", None) or {}
    if isinstance(body, dict):
        error = body.get("error", {})
        if isinstance(error, dict) and error.get("code") == "tool_use_failed":
            return True
    return "tool_use_failed" in str(exc)


def _failed_generation_text(exc: APIStatusError) -> str:
    body = getattr(exc, "body", None) or {}
    if isinstance(body, dict):
        error = body.get("error", {})
        if isinstance(error, dict):
            text = error.get("failed_generation")
            if isinstance(text, str):
                return text
    return ""


def parse_failed_tool_from_text(failed_generation: str) -> tuple[str, dict[str, Any]] | None:
    import re

    pattern = re.compile(r"<function=(\w+)(\{.*\})</function>", re.DOTALL)
    match = pattern.search(failed_generation)
    if not match:
        return None
    try:
        tool_input = json.loads(match.group(2))
    except json.JSONDecodeError:
        return None
    if not isinstance(tool_input, dict):
        return None
    return match.group(1), tool_input
