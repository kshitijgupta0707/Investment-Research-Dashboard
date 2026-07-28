"""The agent's planning output."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PlannedToolCall(BaseModel):
    """One tool the model chose to call.

    `id` is minted by the planner, not by the provider: Gemini does not label
    its function calls. It carries the result back through the executor so the
    synthesis turn can pair each result with the request that produced it, so
    it need only be unique within one plan.
    """

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class QueryPlan(BaseModel):
    """What the model decided a question needs.

    An empty `tool_calls` with a `direct_answer` is a valid, expected outcome:
    "what is a P/E ratio?" needs no data at all.
    """

    query: str
    tool_calls: list[PlannedToolCall] = Field(default_factory=list)
    direct_answer: str | None = None
    model: str
    stop_reason: str | None = None
    latency_ms: float = 0.0

    @property
    def tool_names(self) -> list[str]:
        """Which tools were selected, in order. Written to query history."""
        return [call.name for call in self.tool_calls]

    @property
    def used_tools(self) -> bool:
        return bool(self.tool_calls)
