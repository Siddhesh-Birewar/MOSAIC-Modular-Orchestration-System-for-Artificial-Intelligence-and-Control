"""Read-only local system monitoring tools."""

from datetime import timedelta
import platform
import shutil
import time

import psutil

from app.security.permissions import PermissionRequirement
from app.tools.base import RiskLevel, Tool, ToolContext
from app.tools.schemas import EmptyInput, ObjectOutput


SYSTEM_READ = (PermissionRequirement("system", "read"),)


class CpuUsageTool(Tool):
    tool_id = "system_cpu_usage"
    description = "Read a brief system-wide CPU utilization measurement."
    input_model = EmptyInput
    output_model = ObjectOutput
    risk = RiskLevel.LOW
    required_permissions = SYSTEM_READ
    timeout_seconds = 2

    async def execute(self, arguments, context: ToolContext) -> ObjectOutput:
        try:
            value = psutil.cpu_percent(interval=0.1)
        except (OSError, PermissionError, NotImplementedError):
            value = None
        return ObjectOutput(result={"available": value is not None, "cpu_percent": value})


class MemoryTool(Tool):
    tool_id = "system_memory"
    description = "Read total and currently available physical memory."
    input_model = EmptyInput
    output_model = ObjectOutput
    risk = RiskLevel.LOW
    required_permissions = SYSTEM_READ

    async def execute(self, arguments, context: ToolContext) -> ObjectOutput:
        try:
            memory = psutil.virtual_memory()
        except (OSError, PermissionError, NotImplementedError):
            return ObjectOutput(result={"available": False, "total_bytes": None, "available_bytes": None})
        return ObjectOutput(result={"available": True, "total_bytes": memory.total, "available_bytes": memory.available})


class BatteryTool(Tool):
    tool_id = "system_battery"
    description = "Read battery percentage and charging state when the device reports them."
    input_model = EmptyInput
    output_model = ObjectOutput
    risk = RiskLevel.LOW
    required_permissions = SYSTEM_READ

    async def execute(self, arguments, context: ToolContext) -> ObjectOutput:
        try:
            battery = psutil.sensors_battery()
        except (OSError, NotImplementedError):
            battery = None
        if battery is None:
            return ObjectOutput(result={"available": False, "percentage": None, "charging": None})
        return ObjectOutput(result={
            "available": True,
            "percentage": round(battery.percent, 1),
            "charging": battery.power_plugged,
        })


class DiskTool(Tool):
    tool_id = "system_disk"
    description = "Read total and available capacity for the system volume."
    input_model = EmptyInput
    output_model = ObjectOutput
    risk = RiskLevel.LOW
    required_permissions = SYSTEM_READ

    async def execute(self, arguments, context: ToolContext) -> ObjectOutput:
        try:
            disk = shutil.disk_usage("/")
        except OSError:
            return ObjectOutput(result={"available": False, "total_bytes": None, "available_bytes": None})
        return ObjectOutput(result={"available": True, "total_bytes": disk.total, "available_bytes": disk.free})


class OperatingSystemTool(Tool):
    tool_id = "system_macos_version"
    description = "Read the operating system name and macOS version without device identifiers."
    input_model = EmptyInput
    output_model = ObjectOutput
    risk = RiskLevel.LOW
    required_permissions = SYSTEM_READ

    async def execute(self, arguments, context: ToolContext) -> ObjectOutput:
        version, _, _ = platform.mac_ver()
        return ObjectOutput(result={"system": platform.system(), "version": version or None})


class UptimeTool(Tool):
    tool_id = "system_uptime"
    description = "Read approximate system uptime."
    input_model = EmptyInput
    output_model = ObjectOutput
    risk = RiskLevel.LOW
    required_permissions = SYSTEM_READ

    async def execute(self, arguments, context: ToolContext) -> ObjectOutput:
        try:
            seconds = max(0, int(time.time() - psutil.boot_time()))
        except (OSError, PermissionError, NotImplementedError):
            return ObjectOutput(result={"available": False, "seconds": None, "human": None})
        return ObjectOutput(result={"available": True, "seconds": seconds, "human": str(timedelta(seconds=seconds))})


class RunningOllamaModelsTool(Tool):
    tool_id = "system_ollama_models"
    description = "List Ollama models currently loaded in memory."
    input_model = EmptyInput
    output_model = ObjectOutput
    risk = RiskLevel.LOW
    required_permissions = SYSTEM_READ

    async def execute(self, arguments, context: ToolContext) -> ObjectOutput:
        models = await context.services["ollama"].running_models()
        return ObjectOutput(result={"models": [
            {key: item[key] for key in ("name", "size", "size_vram", "expires_at") if key in item}
            for item in models
        ]})
