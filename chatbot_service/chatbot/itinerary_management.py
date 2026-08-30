"""Mutate persisted itineraries only after place verification."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import TypeAdapter, ValidationError

from chatbot.semantic import SemanticActionType, SemanticInterpretation
from chatbot.tool_planner import PlannedToolCall
from chatbot.tools.models import ItineraryData, MapboxCandidateResolutionData, ToolResult
from chatbot.tools.registry import (
    ADD_ITINERARY_STOP_TOOL_NAME,
    GET_ITINERARY_TOOL_NAME,
    MAPBOX_RESOLVE_CANDIDATES_TOOL_NAME,
    ToolExecution,
    ToolRegistry,
)

_ITINERARY_ADAPTER = TypeAdapter(ToolResult[ItineraryData])
_RESOLUTION_ADAPTER = TypeAdapter(ToolResult[MapboxCandidateResolutionData])


@dataclass(frozen=True)
class ItineraryManagementResult:
    calls: list[PlannedToolCall]
    executions: list[ToolExecution]
    evidence: dict[str, Any]
    itinerary: ItineraryData | None
    operation: str | None = None


class ItineraryManagementPipeline:
    """Execute the supported ADD_STOP vertical slice."""

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        max_tool_calls: int | None = None,
    ) -> None:
        self._registry = registry
        self._max_tool_calls = max_tool_calls

    def execute(
        self,
        *,
        interpretation: SemanticInterpretation,
        active_itinerary_id: str | None,
        active_itinerary_version: int | None,
    ) -> ItineraryManagementResult:
        actions = {action.type for action in interpretation.actions}
        if SemanticActionType.ADD_ITINERARY_STOP not in actions:
            return self._failure("unsupported_itinerary_operation")
        if active_itinerary_id is None or active_itinerary_version is None:
            return self._failure("missing_active_itinerary")
        place_name = next(iter(interpretation.entities.places), "")
        if not place_name:
            return self._failure("missing_place_to_add")

        calls: list[PlannedToolCall] = []
        executions: list[ToolExecution] = []
        get_call = PlannedToolCall(
            GET_ITINERARY_TOOL_NAME,
            {"itineraryId": active_itinerary_id},
            evidence_kind="itinerary",
        )
        current_execution = self._run(get_call, calls, executions)
        current = self._parse(_ITINERARY_ADAPTER, current_execution)
        if current is None:
            return self._failure(
                current_execution.error_code or "itinerary_not_found",
                calls=calls,
                executions=executions,
                operation=ADD_ITINERARY_STOP_TOOL_NAME,
            )
        if current.version != active_itinerary_version:
            return self._failure(
                "version_conflict",
                calls=calls,
                executions=executions,
                operation=ADD_ITINERARY_STOP_TOOL_NAME,
            )

        resolve_call = PlannedToolCall(
            MAPBOX_RESOLVE_CANDIDATES_TOOL_NAME,
            {
                "longitude": sum(stop.longitude for stop in current.stops)
                / len(current.stops),
                "latitude": sum(stop.latitude for stop in current.stops)
                / len(current.stops),
                "candidates": [{
                    "candidateId": "candidate-1",
                    "name": place_name,
                    "aliases": [],
                    "categoryHints": [],
                }],
            },
            evidence_kind="candidate_resolution",
        )
        resolution_execution = self._run(resolve_call, calls, executions)
        resolution = self._parse(_RESOLUTION_ADAPTER, resolution_execution)
        matches = [] if resolution is None else [
            result.place
            for result in resolution.results
            if result.status == "matched" and result.place is not None
        ]
        if len(matches) != 1:
            return self._failure(
                "place_not_uniquely_resolved",
                calls=calls,
                executions=executions,
                operation=ADD_ITINERARY_STOP_TOOL_NAME,
            )
        match = matches[0]
        if any(stop.mapbox_id == match.mapbox_id for stop in current.stops):
            return self._failure(
                "duplicate_stop",
                calls=calls,
                executions=executions,
                operation=ADD_ITINERARY_STOP_TOOL_NAME,
            )

        add_call = PlannedToolCall(
            ADD_ITINERARY_STOP_TOOL_NAME,
            {
                "itineraryId": current.id,
                "expectedVersion": current.version,
                "position": interpretation.itinerary_context.add_position
                or "optimized",
                "stop": {
                    "mapboxId": match.mapbox_id,
                    "name": match.name,
                    "longitude": match.longitude,
                    "latitude": match.latitude,
                },
            },
            evidence_kind="itinerary",
        )
        add_execution = self._run(add_call, calls, executions)
        updated = self._parse(_ITINERARY_ADAPTER, add_execution)
        if updated is None:
            return self._failure(
                add_execution.error_code or "itinerary_operation_failed",
                calls=calls,
                executions=executions,
                operation=ADD_ITINERARY_STOP_TOOL_NAME,
            )

        return ItineraryManagementResult(
            calls=calls,
            executions=executions,
            evidence={
                "success": True,
                "operation": ADD_ITINERARY_STOP_TOOL_NAME,
                "itinerary": updated.model_dump(mode="json", by_alias=True),
            },
            itinerary=updated,
            operation=ADD_ITINERARY_STOP_TOOL_NAME,
        )

    def _run(self, call, calls, executions) -> ToolExecution:
        if (
            self._max_tool_calls is not None
            and len(calls) >= self._max_tool_calls
        ):
            return ToolExecution(
                content=json.dumps(
                    {
                        "success": False,
                        "errorCode": "tool_budget_exceeded",
                    },
                    ensure_ascii=False,
                ),
                sources=(),
                success=False,
                system_failure=False,
                error_code="tool_budget_exceeded",
            )
        execution = self._registry.execute(call.name, call.arguments)
        calls.append(call)
        executions.append(execution)
        return execution

    @staticmethod
    def _parse(adapter: TypeAdapter[Any], execution: ToolExecution) -> Any | None:
        if not execution.success:
            return None
        try:
            result = adapter.validate_json(execution.content)
        except (ValidationError, ValueError):
            return None
        return result.data

    @staticmethod
    def _failure(
        error_code: str,
        *,
        calls: list[PlannedToolCall] | None = None,
        executions: list[ToolExecution] | None = None,
        operation: str | None = None,
    ) -> ItineraryManagementResult:
        return ItineraryManagementResult(
            calls=calls or [],
            executions=executions or [],
            evidence={
                "success": False,
                "operation": operation,
                "errorCode": error_code,
            },
            itinerary=None,
            operation=operation,
        )


__all__ = ["ItineraryManagementPipeline", "ItineraryManagementResult"]
