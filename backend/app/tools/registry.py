"""Explicit tool registration and lookup."""

from app.tools.base import Tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if not tool.tool_id or tool.tool_id in self._tools:
            raise ValueError("Tool identifier is empty or already registered")
        self._tools[tool.tool_id] = tool

    def get(self, tool_id: str) -> Tool:
        try:
            return self._tools[tool_id]
        except KeyError as exc:
            raise KeyError("Unknown tool") from exc

    def list(self) -> list[Tool]:
        return list(self._tools.values())
