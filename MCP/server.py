from __future__ import annotations

import base64
import json
import os
import queue
import secrets
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP, Image as MCPImage

ROOT = Path(__file__).resolve().parent
TOKEN_FILE = Path(os.environ.get("SIRIUS_TOKEN_FILE", str(ROOT / "Sirius_MCP_Token.txt")))
SCRIPT_DIR = ROOT / "scripts"
SCREENSHOT_DIR = ROOT / "screenshots"
SCRIPT_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR.mkdir(exist_ok=True)

if TOKEN_FILE.exists():
    TOKEN = TOKEN_FILE.read_text(encoding="utf-8").strip()
else:
    TOKEN = secrets.token_urlsafe(32)
    TOKEN_FILE.write_text(TOKEN + "\n", encoding="utf-8")
    try:
        TOKEN_FILE.chmod(0o600)
    except OSError:
        pass

HOST = "127.0.0.1"
PORT = int(os.environ.get("SIRIUS_MCP_PORT", "8765"))
COMMANDS: queue.Queue[dict[str, Any]] = queue.Queue()
PENDING: dict[str, dict[str, Any]] = {}
PENDING_LOCK = threading.Lock()
STATE: dict[str, Any] = {"connected": False, "updated_at": None}
STATE_LOCK = threading.Lock()

mcp = FastMCP("Sirius Loader MCP")

def queue_command(kind: str, **payload: Any) -> dict[str, Any]:
    command_id = uuid.uuid4().hex
    event = threading.Event()
    record = {"id": command_id, "type": kind, **payload}
    with PENDING_LOCK:
        PENDING[command_id] = {"event": event, "result": None, "created": time.time()}
    COMMANDS.put(record)
    if not event.wait(timeout=18):
        with PENDING_LOCK:
            PENDING.pop(command_id, None)
        return {"queued": True, "id": command_id, "status": "timeout", "message": "Loader did not answer within 18 seconds. Check that the game is running and the bridge is connected."}
    with PENDING_LOCK:
        item = PENDING.pop(command_id, None)
    return (item or {}).get("result") or {"id": command_id, "ok": False, "error": "No result returned"}

class BridgeHandler(BaseHTTPRequestHandler):
    server_version = "SiriusBridge/1.0"

    def log_message(self, *_: Any) -> None:
        return

    def _json(self, status: int, payload: Any) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self) -> bool:
        return secrets.compare_digest(self.headers.get("X-Sirius-Token", ""), TOKEN)

    def do_GET(self) -> None:
        if not self._authorized():
            self._json(401, {"error": "unauthorized"})
            return
        path = urlparse(self.path).path
        if path == "/poll":
            try:
                command = COMMANDS.get_nowait()
            except queue.Empty:
                command = None
            self._json(200, {"command": command})
        elif path == "/health":
            self._json(200, {"ok": True, "service": "Sirius MCP bridge"})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if not self._authorized():
            self._json(401, {"error": "unauthorized"})
            return
        try:
            length = min(int(self.headers.get("Content-Length", "0")), 2_000_000)
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except Exception:
            self._json(400, {"error": "invalid json"})
            return
        path = urlparse(self.path).path
        if path == "/result":
            command_id = str(body.get("id", ""))
            with PENDING_LOCK:
                item = PENDING.get(command_id)
                if item:
                    item["result"] = body
                    item["event"].set()
            self._json(200, {"ok": bool(item)})
        elif path == "/state":
            with STATE_LOCK:
                STATE.clear()
                STATE.update(body if isinstance(body, dict) else {})
                STATE["connected"] = True
                STATE["updated_at"] = time.time()
            self._json(200, {"ok": True})
        else:
            self._json(404, {"error": "not found"})

def start_bridge() -> None:
    httpd = ThreadingHTTPServer((HOST, PORT), BridgeHandler)
    httpd.daemon_threads = True
    thread = threading.Thread(target=httpd.serve_forever, name="SiriusHTTPBridge", daemon=True)
    thread.start()

start_bridge()

@mcp.tool()
def sirius_connection_status() -> dict[str, Any]:
    """Return whether the running Sirius Loader is connected to this local MCP bridge."""
    with STATE_LOCK:
        state = dict(STATE)
    if state.get("updated_at") and time.time() - float(state["updated_at"]) > 5:
        state["connected"] = False
    return {"bridge": "online", "host": HOST, "port": PORT, **state}

@mcp.tool()
def sirius_get_status() -> dict[str, Any]:
    """Get the latest player, place, health and position status reported by Sirius Loader."""
    return queue_command("status")

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
    """Set a registered Sirius slider to a numeric value. Use its exact id and min/max from sirius_list_controls."""
    return queue_command("set_slider", id=control_id, value=value)

@mcp.tool()
def sirius_create_lua_script(filename: str, code: str) -> dict[str, Any]:
    """Create a Lua script file in the local MCP scripts folder. This only writes a file; it does not execute it."""
    safe_name = Path(filename).name
    if not safe_name.lower().endswith(".lua"):
        safe_name += ".lua"
    if safe_name in {"", ".", ".."} or len(code) > 500_000:
        return {"ok": False, "error": "Invalid filename or script exceeds 500 KB"}
    target = (SCRIPT_DIR / safe_name).resolve()
    if target.parent != SCRIPT_DIR.resolve():
        return {"ok": False, "error": "Invalid path"}
    target.write_text(code, encoding="utf-8")
    return {"ok": True, "path": str(target), "bytes": target.stat().st_size, "executed": False}

@mcp.tool()
def sirius_execute_lua(code: str, confirm_risk: bool = False) -> dict[str, Any]:
    """Execute Lua inside the active Sirius Loader executor. Arbitrary Lua can affect the game session and may access executor APIs. Set confirm_risk=true only after the user has explicitly approved this exact execution."""
    if confirm_risk is not True:
        return {"ok": False, "error": "Execution blocked. Obtain explicit user approval, then call again with confirm_risk=true."}
    if not code.strip() or len(code) > 100_000:
        return {"ok": False, "error": "Code must be non-empty and at most 100 KB"}
    return queue_command("execute_lua", code=code, confirm_risk=True)

@mcp.tool()
def sirius_capture_screenshot() -> dict[str, Any]:
    """Capture the current desktop screenshot and return its local file path."""
    try:
        import mss
        from PIL import Image
        with mss.mss() as capture:
            shot = capture.grab(capture.monitors[1])
            image = Image.frombytes("RGB", shot.size, shot.rgb)
            stamp = time.strftime("%Y%m%d_%H%M%S")
            target = SCREENSHOT_DIR / f"sirius_{stamp}.png"
            image.save(target, format="PNG")
        return [
            {"type": "text", "text": json.dumps({"ok": True, "path": str(target), "width": image.width, "height": image.height}, ensure_ascii=False)},
            MCPImage(data=target.read_bytes(), format="png"),
        ]
    except Exception as exc:
        return {"ok": False, "error": f"Screenshot failed: {exc}. Install the optional mss and Pillow packages."}

@mcp.tool()
def sirius_read_recent_logs(max_lines: int = 100) -> dict[str, Any]:
    """Read recent lines from the local Sirius MCP log file if present."""
    path = ROOT / "sirius.log"
    if not path.exists():
        return {"ok": True, "lines": []}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return {"ok": True, "lines": lines[-max(1, min(max_lines, 500)):]}

if __name__ == "__main__":
    print(f"Sirius MCP HTTP bridge: http://{HOST}:{PORT}", file=sys.stderr)
    print(f"Token file: {TOKEN_FILE}", file=sys.stderr)
    mcp.run(transport="stdio")
