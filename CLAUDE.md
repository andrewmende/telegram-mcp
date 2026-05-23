# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A [FastMCP](https://github.com/jlowin/fastmcp) server that wraps [Telethon](https://docs.telethon.dev) to expose Telegram as MCP tools via the **MTProto protocol** (full user-account access, not the Bot API).

## Setup

Install dependencies:
```bash
.venv/bin/pip install -r requirements.txt
```

Obtain API credentials at [https://my.telegram.org/apps](https://my.telegram.org/apps) and set them:
```bash
export API_ID=your_api_id
export API_HASH=your_api_hash
```

Authenticate (creates a local session file):
```bash
.venv/bin/python cli.py login
```

Run the MCP server:
```bash
.venv/bin/python cli.py start
# or directly:
.venv/bin/python server.py
```

Run the end-to-end test suite (requires a valid session):
```bash
.venv/bin/pytest tests/ -v
```

## Architecture

| File | Purpose |
|------|---------|
| `server.py` | FastMCP tool definitions — the MCP server |
| `telegram.py` | `Telegram` class wrapping `telethon.TelegramClient` |
| `models.py` | Pydantic models (`Dialog`, `Message`, `Media`, `Messages`, `DownloadedMedia`) |
| `utils.py` | Helpers: `parse_entity`, `get_unique_filename`, `parse_telegram_url` |
| `cli.py` | Typer CLI: `login`, `start`, `logout`, `clear-session` commands |

### Key patterns

1. **`Telegram` class** (`telegram.py`) — wraps Telethon; all async Telegram operations live here. `create_client()` reads `API_ID`/`API_HASH` from the environment via `pydantic-settings`.

2. **`app_lifespan`** (`server.py`) — FastMCP async context manager that connects the Telethon client on startup and disconnects on shutdown.

3. **`parse_entity`** (`utils.py`) — converts a string entity (username, phone number, numeric ID) to `int | str` for Telethon.

4. **Session file** — stored at `$XDG_STATE_HOME/telegram-mcp/session.session`. Run `python cli.py clear-session` to remove it.

## Backlog / Adding New Tools

When adding a new tool, follow these steps:

1. **Add the method to `Telegram`** (`telegram.py`) — keep all Telethon calls here.
2. **Add the `@mcp.tool()` function to `server.py`** — call the `Telegram` method via `tg`.
3. **Update `FastMCP(instructions=...)`** in `server.py` if the capability set changed.
4. **Add a test** in `tests/test_telegram.py`.
5. **Run tests** — confirm all pass.

```python
@mcp.tool()
async def my_new_tool(entity: str, ...) -> ReturnType:
    """Tool docstring shown to the model — describe what it returns."""
    _entity = parse_entity(entity)
    return await tg.my_new_method(_entity, ...)
```

## MCP Documentation — Keep It Current

The docstring and `Args:` section of every `@mcp.tool()` are the only documentation an AI agent sees. **Always update:**

1. The function docstring — describe return shape and caveats.
2. The `Args:` section — valid values and examples for every parameter.
3. `FastMCP(instructions=...)` — if the server's overall capabilities change.

## Key Dependency: Telethon

Telethon implements the Telegram MTProto protocol, giving full user-account access (unlike the Bot API). Useful references:

```python
# Discover available methods:
help(tg.client.send_message)

# Telethon docs:
# https://docs.telethon.dev/en/stable/
```

**MTProto limitations to be aware of:**
- Requires a human phone number and 2FA-capable account — not a bot token.
- `iter_messages` returns newest-first; use `offset_date` to paginate.
- Rate limits are enforced by Telegram; Telethon handles flood-wait errors automatically.
- The session file must be present for the server to start (`login` first).
