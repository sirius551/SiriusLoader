from __future__ import annotations

import json
import os
import queue
import secrets
import threading
import time
import uuid
from collections import deque
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Render provides RENDER_EXTERNAL_HOSTNAME automatically. Locally, set
# SIRIUS_ALLOWED_HOST to the hostname used by your test server.
HOSTNAME = os.environ.get("SIRIUS_ALLOWED_HOST") or os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if not HOSTNAME:
    raise RuntimeError("Set RENDER_EXTERNAL_HOSTNAME (Render) or SIRIUS_ALLOWED_HOST")

TOKEN = os.environ.get("SIRIUS_MCP_TOKEN", "").strip()
if len(TOKEN) < 32:
    raise RuntimeError("Set SIRIUS_MCP_TOKEN to a random secret of at least 32 characters")

PORT = int(os.environ.get("PORT", "10000"))
COMMAND_TIMEOUT = int(os.environ.get("SIRIUS_COMMAND_TIMEOUT", "25"))
STATE_STALE_SECONDS = int(os.environ.get("SIRIUS_STATE_STALE_SECONDS", "8"))

COMMANDS: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=100)
PENDING: dict[str, dict[str, Any]] = {}
PENDING_LOCK = threading.Lock()
STATE: dict[str, Any] = {"connected": False, "updated_at": None}
STATE_LOCK = threading.Lock()
LOGS: deque[dict[str, Any]] = deque(maxlen=500)
LOG_LOCK = threading.Lock()


def log_event(event: str, **details: Any) -> None:
    record = {"time": time.time(), "event": event, **details}
    with LOG_LOCK:
        LOGS.append(record)
    print(json.dumps(record, ensure_ascii=False, default=str), flush=True)


def queue_command(kind: str, **payload: Any) -> dict[str, Any]:
    command_id = uuid.uuid4().hex
    event = threading.Event()
    record = {"id": command_id, "type": kind, **payload}
    with PENDING_LOCK:
        if len(PENDING) >= 100:
            return {"ok": False, "error": "Too many pending commands. Wait for existing commands to finish."}
        PENDING[command_id] = {"event": event, "result": None, "created": time.time()}
    try:
        COMMANDS.put_nowait(record)
    except queue.Full:
        with PENDING_LOCK:
            PENDING.pop(command_id, None)
        return {"ok": False, "error": "Command queue is full"}
    log_event("command_queued", command_id=command_id, command_type=kind)
    if not event.wait(timeout=COMMAND_TIMEOUT):
        with PENDING_LOCK:
            PENDING.pop(command_id, None)
        log_event("command_timeout", command_id=command_id, command_type=kind)
        return {
            "queued": True,
            "id": command_id,
            "status": "timeout",
            "message": "Loader did not answer in time. Check that Roblox is running and the bridge is connected.",
        }
    with PENDING_LOCK:
        item = PENDING.pop(command_id, None)
    result = (item or {}).get("result") or {"id": command_id, "ok": False, "error": "No result returned"}
    log_event("command_result", command_id=command_id, command_type=kind, ok=result.get("ok", False))
    return result


class TokenAuthMiddleware:
    """Require the shared secret for MCP and every private bridge endpoint."""

    def __init__(self, app: Any):
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path == "/health":
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        supplied = headers.get(b"x-sirius-token", b"").decode("utf-8", "ignore")
        if not supplied:
            auth = headers.get(b"authorization", b"").decode("utf-8", "ignore")
            if auth.lower().startswith("bearer "):
                supplied = auth[7:].strip()

        if not secrets.compare_digest(supplied, TOKEN):
            response = JSONResponse({"error": "unauthorized"}, status_code=401)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


mcp = FastMCP("Sirius Loader MCP")


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> Response:
    return JSONResponse({"ok": True, "service": "Sirius MCP bridge"})


@mcp.custom_route("/poll", methods=["GET"])
async def poll(_: Request) -> Response:
    try:
        command = COMMANDS.get_nowait()
    except queue.Empty:
        command = None
    return JSONResponse({"command": command})


@mcp.custom_route("/result", methods=["POST"])
async def result(request: Request) -> Response:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)
    command_id = str(body.get("id", ""))
    with PENDING_LOCK:
        item = PENDING.get(command_id)
        if item:
            item["result"] = body
            item["event"].set()
    if not item:
        log_event("orphan_result", command_id=command_id)
    return JSONResponse({"ok": bool(item)})


@mcp.custom_route("/state", methods=["POST"])
async def update_state(request: Request) -> Response:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "state must be an object"}, status_code=400)
    safe_state = {
        key: value for key, value in body.items()
        if key in {"player", "placeId", "jobId", "health", "position"}
    }
    with STATE_LOCK:
        previous_connected = STATE.get("connected", False)
        STATE.clear()
        STATE.update(safe_state)
        STATE["connected"] = True
        STATE["updated_at"] = time.time()
    if not previous_connected:
        log_event("loader_connected", player=safe_state.get("player"), place_id=safe_state.get("placeId"))
    return JSONResponse({"ok": True})


@mcp.custom_route("/logs", methods=["POST"])
async def receive_logs(request: Request) -> Response:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)
    entries = body.get("entries", []) if isinstance(body, dict) else []
    if not isinstance(entries, list):
        return JSONResponse({"error": "entries must be a list"}, status_code=400)
    accepted = 0
    for entry in entries[-50:]:
        if isinstance(entry, (str, int, float, bool)):
            log_event("loader_log", message=str(entry)[:1000])
            accepted += 1
        elif isinstance(entry, dict):
            log_event("loader_log", **{str(k)[:40]: str(v)[:500] for k, v in list(entry.items())[:12]})
            accepted += 1
    return JSONResponse({"ok": True, "accepted": accepted})


@mcp.tool()
def sirius_connection_status() -> dict[str, Any]:
    """Return whether Sirius Loader has sent a recent heartbeat to the cloud bridge."""
    with STATE_LOCK:
        state = dict(STATE)
    updated = state.get("updated_at")
    connected = bool(updated and time.time() - float(updated) <= STATE_STALE_SECONDS)
    state["connected"] = connected
    return {"bridge": "online", **state}


@mcp.tool()
def sirius_get_status() -> dict[str, Any]:
    """Get the latest player, place, health and position status reported by Sirius Loader."""
    with STATE_LOCK:
        updated = STATE.get("updated_at")
        state = dict(STATE)
    if not updated or time.time() - float(updated) > STATE_STALE_SECONDS:
        return {"ok": False, "connected": False, "error": "Sirius Loader is offline or its heartbeat is stale"}
    return {"ok": True, **state}


@mcp.tool()
def sirius_list_controls() -> dict[str, Any]:
    """List registered Sirius toggle/slider controls and bindable actions."""
    return queue_command("list_controls")


@mcp.tool()
def sirius_set_toggle(control_id: str, enabled: bool) -> dict[str, Any]:
    """Set a registered Sirius toggle. Use an exact id returned by sirius_list_controls."""
    return queue_command("set_toggle", id=control_id, value=enabled)


@mcp.tool()
def sirius_run_action(action_id: str) -> dict[str, Any]:
    """Run a registered Sirius button action. Use an exact id returned by sirius_list_controls."""
    return queue_command("run_action", id=action_id)


@mcp.tool()
def sirius_set_slider(control_id: str, value: float) -> dict[str, Any]:
    """Set a registered Sirius slider. The Loader validates the control and its range."""
    return queue_command("set_slider", id=control_id, value=value)


@mcp.tool()
def sirius_create_lua_script(filename: str, code: str) -> dict[str, Any]:
    """Return Lua source as text for the user to save manually. This tool does not write to the cloud filesystem or execute code."""
    safe_name = filename.replace("\\", "/").split("/")[-1][:100]
    if not safe_name.lower().endswith(".lua"):
        safe_name += ".lua"
    if safe_name in {"", ".", ".."} or not code.strip() or len(code) > 100_000:
        return {"ok": False, "error": "Invalid filename or script is empty/too large"}
    log_event("lua_script_prepared", filename=safe_name, bytes=len(code))
    return {"ok": True, "filename": safe_name, "code": code, "saved": False, "executed": False}


@mcp.tool()
def sirius_execute_lua(code: str, confirm_risk: bool = False) -> dict[str, Any]:
    """Execute Lua in the active game executor. Requires explicit user approval for this exact code via confirm_risk=true."""
    if confirm_risk is not True:
        return {"ok": False, "error": "Blocked. Obtain the user's explicit approval for this exact code, then call again with confirm_risk=true."}
    if not code.strip() or len(code) > 100_000:
        return {"ok": False, "error": "Code must be non-empty and at most 100 KB"}
    log_event("lua_execution_requested", bytes=len(code), approval=True)
    return queue_command("execute_lua", code=code, confirm_risk=True)


@mcp.tool()
def sirius_capture_screenshot() -> dict[str, Any]:
    """Desktop screenshots are unavailable on Render because the cloud service cannot capture the user's local screen."""
    return {"ok": False, "error": "Screenshot capture is unavailable in cloud mode. It requires a separate local screenshot source."}


@mcp.tool()
def sirius_read_recent_logs(max_lines: int = 100) -> dict[str, Any]:
    """Read recent cloud bridge events and Loader heartbeat/command logs."""
    limit = max(1, min(int(max_lines), 500))
    with LOG_LOCK:
        entries = list(LOGS)[-limit:]
    return {"ok": True, "lines": entries}


security = TransportSecuritySettings(
    allowed_hosts=[HOSTNAME, f"{HOSTNAME}:*"],
)
mcp_app = mcp.streamable_http_app(
    transport_security=security,
    host="0.0.0.0",
)
app = TokenAuthMiddleware(mcp_app)
