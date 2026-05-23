"""End-to-end tests against the live Telegram MTProto API via Telethon.

Requires:
  - A valid session (run `python cli.py login` first)
  - API_ID and API_HASH environment variables set

Run with: .venv/bin/pytest tests/ -v

Update KNOWN_ENTITY below with a username or chat ID you can test against.
"""
import pytest
from server import delete_message, edit_message, get_messages, search_dialogs, send_message

# Set to a username, phone number, or chat ID you control (e.g. "me" for Saved Messages)
KNOWN_ENTITY = "me"


@pytest.mark.asyncio
async def test_search_dialogs_returns_results():
    results = await search_dialogs(query="Telegram", limit=3)

    assert isinstance(results, list)
    assert len(results) <= 3
    for dialog in results:
        assert hasattr(dialog, "id")
        assert hasattr(dialog, "title")
        assert hasattr(dialog, "type")


@pytest.mark.asyncio
async def test_search_dialogs_empty_query_raises():
    with pytest.raises(ValueError, match="empty"):
        await search_dialogs(query="")


@pytest.mark.asyncio
async def test_get_messages_returns_messages():
    result = await get_messages(entity=KNOWN_ENTITY, limit=5)

    assert result.messages is not None
    assert isinstance(result.messages, list)
    assert len(result.messages) <= 5

    for msg in result.messages:
        assert msg.message_id is not None
        assert isinstance(msg.outgoing, bool)


@pytest.mark.asyncio
async def test_send_edit_delete_message():
    sent_result = await send_message(entity=KNOWN_ENTITY, message="MCP test — please ignore")
    assert "sent" in sent_result.lower()

    # Retrieve to get the message ID
    messages = await get_messages(entity=KNOWN_ENTITY, limit=1)
    assert messages.messages
    msg_id = messages.messages[0].message_id

    # Edit
    edit_result = await edit_message(entity=KNOWN_ENTITY, message_id=msg_id, message="MCP test (edited)")
    assert "edited" in edit_result.lower()

    # Delete
    delete_result = await delete_message(entity=KNOWN_ENTITY, message_ids=[msg_id])
    assert "deleted" in delete_result.lower()


@pytest.mark.asyncio
async def test_get_messages_unread_flag():
    result = await get_messages(entity=KNOWN_ENTITY, limit=5, unread=True)
    assert result.messages is not None
