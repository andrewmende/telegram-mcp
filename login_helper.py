"""Non-interactive, two-step Telegram login for headless environments.

Step 1:  python login_helper.py request <phone>
         -> sends the login code to the phone, persists phone_code_hash.
Step 2:  python login_helper.py signin <code> [2fa_password]
         -> completes sign-in and writes the session string.

Reuses the project's Telegram wrapper so API_ID/API_HASH come from the env
and the session lands at $XDG_STATE_HOME/telegram-mcp/. The intermediate
SQLite session file persists the auth key between the two invocations.
"""

import asyncio
import json
import sys
from pathlib import Path

from telethon.errors import SessionPasswordNeededError  # type: ignore

from telegram import Telegram

tg = Telegram()
_PENDING = tg._state_dir / ".login_pending.json"  # phone + phone_code_hash


async def request(phone: str) -> None:
    tg.create_client()
    await tg.client.connect()
    sent = await tg.client.send_code_request(phone)
    _PENDING.write_text(json.dumps({"phone": phone, "hash": sent.phone_code_hash}))
    print(f"OK: code sent to {phone}. Now run: signin <code> [2fa_password]")
    await tg.client.disconnect()


async def signin(code: str, password: str | None) -> None:
    if not _PENDING.exists():
        sys.exit("No pending login — run `request <phone>` first.")
    data = json.loads(_PENDING.read_text())
    tg.create_client()
    await tg.client.connect()
    try:
        await tg.client.sign_in(phone=data["phone"], code=code, phone_code_hash=data["hash"])
    except SessionPasswordNeededError:
        if not password:
            await tg.client.disconnect()
            sys.exit("2FA enabled — re-run: signin <code> <2fa_password>")
        await tg.client.sign_in(password=password)
    me = await tg.client.get_me()
    tg.save_session_string()
    _PENDING.unlink(missing_ok=True)
    print(f"OK: logged in as {me.first_name} (id={me.id}). Session saved.")
    await tg.client.disconnect()


def main() -> None:
    if len(sys.argv) < 3 or sys.argv[1] not in {"request", "signin"}:
        sys.exit("usage: login_helper.py request <phone> | signin <code> [2fa_password]")
    cmd = sys.argv[1]
    if cmd == "request":
        asyncio.run(request(sys.argv[2]))
    else:
        asyncio.run(signin(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None))


if __name__ == "__main__":
    main()
