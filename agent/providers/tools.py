from __future__ import annotations

from typing import Any

from agent.tool_schemas import TOOLS


def exposed_tools() -> list[dict[str, Any]]:
    return [tool for tool in TOOLS if tool["name"] != "get_previous_findings"]


def openai_function_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": _strict_parameters(tool["input_schema"]),
            },
        }
        for tool in exposed_tools()
    ]


def anthropic_tools() -> list[dict[str, Any]]:
    return [
        {
            "name": tool["name"],
            "description": tool["description"],
            "input_schema": _strict_parameters(tool["input_schema"]),
        }
        for tool in exposed_tools()
    ]


def _strict_parameters(schema: dict[str, Any]) -> dict[str, Any]:
    parameters = dict(schema)
    if parameters.get("type") == "object":
        parameters["additionalProperties"] = False
    return parameters
