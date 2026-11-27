# Sirius Loader MCP — Public multi-user edition

Sirius MCP connects a supported MCP client to your own running Sirius Loader instance. Each Loader instance registers separately and receives its own signed device token. Device commands, status, and logs are isolated by that token.

## Quick start

1. Launch **Sirius Loader** in your Roblox executor and wait for device registration to complete.
2. Make sure the executor supports an HTTP request API and the file APIs used by the Loader. The Loader stores its personal token in `Sirius_MCP_Token.txt` in the executor folder.
3. In Loader, open **Utility → Sirius MCP · Облако** and start MCP. Review the risk notice and accept it only if you understand the remote-control capabilities.
4. Download the installer in your preferred language from the links below.
5. Run the installer, select the MCP clients you want to configure, and click **Install selected / Установить выбранное**.
6. Fully restart the configured MCP client(s).
7. In the MCP client, connect to the `sirius-loader` server and use the tools. Start with `sirius_connection_status`, then `sirius_list_controls`.

> Only download installers from the official links in this repository. Do not run a copy sent by an unknown person.

## Windows installers

Both installers configure the same MCP clients and use the same connection settings. The difference is the language of the installer interface.

| Language | Download |
|---|---|
| Русский | [SiriusMCPInstallerRUS.exe](https://github.com/sirius551/asdfjkafdkgjaj/releases/latest/download/SiriusMCPInstallerRUS.exe) |
| English | [SiriusMCPInstallerENG.exe](https://github.com/sirius551/asdfjkafdkgjaj/releases/latest/download/SiriusMCPInstallerENG.exe) |

The links above require the matching files to be uploaded as assets to the latest GitHub Release. If a download returns 404, the release asset has not been published yet.

### What the installer does

- Searches a bounded set of common folders in the current Windows profile for `Sirius_MCP_Token.txt`. It does not search the entire disk or other Windows user profiles.
- Accepts the token only if it matches the expected `s1.` token format.
- Lets you browse for the token file manually if automatic discovery does not find it.
- Detects common client configuration locations and lets you select which clients to configure.
- Creates a timestamped backup before replacing an existing configuration file.
- Preserves other server entries in JSON configuration files and replaces only the Sirius section in Codex TOML configuration.
- Writes a log file named `SiriusMCPInstaller.log` beside the installer.

The installer does not start Sirius Loader, register a device, or install the server on your computer. The Loader performs device registration; the installer configures MCP clients to use the existing cloud endpoint and the token belonging to that Loader.

### Supported client configuration targets

The installer currently includes configuration entries for:

- Visual Studio Code
- Cursor
- Claude Code
- Gemini CLI
- Windsurf (legacy Cascade configuration path)
- Devin Desktop
- Cline (VS Code extension)
- Roo Code
- OpenAI Codex

Client configuration paths and supported fields can vary between application versions. Check the client documentation if its configuration format has changed.

**Claude Desktop is not configured automatically by this installer.** Use **Settings → Connectors → Add custom connector** in Claude Desktop and enter the MCP URL and authentication header manually.

### Token and configuration security

The installer reads the personal device token and writes it into the selected MCP client's configuration. The token is a credential for your Loader instance.

- Do not share `Sirius_MCP_Token.txt`, paste the token into chats, or commit it to Git.
- Protect access to your Windows account and the MCP client configuration files.
- Only select client configurations on a Windows account you control.
- Backups may also contain the token after a configuration has been installed. Protect or delete old backups securely when they are no longer needed.
- The installer masks the token in its input field, but its log can include local file paths. Review the log before sharing it.

## How the multi-user bridge works

1. On first run, Loader sends a request to `POST /register`.
2. The service creates a unique device ID and returns a signed token.
3. Loader saves the token locally as `Sirius_MCP_Token.txt`.
4. Loader sends its heartbeat, state, logs, and command responses using that token.
5. MCP requests use the same token in the `X-Sirius-Token` HTTP header.
6. The server scopes queues and device data to the authenticated device.

The shared signing secret `SIRIUS_MCP_TOKEN` is a server-side environment variable. It is not the personal device token and must never be placed in Loader code, installers, or public files.

## MCP connection details

- **Transport:** Streamable HTTP
- **MCP endpoint:** `https://sirius-mcp.onrender.com/mcp`
- **Authentication header:** `X-Sirius-Token`
- **Header value:** the contents of your local `Sirius_MCP_Token.txt`

Each user must configure the token belonging to their own running Loader instance. Do not use another user's token.

### Manual connection

If you prefer not to use the installer, configure your MCP client manually with:

- URL: `https://sirius-mcp.onrender.com/mcp`
- Transport: Streamable HTTP
- Header name: `X-Sirius-Token`
- Header value: your personal device token

Use the client's own configuration format and secret-storage mechanism. Avoid placing the token in a project file that is committed to Git.

### Visual Studio Code example

For VS Code, create or edit `.vscode/mcp.json` in your project:

```json
{
  "inputs": [
    {
      "type": "promptString",
      "id": "sirius-device-token",
      "description": "Sirius Loader device token",
      "password": true
    }
  ],
  "servers": {
    "sirius-loader": {
      "type": "http",
      "url": "https://sirius-mcp.onrender.com/mcp",
      "headers": {
        "X-Sirius-Token": "${input:sirius-device-token}"
      }
    }
  }
}
```

Start the server in VS Code and enter the token from your own Loader's `Sirius_MCP_Token.txt` when prompted. Keep the token out of source control.

## Loader controls and risk confirmation

The Loader exposes MCP controls in **Utility → Sirius MCP · Облако**. Starting MCP displays a risk notice explaining that MCP can interact with Loader controls and request Lua execution.

The general risk acknowledgement is separate from approval for an individual Lua execution. The `sirius_execute_lua` tool requires `confirm_risk=true` and a fresh approval on the device for the exact code. Read the full code in the local confirmation prompt before approving it. Declining the prompt prevents that execution.

The Loader may offer a setting to reset the stored MCP risk acknowledgement and a separate option to remove Sirius data. The exact cleanup capabilities depend on the executor's file APIs.

## MCP tools

| Tool | Purpose |
|---|---|
| `sirius_connection_status` | Check whether the Loader associated with this token has sent a recent heartbeat. |
| `sirius_get_status` | Read the latest available player, place, health, and position data. |
| `sirius_list_controls` | List controls registered by this Loader and their IDs. |
| `sirius_set_toggle(control_id, enabled)` | Set a registered toggle. Use an exact control ID. |
| `sirius_set_slider(control_id, value)` | Set a registered slider. The Loader validates the control and range. |
| `sirius_run_action(action_id)` | Run a registered button action. Use an exact action ID. |
| `sirius_create_lua_script(filename, code)` | Return Lua source as text. It does not save or execute the script. |
| `sirius_execute_lua(code, confirm_risk)` | Request Lua execution after explicit risk confirmation and local device approval. |
| `sirius_capture_screenshot()` | Not available in cloud mode. |
| `sirius_read_recent_logs(max_lines)` | Read recent events for this device token. |

Recommended first checks: call `sirius_connection_status`, then `sirius_list_controls`. Use the exact IDs returned by the control list.

## HTTP endpoints

- `GET /health` — public service health check.
- `POST /register` — registers a device and issues a personal token; limited to five attempts per IP per hour.
- `GET /poll` — retrieves a command for the authenticated device.
- `POST /result` — returns a command result for the authenticated device.
- `POST /state` — updates state for the authenticated device.
- `POST /logs` — submits logs for the authenticated device.
- `/mcp` — Streamable HTTP MCP endpoint; requires a valid personal device token.

Device tokens are signed and currently expire after 365 days. Changing the server signing secret invalidates previously issued tokens.

## Server deployment (maintainers)

The following settings describe the current Render deployment configuration:

- Service type: Web Service
- Repository: `sirius551/asdfjkafdkgjaj`
- Branch for this edition: `public-multitenant`
- Runtime: Python 3
- Root directory: `MCP`
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn server:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health`

Required environment variable:

- `SIRIUS_MCP_TOKEN`: a randomly generated server-side signing secret with at least 32 characters. Keep it private. This is not a user's device token.

Render provides `PORT` and `RENDER_EXTERNAL_HOSTNAME`. The service also accepts `SIRIUS_ALLOWED_HOST` as an alternative host setting.

## Limitations and troubleshooting

- **401 Unauthorized:** confirm that the MCP client uses the token from the same Loader instance that is currently running.
- **Token file not found:** start Loader, wait for successful registration, and verify that the executor supports the required file APIs. You can also select the token file manually in the installer.
- **Registration rate limit (429):** the service allows up to five registration attempts per IP in one hour. Wait before trying again.
- **Loader appears offline:** make sure MCP is running in Loader and that the executor's HTTP request API is available.
- **Changes are not visible in the client:** fully restart the configured MCP client after installation.
- **Cloud service restarted:** in-memory queues, pending commands, recent state, and logs are cleared when the process restarts. Devices must reconnect and resume sending state.
- **Screenshot unavailable:** local desktop capture is not supported by the cloud-hosted service.
- **Render sleeps:** an idle free service may sleep; a health endpoint or external ping does not guarantee uninterrupted availability.

The bridge is a remote-control interface to your own Loader. Review actions and Lua code before approving them, and keep both server credentials and personal device tokens private.
