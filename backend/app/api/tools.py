"""Authenticated tool execution, approval, permission, and audit API."""

import hmac
import time
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.security.approvals import ApprovalError
from app.security.permissions import Decision
from app.tools.base import ToolContext
from app.tools.executor import ToolExecutionError

router = APIRouter()


class ToolInvokeRequest(BaseModel):
    tool_id: str = Field(min_length=1, max_length=120)
    arguments: dict[str, Any]
    conversation_id: UUID
    approval_id: str | None = Field(default=None, max_length=40)


class ApprovalDecisionRequest(BaseModel):
    approved: bool


async def require_local_token(request: Request, authorization: str | None = Header(default=None)) -> None:
    expected = request.app.state.settings.api_token
    if not expected:
        raise HTTPException(status_code=503, detail="Tool security endpoints are disabled until MOSAIC_API_TOKEN is configured")
    if not local_token_is_valid(request, authorization):
        raise HTTPException(status_code=401, detail="Bearer authentication required")


def local_token_is_valid(request: Request, authorization: str | None = None) -> bool:
    expected = request.app.state.settings.api_token
    value = authorization if authorization is not None else request.headers.get("authorization")
    if not expected or not value or not value.startswith("Bearer "):
        return False
    return hmac.compare_digest(value.removeprefix("Bearer "), expected)


def _invocation_data(invocation) -> dict[str, Any]:
    return {
        "state": invocation.state,
        "tool_id": invocation.tool_id,
        "result": invocation.result,
        "approval": ({
            "id": invocation.approval_id,
            "expires_in_seconds": invocation.approval_expires_in,
            "arguments": invocation.safe_arguments,
        } if invocation.approval_id else None),
    }


@router.get("/tools")
async def list_tools(request: Request) -> dict[str, Any]:
    return {"tools": [tool.manifest() for tool in request.app.state.tool_registry.list()]}


@router.post("/tools/invoke", dependencies=[Depends(require_local_token)])
async def invoke_tool(body: ToolInvokeRequest, request: Request) -> dict[str, Any]:
    try:
        invocation = await request.app.state.tool_executor.invoke(
            body.tool_id,
            body.arguments,
            ToolContext(str(body.conversation_id), request.app.state.tool_services),
            body.approval_id,
        )
    except ToolExecutionError as exc:
        status = {
            "unknown_tool": 404,
            "invalid_arguments": 422,
            "permission_denied": 403,
            "approval_invalid": 409,
            "timeout": 504,
        }.get(exc.category, 502)
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    return _invocation_data(invocation)


@router.get("/approvals", dependencies=[Depends(require_local_token)])
async def list_approvals(request: Request) -> dict[str, Any]:
    return {"approvals": [
        {"id": item.id, "conversation_id": item.conversation_id, "tool_id": item.tool_id,
         "expires_in_seconds": max(0, int(item.expires_at - time.monotonic()))}
        for item in request.app.state.approvals.pending()
    ]}


@router.post("/approvals/{approval_id}/decision", dependencies=[Depends(require_local_token)])
async def decide_approval(
    approval_id: str, body: ApprovalDecisionRequest, request: Request
) -> dict[str, str]:
    try:
        approval = request.app.state.approvals.decide(approval_id, body.approved)
    except ApprovalError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    decision = "approved" if body.approved else "denied"
    request.app.state.audit.record(
        tool_id=approval.tool_id,
        conversation_id=approval.conversation_id,
        decision=Decision.REQUIRE_APPROVAL.value,
        approval_outcome=decision,
        execution_result="pending" if body.approved else "denied",
        error_category=None if body.approved else "user_rejected",
    )
    return {"id": approval.id, "state": approval.state}


@router.get("/permissions", dependencies=[Depends(require_local_token)])
async def inspect_permissions(request: Request) -> dict[str, Any]:
    return request.app.state.permission_manager.inspect()


@router.get("/audit", dependencies=[Depends(require_local_token)])
async def audit_history(request: Request, limit: int = 100) -> dict[str, Any]:
    return {"events": request.app.state.audit.recent(limit)}
