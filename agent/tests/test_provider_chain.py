from unittest import TestCase
from unittest.mock import MagicMock, patch

from agent.providers.base import CompletionResult, RetryableProviderError
from agent.providers.chain import ChainedLLMProvider, build_provider_chain


class FakeProvider:
    def __init__(self, name: str, results: list[CompletionResult | Exception]) -> None:
        self.name = name
        self._results = list(results)
        self.calls = 0

    def create_completion(self, messages, allow_tools):
        self.calls += 1
        outcome = self._results.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class ChainedLLMProviderTests(TestCase):
    def test_uses_next_provider_on_retryable_error(self) -> None:
        chain = ChainedLLMProvider(
            [
                FakeProvider(
                    "groq",
                    [RetryableProviderError("groq", "rate limit")],
                ),
                FakeProvider(
                    "openai",
                    [CompletionResult(content="done")],
                ),
            ]
        )
        result = chain.create_completion([{"role": "user", "content": "hi"}], False)
        self.assertEqual(result.content, "done")
        self.assertEqual(chain.last_used_name, "openai")

    def test_sticks_to_provider_after_first_success(self) -> None:
        groq = FakeProvider("groq", [CompletionResult(content="a"), CompletionResult(content="b")])
        openai = FakeProvider("openai", [CompletionResult(content="c")])
        chain = ChainedLLMProvider([groq, openai])
        chain.create_completion([], False)
        chain.create_completion([], False)
        self.assertEqual(groq.calls, 2)
        self.assertEqual(openai.calls, 0)


class BuildProviderChainTests(TestCase):
    @patch("agent.providers.chain.settings")
    def test_skips_unconfigured_providers(self, mock_settings) -> None:
        mock_settings.LLM_PROVIDER_ORDER = ["groq", "openai", "anthropic"]
        mock_settings.GROQ_API_KEY = "groq-key"
        mock_settings.GROQ_MODEL = "llama-3.3-70b-versatile"
        mock_settings.OPENAI_API_KEY = ""
        mock_settings.OPENAI_MODEL = "gpt-4o-mini"
        mock_settings.ANTHROPIC_API_KEY = ""
        mock_settings.ANTHROPIC_MODEL = "claude-3-5-haiku-20241022"

        chain = build_provider_chain()
        self.assertEqual(len(chain.providers), 1)
        self.assertEqual(chain.providers[0].name, "groq")
