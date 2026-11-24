import asyncio
import os
from pathlib import Path
import sys
import time

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.security.approvals import ApprovalError, ApprovalManager
from app.security.audit import AuditLog
from app.security.permissions import Decision, PermissionManager, PermissionRequirement
from app.tools.base import RiskLevel, Tool, ToolContext
from app.tools.builtin.applications import LaunchApplicationTool
from app.tools.builtin.files import FileAccess
from app.tools.builtin.system import BatteryTool, CpuUsageTool, DiskTool, MemoryTool, UptimeTool
from app.tools.executor import ToolExecutionError, ToolExecutor
from app.tools.registry import ToolRegistry
from app.tools.schemas import EmptyInput, ObjectOutput


class AllowedNoop(Tool):
    tool_id = "test_noop"
    description = "Test only."
    input_model = EmptyInput
    output_model = ObjectOutput
    risk = RiskLevel.LOW
    required_permissions = (PermissionRequirement("system", "read"),)

    async def execute(self, arguments, context):
        return ObjectOutput(result={"ok": True})


class SlowTool(AllowedNoop):
    tool_id = "test_slow"
    timeout_seconds = 0.01

    async def execute(self, arguments, context):
        await asyncio.sleep(1)
        return ObjectOutput(result={"ok": True})


def test_registry_rejects_duplicate_ids_and_executor_validates_arguments():
    registry = ToolRegistry()
    tool = AllowedNoop()
    registry.register(tool)
    with pytest.raises(ValueError):
        registry.register(tool)
    executor = ToolExecutor(
        registry,
        PermissionManager(FileAccess(()), ()),
        ApprovalManager(),
        AuditLog(),
    )

    async def check():
        with pytest.raises(ToolExecutionError, match="Invalid tool arguments"):
            await executor.invoke("test_noop", {"shell": "id"}, ToolContext("c", {}))
        with pytest.raises(ToolExecutionError, match="Unknown tool"):
            await executor.invoke("unknown", {}, ToolContext("c", {}))

    asyncio.run(check())


def test_default_deny_filesystem_permissions_and_authorized_root(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    secret = tmp_path / "outside.txt"
    secret.write_text("private")
    access = FileAccess((str(allowed),))
    manager = PermissionManager(access, ())
    requirement = (PermissionRequirement("filesystem", "read"),)
    assert manager.evaluate("filesystem_read_text_file", requirement, type("Args", (), {"path": str(allowed)})()) == Decision.ALLOW
    assert manager.evaluate("filesystem_read_text_file", requirement, type("Args", (), {"path": str(secret)})()) == Decision.DENY
    assert manager.evaluate("unknown", (), object()) == Decision.DENY
    assert FileAccess(()).authorized_root_for_path(str(allowed)) is None


def test_file_access_blocks_traversal_symlinks_sensitive_and_special_files(tmp_path):
    root = tmp_path / "authorized"
    root.mkdir()
    text = root / "notes.txt"
    text.write_text("safe text", encoding="utf-8")
    (root / ".env.local").write_text("secret", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    (root / "escape.txt").symlink_to(outside)
    access = FileAccess((str(root),), max_file_bytes=20)
    assert access.read_text(str(text))["content"] == "safe text"
    assert not any(entry["name"].startswith(".env") for entry in access.list_directory(str(root)))
    assert access.authorized_root_for_path(str(root / ".." / "outside.txt")) is None
    assert access.authorized_root_for_path(str(root / "escape.txt")) is None
    with pytest.raises((PermissionError, OSError)):
        access.read_text(str(root / "escape.txt"))
    large = root / "large.txt"
    large.write_text("x" * 30)
    with pytest.raises(ValueError, match="size limit"):
        access.read_text(str(large))
    if hasattr(os, "mkfifo"):
        fifo = root / "pipe"
        os.mkfifo(fifo)
        with pytest.raises(ValueError, match="regular files"):
            access.read_text(str(fifo))


def test_search_is_bounded_and_does_not_follow_symlinks(tmp_path):
    root = tmp_path / "search-root"
    root.mkdir()
    for name in ("one.txt", "two.txt", "three.txt"):
        (root / name).write_text(name)
    (root / "linked").symlink_to(tmp_path, target_is_directory=True)
    access = FileAccess((str(root),))
    results = access.search(str(root), ".txt", 2)
    assert len(results) == 2
    assert all("outside.txt" not in value for value in results)


def test_system_tools_return_real_safe_measurements(monkeypatch):
    async def check():
        context = ToolContext("c", {})
        cpu = await CpuUsageTool().execute(EmptyInput(), context)
        memory = await MemoryTool().execute(EmptyInput(), context)
        battery = await BatteryTool().execute(EmptyInput(), context)
        disk = await DiskTool().execute(EmptyInput(), context)
        uptime = await UptimeTool().execute(EmptyInput(), context)
        assert not cpu.result["available"] or 0 <= cpu.result["cpu_percent"] <= 100
        assert not memory.result["available"] or memory.result["total_bytes"] >= memory.result["available_bytes"] > 0
        assert isinstance(battery.result["available"], bool)
        assert not disk.result["available"] or disk.result["total_bytes"] >= disk.result["available_bytes"] > 0
        assert not uptime.result["available"] or uptime.result["seconds"] >= 0

    asyncio.run(check())


def test_application_launch_requires_bound_user_approval_and_uses_fixed_open(monkeypatch):
    from app.tools.builtin import applications

    calls = []
    monkeypatch.setattr(applications.sys, "platform", "darwin")
    monkeypatch.setattr(Path, "is_dir", lambda _path: True)
    monkeypatch.setattr(applications.subprocess, "Popen", lambda args, **kwargs: calls.append((args, kwargs)))
    tool = LaunchApplicationTool()
    registry = ToolRegistry()
    registry.register(tool)
    approvals = ApprovalManager()
    executor = ToolExecutor(
        registry,
        PermissionManager(FileAccess(()), ("Finder",), application_available=lambda name: name == "Finder"),
        approvals,
        AuditLog(),
    )

    async def check():
        context = ToolContext("conversation-1", {"allowed_applications": ("Finder",)})
        pending = await executor.invoke("applications_launch", {"application": "Finder"}, context)
        assert pending.state == "approval_required" and calls == []
        approvals.decide(pending.approval_id, True)
        completed = await executor.invoke(
            "applications_launch", {"application": "Finder"}, context, pending.approval_id
        )
        assert completed.state == "completed"
        assert calls == [(
            ["/usr/bin/open", "-a", "/System/Library/CoreServices/Finder.app"],
            {"shell": False, "close_fds": True},
        )]

    asyncio.run(check())
    assert len(calls) == 1
    assert calls[0][1]["shell"] is False


def test_approval_expiration_replay_and_changed_arguments():
    approvals = ApprovalManager(ttl_seconds=1)
    changed = approvals.create("c", "tool", {"x": 1})
    approvals.decide(changed.id, True)
    with pytest.raises(ApprovalError, match="does not match"):
        approvals.consume(changed.id, "c", "tool", {"x": 2})
    with pytest.raises(ApprovalError):
        approvals.consume(changed.id, "c", "tool", {"x": 1})

    replay = approvals.create("c", "tool", {"x": 1})
    approvals.decide(replay.id, True)
    approvals.consume(replay.id, "c", "tool", {"x": 1})
    with pytest.raises(ApprovalError, match="no longer"):
        approvals.consume(replay.id, "c", "tool", {"x": 1})

    expired_manager = ApprovalManager(ttl_seconds=0.01)
    expired = expired_manager.create("c", "tool", {})
    time.sleep(0.02)
    with pytest.raises(ApprovalError, match="expired"):
        expired_manager.decide(expired.id, True)


def test_executor_timeout_and_audit_never_records_arguments():
    registry = ToolRegistry()
    registry.register(SlowTool())
    audit = AuditLog(capacity=2)
    executor = ToolExecutor(registry, PermissionManager(FileAccess(()), ()), ApprovalManager(), audit)

    async def check():
        with pytest.raises(ToolExecutionError, match="timed out"):
            await executor.invoke("test_slow", {}, ToolContext("c", {}))

    asyncio.run(check())
    assert audit.recent()[0]["error_category"] == "timeout"
    assert "arguments" not in str(audit.recent()) and "content" not in str(audit.recent())
    for index in range(4):
        audit.record(tool_id="x", conversation_id="c", decision="deny", execution_result="denied")
    assert len(audit.recent()) == 2


def test_action_api_rejects_unauthenticated_and_allows_authenticated_read_tool():
    settings = Settings(api_token="t" * 40)
    with TestClient(create_app(settings)) as client:
        assert client.get("/tools").status_code == 200
        assert client.get("/permissions").status_code == 401
        conversation_id = "e25c1f18-ea83-4fc6-a93b-329d6797ae42"
        assert client.post("/tools/invoke", json={"tool_id": "system_memory", "arguments": {}, "conversation_id": conversation_id}).status_code == 401
        headers = {"Authorization": f"Bearer {'t' * 40}"}
        response = client.post(
            "/tools/invoke",
            json={"tool_id": "system_memory", "arguments": {}, "conversation_id": conversation_id},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["result"]["result"]["total_bytes"] > 0
        assert client.get("/audit", headers=headers).status_code == 200
        pending = client.app.state.approvals.create(conversation_id, "applications_launch", {"application": "Finder"})
        assert client.get("/approvals").status_code == 401
        assert any(item["id"] == pending.id for item in client.get("/approvals", headers=headers).json()["approvals"])
        decision = client.post(
            f"/approvals/{pending.id}/decision", json={"approved": False}, headers=headers
        )
        assert decision.status_code == 200 and decision.json()["state"] == "rejected"
        assert client.post(
            "/tools/invoke",
            json={"tool_id": "filesystem_read_text_file", "arguments": {"path": "/tmp/private.txt"}, "conversation_id": conversation_id},
            headers=headers,
        ).status_code == 403
