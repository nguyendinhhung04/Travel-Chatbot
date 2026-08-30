"""Shared handler mechanics without intent-specific branching."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from chatbot.intent import TravelIntent
from chatbot.semantic import InterpretationStatus
from chatbot.tool_planner import PlannedToolCall
from chatbot.tools.registry import ToolRegistry

from ..contracts import IntentContext, IntentExecutionResult
from ..execution import execute_planned_calls


class BaseIntentHandler(ABC):
    intent: TravelIntent
    response_policy: str | None = None

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        max_tool_calls: int,
    ) -> None:
        self._registry = registry
        self._max_tool_calls = max_tool_calls

    @abstractmethod
    def handle(self, context: IntentContext) -> IntentExecutionResult:
        ...

    @staticmethod
    def should_skip_tools(context: IntentContext) -> bool:
        return context.interpretation.status in {
            InterpretationStatus.NEEDS_CLARIFICATION,
            InterpretationStatus.UNSUPPORTED,
        }

    def execute_calls(
        self,
        context: IntentContext,
        calls: Sequence[PlannedToolCall],
        *,
        response_policy: str | None = None,
    ) -> IntentExecutionResult:
        if self.should_skip_tools(context):
            return IntentExecutionResult()
        planned_calls, executions = execute_planned_calls(
            self._registry,
            calls,
            max_tool_calls=self._max_tool_calls,
        )
        return IntentExecutionResult(
            planned_calls=planned_calls,
            executions=executions,
            response_policy=response_policy if planned_calls else None,
        )


class RagFirstHandler(BaseIntentHandler):
    def handle(self, context: IntentContext) -> IntentExecutionResult:
        if self.should_skip_tools(context):
            return IntentExecutionResult()
        from ..planning import plan_rag_search

        return self.execute_calls(
            context,
            (plan_rag_search(context.interpretation),),
            response_policy=self.response_policy,
        )


__all__ = ["BaseIntentHandler", "RagFirstHandler"]
