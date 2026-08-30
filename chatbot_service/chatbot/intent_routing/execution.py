"""Shared deterministic tool execution used by intent handlers."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Sequence

from chatbot.tool_planner import PlannedToolCall
from chatbot.tools.registry import ToolExecution, ToolRegistry


class ToolInfrastructureError(RuntimeError):
    """Raised when every planned tool failed for infrastructure reasons."""


def _normalized_search_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold().replace("đ", "d"))
    without_marks = "".join(
        character for character in decomposed
        if unicodedata.category(character) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", " ", without_marks).strip()


def _destination_name_matches(name: object, destination: str) -> bool:
    return (
        isinstance(name, str)
        and _normalized_search_text(name) == _normalized_search_text(destination)
    )


def first_result_coordinates(
    execution: ToolExecution,
    *,
    destination: str | None = None,
) -> tuple[float, float] | None:
    if not execution.success:
        return None
    try:
        payload = json.loads(execution.content)
        results = payload["data"]["results"]
        if not isinstance(results, list):
            return None
        for result in results:
            if not isinstance(result, dict):
                continue
            if (
                destination is not None
                and isinstance(result.get("name"), str)
                and not _destination_name_matches(result["name"], destination)
            ):
                continue
            return float(result["longitude"]), float(result["latitude"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return None


def execute_planned_calls(
    registry: ToolRegistry,
    calls: Sequence[PlannedToolCall],
    *,
    max_tool_calls: int,
) -> tuple[tuple[PlannedToolCall, ...], tuple[ToolExecution, ...]]:
    """Execute at most the configured number of calls, resolving anchors in order."""
    planned = tuple(calls[:max_tool_calls])
    executions: list[ToolExecution] = []
    destination_coordinates: dict[str, tuple[float, float]] = {}
    actual_calls: list[PlannedToolCall] = []

    for call in planned:
        arguments = dict(call.arguments)
        if (
            call.name == "mapbox_category_search"
            and call.destination is not None
            and "proximity" not in arguments
        ):
            coordinates = destination_coordinates.get(call.destination)
            if coordinates is None:
                arguments["near"] = call.destination
            else:
                longitude, latitude = coordinates
                arguments.pop("near", None)
                arguments["proximity"] = f"{longitude},{latitude}"

        execution = registry.execute(call.name, arguments)
        actual_calls.append(call)
        executions.append(execution)
        if call.evidence_kind == "destination_location" and call.destination:
            coordinates = first_result_coordinates(
                execution,
                destination=call.destination,
            )
            if coordinates is not None:
                destination_coordinates[call.destination] = coordinates

    return tuple(actual_calls), tuple(executions)


def raise_if_all_tools_had_system_failures(
    executions: Sequence[ToolExecution],
) -> None:
    if (
        executions
        and not any(execution.success for execution in executions)
        and all(execution.system_failure for execution in executions)
    ):
        raise ToolInfrastructureError(
            "All planned tools failed because of infrastructure errors."
        )


__all__ = [
    "execute_planned_calls",
    "first_result_coordinates",
    "raise_if_all_tools_had_system_failures",
    "ToolInfrastructureError",
]
