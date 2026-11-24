"""Construction of MOSAIC's explicit built-in tool registry."""

from app.tools.builtin.applications import LaunchApplicationTool
from app.tools.builtin.files import (
    FileAccess,
    FileMetadataTool,
    ListDirectoryTool,
    ReadTextFileTool,
    SearchFilesTool,
)
from app.tools.builtin.system import (
    BatteryTool,
    CpuUsageTool,
    DiskTool,
    MemoryTool,
    OperatingSystemTool,
    RunningOllamaModelsTool,
    UptimeTool,
)
from app.tools.registry import ToolRegistry


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for tool in (
        CpuUsageTool(), MemoryTool(), BatteryTool(), DiskTool(), OperatingSystemTool(),
        UptimeTool(), RunningOllamaModelsTool(), ListDirectoryTool(), SearchFilesTool(),
        ReadTextFileTool(), FileMetadataTool(), LaunchApplicationTool(),
    ):
        registry.register(tool)
    return registry


__all__ = ["FileAccess", "build_registry"]
