from __future__ import annotations

import json
from typing import Any

from anthropic import APIConnectionError, APIStatusError, Anthropic, AuthenticationError, RateLimitError

from agent.providers.base import CompletionResult, RetryableProviderError, ToolCallRequest
from agent.providers.tools import anthropic_tools


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        self._client = Anthropic(api_key=api_key)

    def create_completion(
        self,
        messages: list[dict[str, Any]],
        allow_tools: bool,
    ) -> CompletionResult:
        system_prompt, anthropic_messages = _convert_messages(messages)
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": anthropic_messages,
            "temperature": 0.2,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if allow_tools:
            kwargs["tools"] = anthropic_tools()

        try:
            response = self._client.messages.create(**kwargs)
        except RateLimitError as exc:
            raise RetryableProviderError(self.name, str(exc)) from exc
        except (AuthenticationError, APIConnectionError) as exc:
            raise RetryableProviderError(self.name, str(exc)) from exc
        except APIStatusError as exc:
            if exc.status_code in {408, 429, 500, 502, 503, 504}:
                raise RetryableProviderError(self.name, str(exc)) from exc
            raise

        content = ""
        tool_calls: list[ToolCallRequest] = []
        for block in response.content:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                content += block.text
            elif block_type == "tool_use":
                tool_calls.append(
                    ToolCallRequest(
                        id=block.id,
                        name=block.name,
                        arguments=json.dumps(block.input),
                    )
                )

        return CompletionResult(
            content=content,
            tool_calls=tool_calls,
            input_tokens=getattr(response.usage, "input_tokens", 0) or 0,
            output_tokens=getattr(response.usage, "output_tokens", 0) or 0,
        )


def _convert_messages(
    messages: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    system_parts: list[str] = []
    converted: list[dict[str, Any]] = []

    for message in messages:
        role = message["role"]
        if role == "system":
            system_parts.append(str(message.get("content", "")))
            continue

        if role == "user":
            converted.append({"role": "user", "content": message.get("content", "")})
            continue

        if role == "assistant":
            blocks: list[dict[str, Any]] = []
            if message.get("content"):
                blocks.append({"type": "text", "text": message["content"]})
            for tool_call in message.get("tool_calls", []):
                function = tool_call["function"]
                try:
                    tool_input = json.loads(function.get("arguments") or "{}")
                except json.JSONDecodeError:
                    tool_input = {"_raw_arguments": function.get("arguments", "")}
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tool_call["id"],
                        "name": function["name"],
                        "input": tool_input,
                    }
                )
            converted.append({"role": "assistant", "content": blocks or ""})
            continue

        if role == "tool":
            converted.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": message["tool_call_id"],
                            "content": message.get("content", ""),
                        }
                    ],
                }
            )

    return "\n\n".join(system_parts), converted
