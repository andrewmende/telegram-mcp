"""Pytest fixtures for telegram-mcp tests."""

import shutil

import pytest
from xdg_base_dirs import xdg_state_home

from telegram import Telegram


@pytest.fixture(scope="session", autouse=True)
async def telegram_client():
    state_dir = xdg_state_home() / "telegram-mcp"
    main_session = state_dir / "session.session"
    test_session = state_dir / "test_session.session"

    if main_session.exists() and not test_session.exists():
        shutil.copy2(main_session, test_session)

    tg = Telegram(session_name="test_session")
    tg.create_client()
    await tg.client.connect()

    # Patch the module-level tg in server so tool functions use this client
    import server
    server.tg = tg

    yield

    await tg.client.disconnect()
