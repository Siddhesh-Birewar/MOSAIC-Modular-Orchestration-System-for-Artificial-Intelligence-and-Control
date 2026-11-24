import json
import httpx
import pytest

from scripts.chat import MosaicCLI, parse_sse


class Response:
    status_code = 200

    def __init__(self, payload=None, lines=None, error=None):
        self.payload = payload or {}
        self._lines = lines or []
        self.error = error
        self.closed = False

    def json(self):
        return self.payload

    def raise_for_status(self):
        return None

    def iter_lines(self):
        if self.error:
            raise self.error
        yield from self._lines

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True


class FakeClient:
    def __init__(self, stream_lines=None):
        self.calls = []
        self.stream_response = Response(lines=stream_lines or [])
        self.closed = False

    def post(self, url, json=None, headers=None):
        self.calls.append(("post", url, json, headers))
        if url.endswith("/conversations"):
            return Response({"id": "conversation-1", "model": (json or {}).get("model", "gpt-oss:20b")})
        return Response({"state": "approved"})

    def get(self, url):
        self.calls.append(("get", url))
        if url.endswith("/models"):
            return Response({"models": [{"name": "gpt-oss:20b", "loaded": True}]})
        return Response({"status": "ok"})

    def patch(self, url, json=None, headers=None):
        self.calls.append(("patch", url, json, headers))
        return Response({"model": json["model"]})

    def stream(self, method, url, json=None, headers=None):
        self.calls.append(("stream", method, url, json, headers))
        return self.stream_response

    def close(self):
        self.closed = True


def sse(event, payload):
    return [f"event: {event}", f"data: {json.dumps(payload)}", ""]


def test_parse_sse_events():
    entries = list(parse_sse([*sse("token", {"text": "hi"}), *sse("done", {"tool_calls": 0})]))
    assert entries == [("token", '{"text": "hi"}'), ("done", '{"tool_calls": 0}')]


def test_cli_commands_and_conversation_lifecycle():
    client = FakeClient()
    output = []
    cli = MosaicCLI("http://localhost:8000", token="opaque-test-token", client=client, output_fn=output.append)
    cli._new_conversation()
    assert cli.conversation_id == "conversation-1"
    assert cli.command("/model qwen3:8b")
    assert cli.model == "qwen3:8b"
    assert cli.command("/clear")
    assert cli.command("/models")
    assert cli.command("/status")
    assert cli.command("/metrics") and cli.show_metrics
    assert cli.command("/help")
    assert not cli.command("/exit")
    assert any("Commands:" in item for item in output)
    assert client.calls[-1][0] == "patch" or any(call[0] == "patch" for call in client.calls)
    assert next(call for call in client.calls if call[1].endswith("/conversations"))[3] == {
        "Authorization": "Bearer opaque-test-token"
    }
    assert next(call for call in client.calls if call[0] == "patch")[3] == {
        "Authorization": "Bearer opaque-test-token"
    }


def test_cli_streaming_metrics_and_approval():
    lines = [
        *sse("token", {"text": "hello "}),
        *sse("approval_required", {"approval_id": "approve-1", "tool_id": "applications_launch", "arguments": {"application": "Finder"}}),
        *sse("done", {"metrics": {"total_duration_seconds": 1}, "tool_calls": 1}),
    ]
    client = FakeClient(lines)
    writes, output = [], []
    cli = MosaicCLI(
        "http://localhost:8000", token="opaque-test-token", client=client,
        input_fn=lambda _prompt: "yes", output_fn=output.append, write_fn=writes.append,
    )
    cli.conversation_id = "conversation-1"
    cli.show_metrics = True
    cli.send_message("open Finder")
    assert writes == ["hello "]
    approval_call = next(call for call in client.calls if call[0] == "post" and "/approvals/" in call[1])
    assert approval_call[3] == {"Authorization": "Bearer opaque-test-token"}
    assert any("Metrics:" in item for item in output)


def test_cli_cancellation_closes_stream():
    client = FakeClient()
    client.stream_response = Response(error=KeyboardInterrupt())
    cli = MosaicCLI("http://localhost:8000", client=client, output_fn=lambda _line: None)
    cli.conversation_id = "conversation-1"
    with pytest.raises(KeyboardInterrupt):
        cli.send_message("cancel")
    assert client.stream_response.closed


def test_cli_reports_network_errors_and_closes_client():
    class FailingClient(FakeClient):
        def post(self, url, json=None, headers=None):
            raise httpx.ConnectError("offline")

    client = FailingClient()
    output = []
    cli = MosaicCLI("http://localhost:8000", client=client, output_fn=output.append)
    cli.run()
    assert any("Backend connection error" in line for line in output)
    assert client.closed
