"""Telegram MTProto MCP Server."""

import logging
import os
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

from fastmcp import FastMCP
from fastmcp.server.auth import AccessToken, TokenVerifier

from models import Dialog, DownloadedMedia, Message, Messages
from telegram import Telegram
from utils import parse_entity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram-mcp")

tg = Telegram()


class StaticTokenVerifier(TokenVerifier):
    """Accepts a single static bearer token read from MCP_TOKEN env var."""

    def __init__(self, token: str) -> None:
        super().__init__()
        self._token = token

    async def verify_token(self, token: str) -> AccessToken | None:
        if not secrets.compare_digest(token, self._token):
            return None
        return AccessToken(token=token, client_id="mcp-client", scopes=[])


_mcp_token = os.getenv("MCP_TOKEN")
_auth = StaticTokenVerifier(_mcp_token) if _mcp_token else None
if _mcp_token:
    logger.info("MCP token auth enabled.")
else:
    logger.warning("MCP_TOKEN not set — server is unauthenticated.")


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[None]:
    tg.create_client()
    await tg.client.connect()
    tg.save_session_string()
    try:
        yield
    finally:
        tg.save_session_string()
        await tg.client.disconnect()  # type: ignore


mcp = FastMCP(
    name="telegram-mcp",
    lifespan=app_lifespan,
    auth=_auth,
    instructions=(
        "Telegram MTProto MCP Server. "
        "Communicates with Telegram as a full user account (not a bot) via the MTProto protocol using Telethon. "
        "Requires API credentials (API_ID, API_HASH env vars) and an authenticated session — run `python cli.py login` first. "
        "Typical read workflow: search_dialogs to find an entity → get_messages to read its history. "
        "!IMPORTANT: When an entity is ambiguous, always use search_dialogs first and confirm with the user before sending."
    ),
)


# ========================== MESSAGES ==========================


@mcp.tool()
async def send_message(
    entity: str,
    message: str = "",
    file_path: list[str] | None = None,
    reply_to: int | None = None,
) -> str:
    """Send a text message (and optional files) to a Telegram user, group, or channel.

    !IMPORTANT: If you are not sure about the entity, use search_dialogs first
    and ask the user to confirm before sending.

    Returns a confirmation string on success or raises on error.

    Args:
        entity: Chat ID, username, phone number ('+1234567890'), or 'me'.
        message: Text to send (supports Markdown: **bold**, __italic__, `mono`, [URL](links)).
        file_path: Optional list of absolute local file paths to attach.
        reply_to: Message ID to reply to.
    """
    _entity = parse_entity(entity)
    await tg.send_message(_entity, message, file_path=file_path, reply_to=reply_to)
    return f"Message sent to {entity}"


@mcp.tool()
async def edit_message(entity: str, message_id: int, message: str) -> str:
    """Edit a previously sent message.

    !IMPORTANT: Only messages sent by the logged-in account can be edited.
    Use search_dialogs if unsure about the entity; use get_messages if unsure about the message ID.

    Returns a confirmation string on success or raises on error.

    Args:
        entity: Chat ID, username, phone number, or 'me'.
        message_id: ID of the message to edit.
        message: New message text.
    """
    _entity = parse_entity(entity)
    await tg.edit_message(_entity, message_id, message)
    return f"Message {message_id} edited in {entity}"


@mcp.tool()
async def delete_message(entity: str, message_ids: list[int]) -> str:
    """Delete one or more messages from a chat.

    !IMPORTANT: Deletion rights depend on group admin settings. Use search_dialogs
    if unsure about the entity; use get_messages if unsure about message IDs.

    Returns a confirmation string on success or raises on error.

    Args:
        entity: Chat ID, username, phone number, or 'me'.
        message_ids: List of message IDs to delete.
    """
    _entity = parse_entity(entity)
    await tg.delete_message(_entity, message_ids)
    return f"Deleted {len(message_ids)} message(s) from {entity}"


@mcp.tool()
async def get_messages(
    entity: str,
    limit: int = 10,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    unread: bool = False,
    mark_as_read: bool = False,
) -> Messages:
    """Retrieve messages from a chat, DM, or channel.

    Returns a Messages object containing a list of Message objects (newest first)
    and the Dialog the messages belong to.

    !IMPORTANT: Use search_dialogs if you are unsure about the entity.

    Args:
        entity: Chat ID, username, phone number, or 'me'.
        limit: Maximum number of messages to return (default 10).
        start_date: Only include messages on or after this date (UTC).
        end_date: Only include messages before this date (UTC, defaults to now).
        unread: If True, return only unread messages (up to `limit`).
        mark_as_read: If True, mark retrieved messages as read.
    """
    _entity = parse_entity(entity)
    return await tg.get_messages(_entity, limit, start_date, end_date, unread, mark_as_read)


@mcp.tool()
async def message_from_link(link: str) -> Message:
    """Retrieve a single message from a t.me link.

    Handles public links (t.me/username/123) and private channel links (t.me/c/id/123).
    Returns a Message object or raises if the link is invalid or inaccessible.

    Args:
        link: A Telegram message URL, e.g. 'https://t.me/somegroup/42'.
    """
    return await tg.message_from_link(link)


# ========================== DRAFTS ==========================


@mcp.tool()
async def get_draft(entity: str) -> str:
    """Get the current draft message for a chat.

    Returns the draft text, or an empty string if no draft exists.

    Args:
        entity: Chat ID, username, phone number, or 'me'.
    """
    _entity = parse_entity(entity)
    return await tg.get_draft(_entity)


@mcp.tool()
async def set_draft(entity: str, message: str) -> str:
    """Save a draft message for a chat without sending it.

    Returns a confirmation string on success or raises on error.

    Args:
        entity: Chat ID, username, phone number, or 'me'.
        message: Draft text to save.
    """
    _entity = parse_entity(entity)
    await tg.set_draft(_entity, message)
    return f"Draft saved for {entity}"


# ========================== DIALOGS ==========================


@mcp.tool()
async def get_unread_dialogs() -> list[Dialog]:
    """Return dialogs that have unread messages, sorted newest-first by last message date.

    Scans the 200 most recent dialogs and returns all unread ones.
    Each Dialog has: id, title, username, phone_number,
    type (user/bot/group/channel), unread_messages_count, can_send_message.
    """
    return await tg.get_unread_dialogs()


@mcp.tool()
async def search_dialogs(
    query: str,
    limit: int = 10,
    global_search: bool = False,
) -> list[Dialog]:
    """Search for users, groups, and channels by name or username.

    Searches the logged-in account's contacts and dialogs. With global_search=True,
    also searches Telegram's public index.

    Returns a list of Dialog objects sorted by relevance, each with:
    id, title, username, phone_number, type (user/bot/group/channel),
    unread_messages_count, can_send_message.

    !IMPORTANT: Always use this tool to resolve an entity before messaging when
    the identity isn't certain — never guess chat IDs.

    Args:
        query: Name or username fragment to search for.
        limit: Maximum number of results to return (default 10, must be > 0).
        global_search: If True, extend search beyond personal contacts/dialogs.
    """
    return await tg.search_dialogs(query, limit, global_search)


# ========================== MEDIA ==========================


@mcp.tool()
async def media_download(
    entity: str,
    message_id: int,
    path: str | None = None,
) -> DownloadedMedia:
    """Download a media file attached to a message to local disk.

    Returns a DownloadedMedia object with the absolute local path and media metadata
    (mime_type, file_name, file_size).

    !IMPORTANT: Use search_dialogs if unsure about the entity; use get_messages
    to find the message ID containing the media.

    Args:
        entity: Chat ID, username, phone number, or 'me'.
        message_id: ID of the message containing the media.
        path: Optional directory path to save the file. Defaults to the XDG state dir.
    """
    _entity = parse_entity(entity)
    return await tg.download_media(_entity, message_id, path)


if __name__ == "__main__":
    mcp.run()
