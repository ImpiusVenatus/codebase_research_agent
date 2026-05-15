from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments: str


@dataclass
class CompletionResult:
    content: str
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0


class LLMProvider(Protocol):
    name: str

    def create_completion(
        self,
        messages: list[dict[str, Any]],
        allow_tools: bool,
    ) -> CompletionResult:
        ...


class RetryableProviderError(Exception):
    """Provider failed in a way that should trigger the next provider in the chain."""

    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        super().__init__(message)


class ToolUseFailedError(Exception):
    """Model emitted invalid tool syntax (Groq-specific recovery may apply)."""

    def __init__(self, message: str, failed_generation: str = "") -> None:
        self.failed_generation = failed_generation
        super().__init__(message)


class NoProvidersConfigured(Exception):
    pass


class AllProvidersFailed(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(
            "All configured LLM providers failed. "
            + "; ".join(errors)
        )
