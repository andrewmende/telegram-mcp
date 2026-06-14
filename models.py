"""Pydantic types for the Telegram MCP server."""

import typing
from datetime import datetime
from enum import Enum

from pydantic import BaseModel
from telethon import hints, types, utils  # type: ignore
from telethon.tl import custom, patched  # type: ignore


class DialogType(Enum):
    USER = "user"
    GROUP = "group"
    CHANNEL = "channel"
    BOT = "bot"


class Dialog(BaseModel):
    id: int
    title: str
    username: str | None = None
    phone_number: str | None = None
    type: DialogType
    unread_messages_count: int
    can_send_message: bool

    @staticmethod
    def get_dialog_type(entity: hints.Entity) -> "DialogType":
        if isinstance(entity, types.User):
            return DialogType.BOT if entity.bot else DialogType.USER
        elif isinstance(entity, types.Chat):
            return DialogType.GROUP
        else:
            return DialogType.GROUP if entity.megagroup else DialogType.CHANNEL

    @staticmethod
    def from_entity(entity: hints.Entity, can_send_message: bool = False) -> "Dialog":
        return Dialog(
            id=utils.get_peer_id(entity),  # type: ignore
            title=utils.get_display_name(entity),  # type: ignore
            type=Dialog.get_dialog_type(entity),
            username=entity.username if not isinstance(entity, types.Chat) else None,
            phone_number=entity.phone if isinstance(entity, types.User) else None,
            unread_messages_count=0,
            can_send_message=can_send_message,
        )

    @staticmethod
    def from_dialog(dialog: custom.Dialog, can_send_message: bool = False) -> "Dialog":
        entity = dialog.entity
        return Dialog(
            id=utils.get_peer_id(entity),  # type: ignore
            title=utils.get_display_name(entity),  # type: ignore
            type=Dialog.get_dialog_type(entity),
            username=entity.username if not isinstance(entity, types.Chat) else None,
            phone_number=entity.phone if isinstance(entity, types.User) else None,
            unread_messages_count=dialog.unread_count,
            can_send_message=can_send_message,
        )


class Media(BaseModel):
    media_id: int
    mime_type: str | None = None
    file_name: str | None = None
    file_size: int | None = None

    @staticmethod
    def from_message(message: custom.Message) -> typing.Union["Media", None]:
        if message.media and message.file:
            if message.photo:
                media_id = message.photo.id
            elif message.document:
                media_id = message.document.id
            else:
                media_id = message.id

            file_name = message.file.name if isinstance(message.file.name, str) else None
            return Media(
                media_id=media_id,
                mime_type=message.file.mime_type,
                file_name=file_name,
                file_size=message.file.size,
            )
        return None


class DownloadedMedia(BaseModel):
    path: str
    media: Media


class Message(BaseModel):
    message_id: int
    sender_id: int | None = None
    message: str | None = None
    outgoing: bool
    date: datetime | None = None
    media: Media | None = None
    reply_to: int | None = None

    @staticmethod
    def from_message(message: patched.Message) -> "Message":
        sender_id: int | None = None
        if message.from_id:
            sender_id = int(utils.get_peer_id(message.from_id))  # type: ignore

        reply_to: int | None = None
        if message.reply_to and isinstance(message.reply_to, types.MessageReplyHeader):
            try:
                reply_to = int(message.reply_to.reply_to_msg_id) if message.reply_to.reply_to_msg_id else None
            except (AttributeError, TypeError, ValueError):
                pass

        return Message(
            message_id=message.id,
            sender_id=sender_id,
            message=message.text if isinstance(message.text, str) else None,  # type: ignore
            outgoing=message.out,
            date=message.date,
            media=Media.from_message(message),
            reply_to=reply_to,
        )


class Messages(BaseModel):
    messages: list[Message]
    dialog: Dialog | None = None
