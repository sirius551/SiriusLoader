from __future__ import annotations

import base64
import contextvars
import hashlib
import hmac
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
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

HOSTNAME = os.environ.get("SIRIUS_ALLOWED_HOST") or os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if not HOSTNAME:
    raise RuntimeError("Set RENDER_EXTERNAL_HOSTNAME (Render) or SIRIUS_ALLOWED_HOST")

SIGNING_SECRET = os.environ.get("SIRIUS_MCP_TOKEN", "").strip().encode("utf-8")
if len(SIGNING_SECRET) < 32:
    raise RuntimeError("Set SIRIUS_MCP_TOKEN to a random secret of at least 32 characters")

PORT = int(os.environ.get("PORT", "10000"))
COMMAND_TIMEOUT = int(os.environ.get("SIRIUS_COMMAND_TIMEOUT", "25"))
STATE_STALE_SECONDS = int(os.environ.get("SIRIUS_STATE_STALE_SECONDS", "8"))
TOKEN_TTL_SECONDS = 365 * 24 * 60 * 60
DEVICE_QUEUES: dict[str, queue.Queue[dict[str, Any]]] = {}
DEVICE_PENDING: dict[tuple[str, str], dict[str, Any]] = {}
DEVICE_STATES: dict[str, dict[str, Any]] = {}
DEVICE_LOGS: dict[str, deque[dict[str, Any]]] = {}
DATA_LOCK = threading.RLock()
REGISTER_ATTEMPTS: dict[str, deque[float]] = {}
REGISTER_LOCK = threading.Lock()
CURRENT_DEVICE: contextvars.ContextVar[str | None] = contextvars.ContextVar("sirius_device", default=None)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def issue_device_token(device_id: str) -> str:
    payload = json.dumps({"sub": device_id, "exp": int(time.time()) + TOKEN_TTL_SECONDS}, separators=(",", ":")).encode()
    encoded = _b64(payload)
    signature = _b64(hmac.new(SIGNING_SECRET, encoded.encode(), hashlib.sha256).digest())
    return "s1." + encoded + "." + signature


def verify_device_token(token: str) -> str | None:
    try:
        version, encoded, supplied = token.split(".", 2)
        if version != "s1":
            return None
        expected = _b64(hmac.new(SIGNING_SECRET, encoded.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(supplied, expected):
            return None
        payload = json.loads(_unb64(encoded))
        device_id = str(payload["sub"])
        if int(payload["exp"]) < int(time.time()) or len(device_id) != 32:
            return None
        return device_id
    except Exception:
        return None


def device_queue(device_id: str) -> queue.Queue[dict[str, Any]]:
    with DATA_LOCK:
        return DEVICE_QUEUES.setdefault(device_id, queue.Queue(maxsize=30))


def log_event(event: str, device_id: str | None = None, **details: Any) -> None:
    record = {"time": time.time(), "event": event, **details}
    print(json.dumps({"device_id": device_id, **record}, ensure_ascii=False, default=str), flush=True)
    if device_id:
        with DATA_LOCK:
            DEVICE_LOGS.setdefault(device_id, deque(maxlen=200)).append(record)


def current_device() -> str:
    device_id = CURRENT_DEVICE.get()
    if not device_id:
        raise RuntimeError("Missing device token. Register this Loader and configure the same token in your MCP client.")
    return device_id


def queue_command(kind: str, **payload: Any) -> dict[str, Any]:
    device_id = current_device()
    command_id = uuid.uuid4().hex
    event = threading.Event()
    record = {"id": command_id, "type": kind, **payload}
    with DATA_LOCK:
        pending_count = sum(1 for key in DEVICE_PENDING if key[0] == device_id)
        if pending_count >= 30:
            return {"ok": False, "error": "Too many pending commands for this device"}
        DEVICE_PENDING[(device_id, command_id)] = {"event": event, "result": None, "created": time.time()}
    try:
        device_queue(device_id).put_nowait(record)
    except queue.Full:
        with DATA_LOCK:
            DEVICE_PENDING.pop((device_id, command_id), None)
        return {"ok": False, "error": "This device command queue is full"}
    log_event("command_queued", device_id, command_id=command_id, command_type=kind)
    if not event.wait(timeout=COMMAND_TIMEOUT):
        with DATA_LOCK:
            DEVICE_PENDING.pop((device_id, command_id), None)
        log_event("command_timeout", device_id, command_id=command_id, command_type=kind)
        return {"queued": True, "id": command_id, "status": "timeout", "message": "Loader did not answer in time"}
    with DATA_LOCK:
        item = DEVICE_PENDING.pop((device_id, command_id), None)
    result = (item or {}).get("result") or {"id": command_id, "ok": False, "error": "No result returned"}
    log_event("command_result", device_id, command_id=command_id, command_type=kind, ok=result.get("ok", False))
    return result


class DeviceAuthMiddleware:
    def __init__(self, app: Any):
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path == "/health" or (path == "/register" and scope.get("method") == "POST"):
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        supplied = headers.get(b"x-sirius-token", b"").decode("utf-8", "ignore")
        if not supplied:
            auth = headers.get(b"authorization", b"").decode("utf-8", "ignore")
            if auth.lower().startswith("bearer "):
                supplied = auth[7:].strip()
        device_id = verify_device_token(supplied)
        if not device_id:
            response = JSONResponse({"error": "unauthorized", "message": "Register the Loader to obtain a device token"}, status_code=401)
            await response(scope, receive, send)
            return
        context_token = CURRENT_DEVICE.set(device_id)
        try:
            await self.app(scope, receive, send)
        finally:
            CURRENT_DEVICE.reset(context_token)


mcp = FastMCP("Sirius Loader MCP")


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> Response:
    return JSONResponse({"ok": True, "service": "Sirius MCP bridge", "auth": "per-device"})


@mcp.custom_route("/register", methods=["POST"])
async def register(request: Request) -> Response:
    forwarded_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    client_ip = forwarded_ip or (request.client.host if request.client else "unknown")
    now = time.time()
    with REGISTER_LOCK:
        attempts = REGISTER_ATTEMPTS.setdefault(client_ip, deque())
        while attempts and now - attempts[0] > 3600:
            attempts.popleft()
        if len(attempts) >= 5:
            return JSONResponse({"ok": False, "error": "Registration rate limit reached. Try again later."}, status_code=429)
        attempts.append(now)
    device_id = uuid.uuid4().hex
    token = issue_device_token(device_id)
    log_event("device_registered", device_id)
    return JSONResponse({"ok": True, "device_id": device_id, "token": token, "expires_in": TOKEN_TTL_SECONDS})


@mcp.custom_route("/poll", methods=["GET"])
async def poll(_: Request) -> Response:
    device_id = current_device()
    try:
        command = device_queue(device_id).get_nowait()
    except queue.Empty:
        command = None
    return JSONResponse({"command": command})


@mcp.custom_route("/result", methods=["POST"])
async def result(request: Request) -> Response:
    device_id = current_device()
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)
    command_id = str(body.get("id", ""))
    with DATA_LOCK:
        item = DEVICE_PENDING.get((device_id, command_id))
        if item:
            item["result"] = body
            item["event"].set()
    if not item:
        log_event("orphan_result", device_id, command_id=command_id)
    return JSONResponse({"ok": bool(item)})


@mcp.custom_route("/state", methods=["POST"])
async def update_state(request: Request) -> Response:
    device_id = current_device()
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "state must be an object"}, status_code=400)
    safe_state = {key: value for key, value in body.items() if key in {"player", "placeId", "jobId", "health", "position"}}
    with DATA_LOCK:
        previous_connected = DEVICE_STATES.get(device_id, {}).get("connected", False)
        DEVICE_STATES[device_id] = {**safe_state, "connected": True, "updated_at": time.time()}
    if not previous_connected:
        log_event("loader_connected", device_id, player=safe_state.get("player"), place_id=safe_state.get("placeId"))
    return JSONResponse({"ok": True})


@mcp.custom_route("/logs", methods=["POST"])
async def receive_logs(request: Request) -> Response:
    device_id = current_device()
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
            log_event("loader_log", device_id, message=str(entry)[:1000])
            accepted += 1
        elif isinstance(entry, dict):
            log_event("loader_log", device_id, **{str(k)[:40]: str(v)[:500] for k, v in list(entry.items())[:12]})
            accepted += 1
    return JSONResponse({"ok": True, "accepted": accepted})


@mcp.tool()
def sirius_connection_status() -> dict[str, Any]:
    """Return whether the Loader associated with this MCP device token sent a recent heartbeat."""
    device_id = current_device()
    with DATA_LOCK:
        state = dict(DEVICE_STATES.get(device_id, {}))
    updated = state.get("updated_at")
    connected = bool(updated and time.time() - float(updated) <= STATE_STALE_SECONDS)
    state["connected"] = connected
    return {"bridge": "online", **state}


@mcp.tool()
def sirius_get_status() -> dict[str, Any]:
    """Get the latest player, place, health and position for this device token."""
    device_id = current_device()
    with DATA_LOCK:
        state = dict(DEVICE_STATES.get(device_id, {}))
    updated = state.get("updated_at")
    if not updated or time.time() - float(updated) > STATE_STALE_SECONDS:
        return {"ok": False, "connected": False, "error": "This Loader is offline or its heartbeat is stale"}
    return {"ok": True, **state}


@mcp.tool()
def sirius_list_controls() -> dict[str, Any]:
    """List controls registered by the Loader associated with this MCP device token."""
    return queue_command("list_controls")


@mcp.tool()
def sirius_set_toggle(control_id: str, enabled: bool) -> dict[str, Any]:
    """Set a registered toggle on this device. Use an exact id returned by sirius_list_controls."""
    return queue_command("set_toggle", id=control_id, value=enabled)


@mcp.tool()
def sirius_run_action(action_id: str) -> dict[str, Any]:
    """Run a registered button action on this device. Use an exact id returned by sirius_list_controls."""
    return queue_command("run_action", id=action_id)


@mcp.tool()
def sirius_set_slider(control_id: str, value: float) -> dict[str, Any]:
    """Set a registered slider on this device. The Loader validates the control and its range."""
    return queue_command("set_slider", id=control_id, value=value)


@mcp.tool()
def sirius_create_lua_script(filename: str, code: str) -> dict[str, Any]:
    """Return Lua source as text for the user to save manually; does not save or execute it."""
    safe_name = filename.replace("\\", "/").split("/")[-1][:100]
    if not safe_name.lower().endswith(".lua"):
        safe_name += ".lua"
    if safe_name in {"", ".", ".."} or not code.strip() or len(code) > 100_000:
        return {"ok": False, "error": "Invalid filename or script is empty/too large"}
    log_event("lua_script_prepared", current_device(), filename=safe_name, bytes=len(code))
    return {"ok": True, "filename": safe_name, "code": code, "saved": False, "executed": False}


@mcp.tool()
def sirius_execute_lua(code: str, confirm_risk: bool = False) -> dict[str, Any]:
    """Execute Lua only after confirm_risk=true and a fresh on-device approval for this exact code."""
    if confirm_risk is not True:
        return {"ok": False, "error": "Blocked. Obtain explicit approval for this exact code, then call again with confirm_risk=true."}
    if not code.strip() or len(code) > 100_000:
        return {"ok": False, "error": "Code must be non-empty and at most 100 KB"}
    log_event("lua_execution_requested", current_device(), bytes=len(code), approval=True)
    return queue_command("execute_lua", code=code, confirm_risk=True)


@mcp.tool()
def sirius_capture_screenshot() -> dict[str, Any]:
    """Desktop screenshots are unavailable on Render; the cloud service cannot capture the local screen."""
    return {"ok": False, "error": "Screenshot capture is unavailable in cloud mode."}


@mcp.tool()
def sirius_read_recent_logs(max_lines: int = 100) -> dict[str, Any]:
    """Read recent events for the device associated with this MCP token."""
    device_id = current_device()
    limit = max(1, min(int(max_lines), 200))
    with DATA_LOCK:
        entries = list(DEVICE_LOGS.get(device_id, []))[-limit:]
    return {"ok": True, "lines": entries}


mcp_app = mcp.streamable_http_app()
host_checked_app = TrustedHostMiddleware(mcp_app, allowed_hosts=[HOSTNAME])
app = DeviceAuthMiddleware(host_checked_app)
