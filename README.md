# telegram-mcp

A [FastMCP](https://github.com/jlowin/fastmcp) server that exposes Telegram as MCP tools via the **MTProto protocol**, giving AI agents full user-account access — not just the limited Bot API.

Built on [Telethon](https://docs.telethon.dev).

## Tools

| Tool | Description |
|------|-------------|
| `search_dialogs` | Search contacts and dialogs by name/username |
| `get_messages` | Read message history from any chat |
| `send_message` | Send text and files to any user, group, or channel |
| `edit_message` | Edit a sent message |
| `delete_message` | Delete one or more messages |
| `get_draft` | Read the current draft for a chat |
| `set_draft` | Save a draft to a chat |
| `media_download` | Download media attached to a message |
| `message_from_link` | Resolve a `t.me` link to a message |

## Setup

**1. Get API credentials**

Visit [my.telegram.org/apps](https://my.telegram.org/apps), create an application, and note your **API ID** and **API Hash**.

**2. Install dependencies**

```bash
uv sync
```

**3. Set credentials and authenticate**

```bash
export API_ID=your_api_id
export API_HASH=your_api_hash
uv run python cli.py login
```

This creates a session file at `$XDG_STATE_HOME/telegram-mcp/session.string`.

**4. Configure your MCP client**

Add to your `.mcp.json` (or equivalent):

```json
{
  "mcpServers": {
    "telegram-mcp": {
      "command": "uv",
      "args": ["--directory", "/path/to/telegram-mcp", "run", "python", "server.py"],
      "env": {
        "API_ID": "your_api_id",
        "API_HASH": "your_api_hash"
      }
    }
  }
}
```

## Running

```bash
uv run python cli.py start
# or directly:
uv run python server.py
```

## Multiple instances

The server uses `StringSession` to store auth data as a plain text file rather than SQLite, so multiple MCP client instances (e.g. multiple Claude windows) can connect concurrently without database lock errors.

## Tests

Requires a valid session and credentials in the environment:

```bash
API_ID=your_api_id API_HASH=your_api_hash uv run python -m pytest tests/ -v
```

## CLI reference

```
uv run python cli.py login          # authenticate and save session
uv run python cli.py start          # start the MCP server
uv run python cli.py logout         # instructions for revoking the session
uv run python cli.py clear-session  # delete the local session file
```
