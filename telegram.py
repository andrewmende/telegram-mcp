"""Telethon client wrapper for the Telegram MCP server."""

import itertools
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from telethon import TelegramClient, hints, types  # type: ignore
from telethon.sessions import StringSession  # type: ignore
from telethon.tl import custom, functions, patched  # type: ignore
from xdg_base_dirs import xdg_state_home

from models import Dialog, DownloadedMedia, Media, Message, Messages
from utils import get_unique_filename, parse_telegram_url

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    api_id: str
    api_hash: SecretStr


class Telegram:
    """Wrapper around telethon.TelegramClient."""

    def __init__(self, session_name: str = "session"):
        self._state_dir = xdg_state_home() / "telegram-mcp"
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._session_file = self._state_dir / session_name  # legacy SQLite path
        self._session_string_file = self._state_dir / f"{session_name}.string"
        self._downloads_dir = self._state_dir / "downloads"
        self._downloads_dir.mkdir(parents=True, exist_ok=True)
        self._client: TelegramClient | None = None

    @property
    def client(self) -> TelegramClient:
        if self._client is None:
            raise RuntimeError("Client not initialised — call create_client() first.")
        return self._client

    @property
    def session_file(self) -> Path:
        return self._session_file

    async def ensure_connected(self) -> None:
        if not self.client.is_connected():
            await self.client.connect()

    def create_client(self, api_id: str | None = None, api_hash: str | None = None) -> TelegramClient:
        if self._client is not None:
            return self._client

        if api_id is None or api_hash is None:
            settings = Settings()  # type: ignore
        else:
            settings = Settings(api_id=api_id, api_hash=SecretStr(api_hash))

        if self._session_string_file.exists():
            session: StringSession | str = StringSession(self._session_string_file.read_text().strip())
        else:
            session = str(self._session_file)  # SQLite fallback for initial login

        self._client = TelegramClient(
            session=session,
            api_id=int(settings.api_id),
            api_hash=settings.api_hash.get_secret_value(),
        )
        return self._client

    def save_session_string(self) -> None:
        """Export current auth key to a plain-text string file for lock-free sharing."""
        ss = StringSession()
        ss.set_dc(self.client.session.dc_id, self.client.session.server_address, self.client.session.port)
        ss.auth_key = self.client.session.auth_key
        self._session_string_file.write_text(ss.save())

    # ------------------------------------------------------------------ #
    # Messages                                                             #
    # ------------------------------------------------------------------ #

    async def send_message(
        self,
        entity: str | int,
        message: str = "",
        file_path: list[str] | None = None,
        reply_to: int | None = None,
    ) -> None:
        await self.ensure_connected()
        if file_path:
            for path in file_path:
                p = Path(path)
                if not p.exists() or not p.is_file():
                    raise FileNotFoundError(f"File not found: {path}")

        await self.client.send_message(
            entity,
            message,
            file=file_path,  # type: ignore
            reply_to=reply_to,  # type: ignore
        )

    async def edit_message(self, entity: str | int, message_id: int, message: str) -> None:
        await self.ensure_connected()
        await self.client.edit_message(entity, message_id, message)

    async def delete_message(self, entity: str | int, message_ids: list[int]) -> None:
        await self.ensure_connected()
        await self.client.delete_messages(entity, message_ids)

    async def get_messages(
        self,
        entity: str | int,
        limit: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        unread: bool = False,
        mark_as_read: bool = False,
    ) -> Messages:
        if end_date is None:
            end_date = datetime.now(timezone.utc)
        if start_date is None:
            start_date = end_date - timedelta(days=10000)
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        await self.ensure_connected()
        _entity = await self.client.get_entity(entity)
        assert isinstance(_entity, hints.Entity)
        dialog = Dialog.from_entity(_entity)

        if unread:
            if not dialog or dialog.unread_messages_count == 0:
                return Messages(messages=[], dialog=dialog)
            limit = min(limit, dialog.unread_messages_count)

        results: list[Message] = []
        async for msg in self.client.iter_messages(_entity, offset_date=end_date):  # type: ignore
            if not isinstance(msg, patched.Message) or isinstance(
                msg, patched.MessageService | patched.MessageEmpty
            ):
                continue
            if msg.date is None or msg.date < start_date or len(results) >= limit:
                break
            if mark_as_read:
                try:
                    await msg.mark_read()
                except Exception as exc:
                    logger.warning(f"Failed to mark message {msg.id} as read: {exc}")
            results.append(Message.from_message(msg))

        return Messages(messages=results, dialog=dialog)

    # ------------------------------------------------------------------ #
    # Drafts                                                               #
    # ------------------------------------------------------------------ #

    async def get_draft(self, entity: str | int) -> str:
        await self.ensure_connected()
        draft = await self.client.get_drafts(entity)
        assert isinstance(draft, custom.Draft)
        return draft.text if isinstance(draft.text, str) else ""  # type: ignore

    async def set_draft(self, entity: str | int, message: str) -> None:
        await self.ensure_connected()
        peer_id = await self.client.get_peer_id(entity)
        draft = await self.client.get_drafts(peer_id)
        assert isinstance(draft, custom.Draft)
        await draft.set_message(message)  # type: ignore

    # ------------------------------------------------------------------ #
    # Media                                                                #
    # ------------------------------------------------------------------ #

    async def download_media(self, entity: str | int, message_id: int, path: str | None = None) -> DownloadedMedia:
        await self.ensure_connected()
        message = await self.client.get_messages(entity, ids=message_id)  # type: ignore
        if not message or not isinstance(message, patched.Message):
            raise ValueError(f"Message {message_id} not found in {entity}.")

        media = Media.from_message(message)
        if not media:
            raise ValueError(f"Message {message_id} in {entity} has no downloadable media.")

        filename = get_unique_filename(message)
        filepath = (Path(path) if path else self._downloads_dir) / filename

        downloaded = await message.download_media(file=filepath)  # type: ignore
        if not downloaded or not isinstance(downloaded, str):
            raise ValueError(f"Failed to download media for message {message_id}.")

        return DownloadedMedia(path=str(Path(downloaded).resolve()), media=media)

    # ------------------------------------------------------------------ #
    # Dialogs / Search                                                     #
    # ------------------------------------------------------------------ #

    async def search_dialogs(self, query: str, limit: int, global_search: bool = False) -> list[Dialog]:
        await self.ensure_connected()
        if not query:
            raise ValueError("Query cannot be empty.")
        if limit <= 0:
            raise ValueError("Limit must be greater than 0.")

        response: Any = await self.client(functions.contacts.SearchRequest(q=query, limit=limit))
        assert isinstance(response, types.contacts.Found)

        priority: dict[int, int] = {}
        for i, peer in enumerate(
            itertools.chain(response.my_results, response.results) if global_search else response.my_results
        ):
            peer_id = await self.client.get_peer_id(peer)
            priority[peer_id] = i

        result: list[Dialog] = []
        for x in itertools.chain(response.users, response.chats):
            if isinstance(x, hints.Entity):
                peer_id = await self.client.get_peer_id(x)
                if peer_id in priority:
                    can_send = await self._can_send_message(x)
                    try:
                        result.append(Dialog.from_entity(x, can_send))
                    except Exception as exc:
                        logger.warning(f"Failed to build dialog for {x.id}: {exc}")

        result.sort(key=lambda d: priority.get(d.id, 9999))
        return result[:limit]

    async def _can_send_message(self, entity: hints.Entity) -> bool:
        if isinstance(entity, types.User):
            return True
        try:
            permissions = await self.client.get_permissions(entity, "me")
            assert isinstance(permissions, custom.ParticipantPermissions)
            if permissions.is_creator or (permissions.is_admin and permissions.post_messages):
                return True
            if isinstance(entity, types.Channel) and entity.broadcast:
                return False
            if permissions.is_banned:
                assert isinstance(permissions.participant, types.ChannelParticipantBanned)  # type: ignore
                return not permissions.participant.banned_rights.send_messages
            banned_rights = await self.client.get_permissions(entity)
            assert isinstance(banned_rights, types.ChatBannedRights)
            return not banned_rights.send_messages
        except Exception as exc:
            logger.warning(f"Failed to get permissions for {entity}: {exc}")
            return False

    async def get_unread_dialogs(self) -> list[Dialog]:
        await self.ensure_connected()
        results: list[Dialog] = []
        async for dialog in self.client.iter_dialogs(limit=200):
            if dialog.unread_count == 0:
                continue
            can_send = await self._can_send_message(dialog.entity)
            try:
                results.append(Dialog.from_dialog(dialog, can_send))
            except Exception as exc:
                logger.warning(f"Failed to build dialog for {dialog.entity}: {exc}")
        return results

    # ------------------------------------------------------------------ #
    # Links                                                                #
    # ------------------------------------------------------------------ #

    async def message_from_link(self, link: str) -> Message:
        await self.ensure_connected()
        parsed = parse_telegram_url(link)
        if parsed is None:
            raise ValueError(f"Could not parse a valid Telegram message link: {link}")
        entity, message_id = parsed
        message = await self.client.get_messages(entity, ids=message_id)  # type: ignore
        if not message or not isinstance(message, patched.Message):
            raise ValueError(f"Could not retrieve message {message_id} from {entity}.")
        return Message.from_message(message)
