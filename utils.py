"""Utility functions for the Telegram MCP server."""

import re
import uuid
from pathlib import Path

from telethon.tl import patched  # type: ignore


def parse_entity(entity: str) -> int | str:
    """Return entity as int if it looks like an integer ID, otherwise return as-is (username/phone/'me')."""
    return int(entity) if entity.lstrip("-").isdigit() else entity


def get_unique_filename(message: patched.Message) -> str:
    """Generate a collision-free filename for a downloaded media attachment."""
    unique_prefix = str(uuid.uuid4())
    original_filename = None
    original_suffix = ""

    if message.file and isinstance(message.file.name, str):
        original_filename = Path(message.file.name).stem
        original_suffix = Path(message.file.name).suffix

    if original_filename:
        return f"{original_filename}_{unique_prefix}{original_suffix}"

    fallback = f"download_{message.id}_{unique_prefix}"
    if message.file and isinstance(message.file.mime_type, str):
        parts = message.file.mime_type.split("/")
        if len(parts) == 2 and parts[1]:
            return f"{fallback}.{parts[1]}"
    return fallback


def parse_telegram_url(url: str) -> tuple[str | int, int] | None:
    """Parse a t.me/telegram.me message link into (entity, message_id).

    Handles:
    - https://t.me/username/123
    - https://t.me/c/1234567890/123  (private channel)
    - telegram.me/username/123

    Returns None if the URL format is not recognised.
    """
    pattern = (
        r"^(?:https?://)?t(?:elegram)?\.me/"
        r"(?:(?P<username>[A-Za-z0-9_]+)/(?P<message_id>\d+)"
        r"|c/(?P<chat_id>\d+)/(?P<chat_message_id>\d+))/?$"
    )
    match = re.match(pattern, url)
    if not match:
        return None

    captured = match.groupdict()
    entity = captured.get("username") or captured.get("chat_id")
    message_id = captured.get("message_id") or captured.get("chat_message_id")
    if entity and message_id:
        return parse_entity(entity), int(message_id)
    return None
