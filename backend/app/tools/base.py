"""Typed base contract for built-in and future MOSAIC tools."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from app.security.permissions import PermissionRequirement


InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ToolContext:
    conversation_id: str
    services: dict[str, Any]


class Tool(ABC, Generic[InputT, OutputT]):
    tool_id: str
    description: str
    input_model: type[InputT]
    output_model: type[OutputT]
    risk: RiskLevel
    required_permissions: tuple[PermissionRequirement, ...]
    timeout_seconds: float = 5.0
    requires_approval: bool = False

    @abstractmethod
    async def execute(self, arguments: InputT, context: ToolContext) -> OutputT:
        """Execute validated arguments within the declared capability."""

    def manifest(self) -> dict[str, Any]:
        schema = self.input_model.model_json_schema()
        return {
            "id": self.tool_id,
            "description": self.description,
            "input_schema": schema,
            "risk": self.risk.value,
            "required_permissions": [
                {"resource_type": item.resource_type, "action": item.action}
                for item in self.required_permissions
            ],
            "approval_required": self.requires_approval,
        }

    def ollama_definition(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.tool_id,
                "description": self.description,
                "parameters": self.input_model.model_json_schema(),
            },
        }
