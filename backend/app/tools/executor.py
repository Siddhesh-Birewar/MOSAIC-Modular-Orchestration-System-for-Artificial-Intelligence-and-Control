"""The only execution path for registered tools."""

import asyncio
from dataclasses import dataclass
import json
import time
from typing import Any

from pydantic import ValidationError

from app.security.approvals import ApprovalError, ApprovalManager
from app.security.audit import AuditLog
from app.security.permissions import Decision, PermissionManager
from app.tools.base import ToolContext
from app.tools.registry import ToolRegistry


class ToolExecutionError(RuntimeError):
    def __init__(self, message: str, category: str) -> None:
        super().__init__(message)
        self.category = category


@dataclass
class ToolInvocation:
    state: str
    tool_id: str
    result: dict[str, Any] | None = None
    approval_id: str | None = None
    approval_expires_in: int | None = None
    safe_arguments: dict[str, Any] | None = None


class ToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        permissions: PermissionManager,
        approvals: ApprovalManager,
        audit: AuditLog,
        *,
        max_result_bytes: int = 32_768,
    ) -> None:
        self.registry = registry
        self.permissions = permissions
        self.approvals = approvals
        self.audit = audit
        self.max_result_bytes = max_result_bytes

    async def invoke(
        self,
        tool_id: str,
        raw_arguments: dict[str, Any],
        context: ToolContext,
        approval_id: str | None = None,
        timeout_cap: float | None = None,
    ) -> ToolInvocation:
        try:
            tool = self.registry.get(tool_id)
        except KeyError as exc:
            self.audit.record(
                tool_id="unknown", conversation_id=context.conversation_id,
                decision=Decision.DENY.value, execution_result="denied", error_category="unknown_tool",
            )
            raise ToolExecutionError("Unknown tool", "unknown_tool") from exc
        try:
            arguments = tool.input_model.model_validate(raw_arguments)
        except ValidationError as exc:
            self.audit.record(
                tool_id=tool_id, conversation_id=context.conversation_id,
                decision=Decision.DENY.value, execution_result="denied", error_category="invalid_arguments",
            )
            raise ToolExecutionError("Invalid tool arguments", "invalid_arguments") from exc

        decision = self.permissions.evaluate(tool_id, tool.required_permissions, arguments)
        if decision == Decision.DENY:
            self.audit.record(
                tool_id=tool_id, conversation_id=context.conversation_id,
                decision=decision.value, execution_result="denied", error_category="permission_denied",
            )
            raise ToolExecutionError("Permission denied", "permission_denied")
        if tool.requires_approval:
            decision = Decision.REQUIRE_APPROVAL

        validated_arguments = arguments.model_dump(mode="json")
        if decision == Decision.REQUIRE_APPROVAL and approval_id is None:
            approval = self.approvals.create(context.conversation_id, tool_id, validated_arguments)
            self.audit.record(
                tool_id=tool_id, conversation_id=context.conversation_id,
                decision=decision.value, approval_outcome="requested", execution_result="pending",
            )
            return ToolInvocation(
                state="approval_required",
                tool_id=tool_id,
                approval_id=approval.id,
                approval_expires_in=self.approvals.ttl_seconds,
                safe_arguments=validated_arguments,
            )
        if decision != Decision.REQUIRE_APPROVAL and approval_id is not None:
            raise ToolExecutionError("Unexpected approval for this action", "approval_mismatch")
        if decision == Decision.REQUIRE_APPROVAL:
            try:
                approval = self.approvals.consume(
                    approval_id or "", context.conversation_id, tool_id, validated_arguments
                )
            except ApprovalError as exc:
                self.audit.record(
                    tool_id=tool_id, conversation_id=context.conversation_id,
                    decision=decision.value, approval_outcome="invalid", execution_result="denied",
                    error_category="approval_invalid",
                )
                raise ToolExecutionError("Approval is invalid, expired, or already used", "approval_invalid") from exc
        else:
            approval = None

        started = time.monotonic()
        try:
            timeout = min(tool.timeout_seconds, timeout_cap) if timeout_cap is not None else tool.timeout_seconds
            if timeout <= 0:
                raise asyncio.TimeoutError
            output = await asyncio.wait_for(tool.execute(arguments, context), timeout=timeout)
            validated_output = tool.output_model.model_validate(output)
            result = validated_output.model_dump(mode="json")
            if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > self.max_result_bytes:
                raise ToolExecutionError("Tool result exceeds size limit", "result_too_large")
        except asyncio.TimeoutError as exc:
            self.audit.record(
                tool_id=tool_id, conversation_id=context.conversation_id, decision=decision.value,
                approval_outcome="approved" if approval else None, execution_result="failed",
                duration_seconds=round(time.monotonic() - started, 6), error_category="timeout",
            )
            raise ToolExecutionError("Tool execution timed out", "timeout") from exc
        except ToolExecutionError as exc:
            self.audit.record(
                tool_id=tool_id, conversation_id=context.conversation_id, decision=decision.value,
                approval_outcome="approved" if approval else None, execution_result="failed",
                duration_seconds=round(time.monotonic() - started, 6), error_category=exc.category,
            )
            raise
        except Exception as exc:
            self.audit.record(
                tool_id=tool_id, conversation_id=context.conversation_id, decision=decision.value,
                approval_outcome="approved" if approval else None, execution_result="failed",
                duration_seconds=round(time.monotonic() - started, 6),
                error_category=type(exc).__name__.lower(),
            )
            raise ToolExecutionError("Tool execution failed", "execution_error") from exc

        self.audit.record(
            tool_id=tool_id, conversation_id=context.conversation_id, decision=decision.value,
            approval_outcome="approved" if approval else None, execution_result="succeeded",
            duration_seconds=round(time.monotonic() - started, 6),
        )
        return ToolInvocation(state="completed", tool_id=tool_id, result=result)
