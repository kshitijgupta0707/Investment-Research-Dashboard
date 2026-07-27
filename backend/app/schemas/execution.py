"""Results of running the tools the planner selected."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """One tool's outcome. A failure is data, not an exception.

    `tool_use_id` echoes the planner's id so the synthesis turn can match this
    result to the request that produced it.
    """

    tool_use_id: str
    name: str
    ok: bool
    data: Any | None = None
    error: str | None = None
    latency_ms: float = 0.0

    @property
    def failed(self) -> bool:
        return not self.ok


class ExecutionResult(BaseModel):
    """Everything the tools returned, including what did not work.

    `partial` is the flag the frontend reads to show a degraded-data banner.
    """

    results: list[ToolResult] = Field(default_factory=list)
    latency_ms: float = 0.0

    @property
    def succeeded(self) -> list[ToolResult]:
        return [r for r in self.results if r.ok]

    @property
    def failed_tools(self) -> list[str]:
        return [r.name for r in self.results if r.failed]

    @property
    def partial(self) -> bool:
        """True when some tools worked and others did not."""
        return bool(self.failed_tools) and bool(self.succeeded)

    @property
    def all_failed(self) -> bool:
        return bool(self.results) and not self.succeeded
