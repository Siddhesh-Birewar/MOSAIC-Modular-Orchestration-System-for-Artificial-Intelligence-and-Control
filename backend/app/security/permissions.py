"""Default-deny, tool-specific authorization policy."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from collections.abc import Callable


class Decision(StrEnum):
    DENY = "deny"
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"


@dataclass(frozen=True)
class PermissionRequirement:
    resource_type: str
    action: str


class PermissionManager:
    def __init__(
        self,
        file_access,
        allowed_applications: tuple[str, ...],
        application_available: Callable[[str], bool] | None = None,
    ) -> None:
        self.file_access = file_access
        self.allowed_applications = frozenset(allowed_applications)
        self.application_available = application_available or (lambda _name: False)

    def evaluate(self, tool_id: str, requirements: tuple[PermissionRequirement, ...], arguments) -> Decision:
        if not requirements:
            return Decision.DENY
        decision = Decision.ALLOW
        for requirement in requirements:
            if requirement.resource_type == "system" and requirement.action == "read":
                continue
            if requirement.resource_type == "filesystem" and requirement.action == "read":
                value = getattr(arguments, "path", None) or getattr(arguments, "root", None)
                if not value or self.file_access.authorized_root_for_path(value) is None:
                    return Decision.DENY
                continue
            if requirement.resource_type == "application" and requirement.action == "launch":
                name = getattr(arguments, "application", None)
                if name not in self.allowed_applications or not self.application_available(name):
                    return Decision.DENY
                return Decision.REQUIRE_APPROVAL
            return Decision.DENY
        return decision

    def inspect(self) -> dict:
        return {
            "default": Decision.DENY.value,
            "system_read": Decision.ALLOW.value,
            "filesystem_roots": [str(root) for root in self.file_access.roots],
            "applications": sorted(self.allowed_applications),
            "application_launch": Decision.REQUIRE_APPROVAL.value,
        }
