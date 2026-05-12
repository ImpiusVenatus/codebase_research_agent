from __future__ import annotations

import json
import time
from typing import Any

from django.conf import settings
from django.utils import timezone

from agent.tool_dispatcher import execute_tool
from agent.tool_schemas import TOOLS
from research.models import ResearchSession, ToolCall


MAX_TOOL_CALLS = 25
MAX_WALL_CLOCK_SECONDS = 60
MAX_TOOL_RESULT_CHARS = 8000


class ResearchAgent:
    def __init__(
        self,
        session: ResearchSession,
        client: Any,
        model: str,
    ) -> None:
        self.session = session
        self.client = client
        self.model = model
        self.repo_root = session.repository.local_clone_path
        self.repo_url = session.repository.url

    def run(self) -> ResearchSession:
        start_time = time.monotonic()
        tool_count = 0
        force_final = False
        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": self._initial_user_message()},
        ]

        self._mark_running()

        try:
            while True:
                if self._budget_exhausted(start_time, tool_count):
                    messages.append({"role": "user", "content": self._budget_message()})
                    force_final = True

                response = self._create_completion(messages, allow_tools=not force_final)
                self._record_usage(response)

                message = response.choices[0].message
                content = message.content or ""
                tool_calls = getattr(message, "tool_calls", None) or []

                if tool_calls and not force_final:
                    assistant_message = self._assistant_message(message)
                    messages.append(assistant_message)

                    for tool_call in tool_calls:
                        if self._budget_exhausted(start_time, tool_count):
                            messages.append(self._budget_tool_result(tool_call))
                            continue

                        tool_count += 1
                        tool_input = self._tool_input(tool_call)
                        output, duration_ms = execute_tool(
                            tool_name=tool_call.function.name,
                            tool_input=tool_input,
                            repo_root=self.repo_root,
                            session_id=self.session.id,
                        )
                        ToolCall.objects.create(
                            session=self.session,
                            step_number=tool_count,
                            tool_name=tool_call.function.name,
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

                self._mark_completed(content)
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
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }
        if allow_tools:
            kwargs["tools"] = groq_tools()
            kwargs["tool_choice"] = "auto"
        return self.client.chat.completions.create(**kwargs)

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

    def _record_usage(self, response: Any) -> None:
        usage = getattr(response, "usage", None)
        if usage is None:
            return

        input_tokens = _usage_value(usage, "prompt_tokens", "input_tokens")
        output_tokens = _usage_value(usage, "completion_tokens", "output_tokens")
        if input_tokens or output_tokens:
            self.session.input_tokens += input_tokens
            self.session.output_tokens += output_tokens
            self.session.save(update_fields=["input_tokens", "output_tokens"])

    def _assistant_message(self, message: Any) -> dict[str, Any]:
        assistant_message: dict[str, Any] = {
            "role": "assistant",
            "content": message.content or "",
        }
        tool_calls = []
        for tool_call in getattr(message, "tool_calls", None) or []:
            tool_calls.append(
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
            )
        if tool_calls:
            assistant_message["tool_calls"] = tool_calls
        return assistant_message

    def _tool_input(self, tool_call: Any) -> dict[str, Any]:
        arguments = tool_call.function.arguments or "{}"
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError:
            return {"_raw_arguments": arguments}
        return parsed if isinstance(parsed, dict) else {"value": parsed}

    def _budget_exhausted(self, start_time: float, tool_count: int) -> bool:
        return (
            tool_count >= MAX_TOOL_CALLS
            or time.monotonic() - start_time >= MAX_WALL_CLOCK_SECONDS
        )

    def _budget_tool_result(self, tool_call: Any) -> dict[str, str]:
        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": "ERROR: tool budget reached. Produce a final answer now.",
        }

    def _truncate_tool_result(self, output: str) -> str:
        if len(output) <= MAX_TOOL_RESULT_CHARS:
            return output
        return output[:MAX_TOOL_RESULT_CHARS] + "\n... [truncated]"

    def _initial_user_message(self) -> str:
        return (
            f"Repository URL: {self.repo_url}\n"
            f"Local clone path: {self.repo_root}\n\n"
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
            "- First call get_previous_findings for the repository URL to check prior research.\n"
            "- Explore strategically: start with list_files at the root, then drill into likely directories.\n"
            "- Use search_code for specific symbols, terms, routes, errors, and configuration names.\n"
            "- Use get_file_outline before reading large files.\n"
            "- Read only relevant files and line ranges; do not over-explore.\n"
            "- Call save_finding for each citation that will appear in the final answer.\n"
            "- Final answers must cite file paths and line numbers inline.\n"
            "- Be concise and explain only what the question asks."
        )


def groq_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        }
        for tool in TOOLS
    ]


def _usage_value(usage: Any, *names: str) -> int:
    for name in names:
        value = getattr(usage, name, None)
        if value is not None:
            return int(value)
    return 0
