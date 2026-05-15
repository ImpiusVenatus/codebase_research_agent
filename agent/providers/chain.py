from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from agent.providers.anthropic import AnthropicProvider
from agent.providers.base import (
    AllProvidersFailed,
    CompletionResult,
    LLMProvider,
    NoProvidersConfigured,
    RetryableProviderError,
    ToolUseFailedError,
)
from agent.providers.openai_compat import OpenAICompatibleProvider
logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class ChainedLLMProvider:
    """Try configured providers in order on each completion call."""

    def __init__(self, providers: list[LLMProvider]) -> None:
        if not providers:
            raise NoProvidersConfigured()
        self.providers = providers
        self.last_used_name: str | None = None

    def create_completion(
        self,
        messages: list[dict[str, Any]],
        allow_tools: bool,
    ) -> CompletionResult:
        errors: list[str] = []
        ordered = self._provider_order()

        for provider in ordered:
            try:
                result = provider.create_completion(messages, allow_tools)
                self.last_used_name = provider.name
                return result
            except ToolUseFailedError:
                raise
            except RetryableProviderError as exc:
                logger.warning("Provider %s failed: %s", provider.name, exc)
                errors.append(f"{provider.name}: {exc}")
                continue

        raise AllProvidersFailed(errors)

    def _provider_order(self) -> list[LLMProvider]:
        if self.last_used_name:
            preferred = [p for p in self.providers if p.name == self.last_used_name]
            rest = [p for p in self.providers if p.name != self.last_used_name]
            return preferred + rest
        return list(self.providers)


def build_provider_chain() -> ChainedLLMProvider:
    providers: list[LLMProvider] = []
    order = [name.strip() for name in settings.LLM_PROVIDER_ORDER if name.strip()]

    for name in order:
        provider = _build_provider(name)
        if provider is not None:
            providers.append(provider)
        else:
            logger.info("Skipping provider %s (not configured)", name)

    return ChainedLLMProvider(providers)


def _build_provider(name: str) -> LLMProvider | None:
    if name == "groq" and settings.GROQ_API_KEY:
        return OpenAICompatibleProvider(
            name="groq",
            api_key=settings.GROQ_API_KEY,
            model=settings.GROQ_MODEL,
            base_url=GROQ_BASE_URL,
        )
    if name == "openai" and settings.OPENAI_API_KEY:
        return OpenAICompatibleProvider(
            name="openai",
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_MODEL,
        )
    if name == "anthropic" and settings.ANTHROPIC_API_KEY:
        return AnthropicProvider(
            api_key=settings.ANTHROPIC_API_KEY,
            model=settings.ANTHROPIC_MODEL,
        )
    return None


def has_configured_provider() -> bool:
    try:
        build_provider_chain()
        return True
    except NoProvidersConfigured:
        return False
