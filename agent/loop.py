from __future__ import annotations

import json
import time
import uuid
from typing import Any

from django.conf import settings
from django.utils import timezone

from agent.citations import persist_citations_from_answer
from agent.providers.base import CompletionResult, ToolCallRequest, ToolUseFailedError
from agent.providers.chain import ChainedLLMProvider
from agent.providers.openai_compat import parse_failed_tool_from_text
from agent.tool_dispatcher import execute_tool
from agent.tools.db_tools import get_previous_findings
from research.models import ResearchSession, ToolCall


MAX_TOOL_CALLS = 15
MAX_WALL_CLOCK_SECONDS = 60
MAX_TOOL_RESULT_CHARS = 3000
MAX_COMPLETION_RETRIES = 2


class ResearchAgent:
    def __init__(
        self,
        session: ResearchSession,
        provider: ChainedLLMProvider,
    ) -> None:
        self.session = session
        self.provider = provider
        self.repo_root = session.repository.local_clone_path
        self.repo_url = session.repository.url

    def run(self) -> ResearchSession:
        start_time = time.monotonic()
        force_final = False
        prior_findings = get_previous_findings(self.repo_url)
        messages = [
            {"role": "system", "content": self._system_prompt()},
            {
                "role": "user",
                "content": self._initial_user_message(prior_findings),
            },
        ]

        self._mark_running()

        try:
            while True:
                if self._budget_exhausted(start_time):
                    messages.append({"role": "user", "content": self._budget_message()})
                    force_final = True

                try:
                    result = self._create_completion(messages, allow_tools=not force_final)
                except ToolUseFailedError as exc:
                    if force_final or not self._recover_failed_tool_generation(
                        exc.failed_generation,
                        messages,
                        start_time,
                    ):
                        raise
                    continue

                self._record_usage(result)

                if result.tool_calls and not force_final:
                    messages.append(self._assistant_message(result))

                    for tool_call in result.tool_calls:
                        if self._budget_exhausted(start_time):
                            messages.append(self._budget_tool_result(tool_call))
                            continue

                        step_number = self._count_tool_calls() + 1
                        tool_input = self._tool_input(tool_call)
                        output, duration_ms = execute_tool(
                            tool_name=tool_call.name,
                            tool_input=tool_input,
                            repo_root=self.repo_root,
                            session_id=self.session.id,
                        )
                        ToolCall.objects.create(
                            session=self.session,
                            step_number=step_number,
                            tool_name=tool_call.name,
                            tool_input=tool_input,
                            tool_output=output,
                            duration_ms=duration_ms,
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": self._truncate_tool_result(output),
                            }
                        )

                    continue

                if (
                    not force_final
                    and result.content
                    and self.session.findings.count() == 0
                ):
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Before your final answer, call save_finding once "
                                "for each file citation (file_path, line_start, "
                                "line_end, and a short note). Then provide the "
                                "final answer with inline citations."
                            ),
                        }
                    )
                    continue

                final_answer = result.content
                if self.provider.last_used_name:
                    final_answer += f"\n\n_(LLM provider: {self.provider.last_used_name})_"
                self._mark_completed(final_answer)
                persist_citations_from_answer(self.session, result.content)
                return self.session
        except Exception as exc:
            self._mark_failed(exc)
            if settings.DEBUG:
                raise
            return self.session

    def _create_completion(
        self,
        messages: list[dict[str, Any]],
        allow_tools: bool,
    ) -> CompletionResult:
        for attempt in range(MAX_COMPLETION_RETRIES + 1):
            try:
                return self.provider.create_completion(messages, allow_tools)
            except ToolUseFailedError as exc:
                if not allow_tools or attempt >= MAX_COMPLETION_RETRIES:
                    raise
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Your last tool call was invalid. Use only the "
                            "provided function-calling API. Do not emit "
                            "<function=...> XML tags."
                        ),
                    }
                )
        raise RuntimeError("completion failed without a response")

    def _recover_failed_tool_generation(
        self,
        failed_generation: str,
        messages: list[dict[str, Any]],
        start_time: float,
    ) -> bool:
        parsed = parse_failed_tool_from_text(failed_generation)
        if parsed is None:
            return False

        tool_name, tool_input = parsed
        if self._budget_exhausted(start_time):
            return False

        tool_call_id = f"recovered_{uuid.uuid4().hex[:12]}"
        output, duration_ms = execute_tool(
            tool_name=tool_name,
            tool_input=tool_input,
            repo_root=self.repo_root,
            session_id=self.session.id,
        )
        step_number = self._count_tool_calls() + 1
        ToolCall.objects.create(
            session=self.session,
            step_number=step_number,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=output,
            duration_ms=duration_ms,
        )
        messages.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(tool_input),
                        },
                    }
                ],
            }
        )
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": self._truncate_tool_result(output),
            }
        )
        return True

    def _count_tool_calls(self) -> int:
        return self.session.tool_calls.count()

    def _mark_running(self) -> None:
        self.session.status = ResearchSession.Status.RUNNING
        self.session.started_at = timezone.now()
        self.session.save(update_fields=["status", "started_at"])

    def _mark_completed(self, final_answer: str) -> None:
        self.session.final_answer = final_answer
        self.session.status = ResearchSession.Status.COMPLETED
        self.session.completed_at = timezone.now()
        self.session.save(
            update_fields=[
                "final_answer",
                "status",
                "completed_at",
                "input_tokens",
                "output_tokens",
            ]
        )

    def _mark_failed(self, exc: Exception) -> None:
        self.session.final_answer = f"ERROR: {type(exc).__name__}: {exc}"
        self.session.status = ResearchSession.Status.FAILED
        self.session.completed_at = timezone.now()
        self.session.save(update_fields=["final_answer", "status", "completed_at"])

    def _record_usage(self, result: CompletionResult) -> None:
        if result.input_tokens or result.output_tokens:
            self.session.input_tokens += result.input_tokens
            self.session.output_tokens += result.output_tokens
            self.session.save(update_fields=["input_tokens", "output_tokens"])

    def _assistant_message(self, result: CompletionResult) -> dict[str, Any]:
        assistant_message: dict[str, Any] = {
            "role": "assistant",
            "content": result.content or "",
        }
        if result.tool_calls:
            assistant_message["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.name,
                        "arguments": tool_call.arguments,
                    },
                }
                for tool_call in result.tool_calls
            ]
        return assistant_message

    def _tool_input(self, tool_call: ToolCallRequest) -> dict[str, Any]:
        try:
            parsed = json.loads(tool_call.arguments or "{}")
        except json.JSONDecodeError:
            return {"_raw_arguments": tool_call.arguments}
        return parsed if isinstance(parsed, dict) else {"value": parsed}

    def _budget_exhausted(self, start_time: float) -> bool:
        return (
            self._count_tool_calls() >= MAX_TOOL_CALLS
            or time.monotonic() - start_time >= MAX_WALL_CLOCK_SECONDS
        )

    def _budget_tool_result(self, tool_call: ToolCallRequest) -> dict[str, str]:
        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": "ERROR: tool budget reached. Produce a final answer now.",
        }

    def _truncate_tool_result(self, output: str) -> str:
        if len(output) <= MAX_TOOL_RESULT_CHARS:
            return output
        return output[:MAX_TOOL_RESULT_CHARS] + "\n... [truncated]"

    def _initial_user_message(self, prior_findings: list[dict[str, str]]) -> str:
        prior_text = (
            json.dumps(prior_findings, indent=2)
            if prior_findings
            else "[] (no prior findings for this repository)"
        )
        return (
            f"Repository URL: {self.repo_url}\n"
            f"Clone root on disk (for your reference only): {self.repo_root}\n\n"
            f"IMPORTANT: All tool paths must be relative to the repository root. "
            f"Use path '.' for the repo root (e.g. list_files with path '.'). "
            f"Never use repo_cache, absolute paths, or the clone directory name.\n\n"
            f"Prior findings (already loaded; do not call get_previous_findings):\n"
            f"{prior_text}\n\n"
            f"Question: {self.session.question}"
        )

    def _budget_message(self) -> str:
        return (
            "You have reached the tool budget. Produce your final answer now using "
            "only the information you have."
        )

    def _system_prompt(self) -> str:
        return (
            "You are a concise codebase research agent. Your job is to answer the "
            "user's technical question by exploring the repository with tools and "
            "persisting important findings.\n\n"
            "Workflow requirements:\n"
            "- Prior findings are already provided in the user message.\n"
            "- Explore strategically: start with list_files(path='.'), then drill into subdirectories.\n"
            "- Never pass repo_cache or absolute filesystem paths to tools.\n"
            "- Use only the provided function-calling tools; never write <function=...> tags.\n"
            "- Use search_code for specific symbols, terms, routes, errors, and configuration names.\n"
            "- Use get_file_outline before reading large files.\n"
            "- Read only relevant files and line ranges; do not over-explore.\n"
            "- Call save_finding for each citation that will appear in the final answer.\n"
            "- Final answers must cite file paths and line numbers inline.\n"
            "- Be concise and explain only what the question asks."
        )
