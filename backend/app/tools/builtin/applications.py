"""Allowlisted application launcher; launches always require approval."""

import subprocess
import sys
from pathlib import Path

from app.security.permissions import PermissionRequirement
from app.tools.base import RiskLevel, Tool, ToolContext
from app.tools.schemas import ApplicationInput, ObjectOutput


APPLICATION_CANDIDATES = {
    "Visual Studio Code": ("/Applications/Visual Studio Code.app",),
    "Finder": ("/System/Library/CoreServices/Finder.app",),
    "Calculator": ("/System/Applications/Calculator.app",),
    "Notes": ("/System/Applications/Notes.app",),
    "Safari": ("/System/Applications/Safari.app", "/Applications/Safari.app"),
    "Google Chrome": ("/Applications/Google Chrome.app",),
}


def installed_application_path(name: str) -> str | None:
    return next((path for path in APPLICATION_CANDIDATES.get(name, ()) if Path(path).is_dir()), None)


class LaunchApplicationTool(Tool):
    tool_id = "applications_launch"
    description = "Open one named, allowlisted macOS application after explicit user approval."
    input_model = ApplicationInput
    output_model = ObjectOutput
    risk = RiskLevel.HIGH
    required_permissions = (PermissionRequirement("application", "launch"),)
    timeout_seconds = 3
    requires_approval = True

    async def execute(self, arguments, context: ToolContext) -> ObjectOutput:
        name = arguments.application
        if sys.platform != "darwin":
            raise RuntimeError("macOS application launching is unavailable")
        if name not in context.services["allowed_applications"]:
            raise PermissionError("Application is not on the configured allowlist")
        installed = installed_application_path(name)
        if installed is None:
            raise FileNotFoundError("Allowlisted application is not installed")
        subprocess.Popen(["/usr/bin/open", "-a", installed], shell=False, close_fds=True)
        return ObjectOutput(result={"application": name, "status": "launch_requested"})
