"""Short-lived, argument-bound, single-use user approvals."""

import asyncio
from dataclasses import dataclass, field
import hashlib
import json
import secrets
import time


class ApprovalError(ValueError):
    pass


def argument_digest(arguments: dict) -> str:
    encoded = json.dumps(arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass
class Approval:
    id: str
    conversation_id: str
    tool_id: str
    argument_hash: str
    expires_at: float
    state: str = "pending"
    event: asyncio.Event = field(default_factory=asyncio.Event)


class ApprovalManager:
    def __init__(self, ttl_seconds: int = 90, max_records: int = 500) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_records = max(10, max_records)
        self._items: dict[str, Approval] = {}

    def create(self, conversation_id: str, tool_id: str, arguments: dict) -> Approval:
        now = time.monotonic()
        self._items = {
            key: item for key, item in self._items.items()
            if item.expires_at > now and item.state in ("pending", "approved")
        }
        if len(self._items) >= self.max_records:
            oldest = next(iter(self._items))
            self._items.pop(oldest, None)
        approval_id = secrets.token_urlsafe(6)
        while approval_id in self._items:
            approval_id = secrets.token_urlsafe(6)
        approval = Approval(
            id=approval_id,
            conversation_id=conversation_id,
            tool_id=tool_id,
            argument_hash=argument_digest(arguments),
            expires_at=time.monotonic() + self.ttl_seconds,
        )
        self._items[approval.id] = approval
        return approval

    def decide(self, approval_id: str, approved: bool) -> Approval:
        approval = self._get_live(approval_id)
        if approval.state != "pending":
            raise ApprovalError("Approval is no longer pending")
        approval.state = "approved" if approved else "rejected"
        approval.event.set()
        return approval

    async def wait(self, approval_id: str, timeout_seconds: float | None = None) -> Approval:
        approval = self._get_live(approval_id)
        remaining = max(0, approval.expires_at - time.monotonic())
        if timeout_seconds is not None:
            remaining = min(remaining, max(0, timeout_seconds))
        try:
            await asyncio.wait_for(approval.event.wait(), timeout=remaining)
        except TimeoutError as exc:
            approval.state = "expired"
            raise ApprovalError("Approval expired") from exc
        return self._get_live(approval_id)

    def consume(self, approval_id: str, conversation_id: str, tool_id: str, arguments: dict) -> Approval:
        approval = self._get_live(approval_id)
        if approval.state != "approved":
            if approval.state in ("consumed", "rejected", "expired"):
                raise ApprovalError("Approval is no longer valid")
            raise ApprovalError("Approval has not been granted")
        if (
            approval.conversation_id != conversation_id
            or approval.tool_id != tool_id
            or not secrets.compare_digest(approval.argument_hash, argument_digest(arguments))
        ):
            approval.state = "rejected"
            approval.event.set()
            raise ApprovalError("Approval does not match this invocation")
        approval.state = "consumed"
        return approval

    def get(self, approval_id: str) -> Approval:
        return self._get_live(approval_id)

    def pending(self) -> list[Approval]:
        now = time.monotonic()
        return [item for item in self._items.values() if item.state == "pending" and item.expires_at > now]

    def _get_live(self, approval_id: str) -> Approval:
        approval = self._items.get(approval_id)
        if approval is None:
            raise ApprovalError("Unknown approval")
        if time.monotonic() >= approval.expires_at and approval.state not in ("consumed", "rejected"):
            approval.state = "expired"
            approval.event.set()
            raise ApprovalError("Approval expired")
        return approval
