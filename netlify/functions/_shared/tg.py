"""
Per-request Telethon client using StringSession.
Auth is done once locally via setup_auth.py; the resulting session string
is stored as the TELEGRAM_SESSION environment variable.
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID   = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]


def _session():
    return StringSession(os.environ.get("TELEGRAM_SESSION", ""))


def is_authorized() -> bool:
    """Return True if TELEGRAM_SESSION is set and the session is valid."""
    session_str = os.environ.get("TELEGRAM_SESSION", "").strip()
    if not session_str:
        return False

    async def _check():
        async with TelegramClient(_session(), API_ID, API_HASH) as client:
            return await client.is_user_authorized()

    try:
        return asyncio.run(_check())
    except Exception:
        return False


def resolve_channel(identifier: str) -> dict:
    """Return {'username': ..., 'display_name': ...} for a channel identifier."""
    identifier = identifier.strip()
    if identifier.startswith("https://t.me/") or identifier.startswith("t.me/"):
        identifier = identifier.split("t.me/")[-1].split("/")[0]
    if not identifier.startswith("@"):
        identifier = "@" + identifier

    async def _resolve():
        async with TelegramClient(_session(), API_ID, API_HASH) as client:
            entity = await client.get_entity(identifier)
            username = getattr(entity, "username", None) or identifier.lstrip("@")
            title    = getattr(entity, "title",    username)
            return {"username": username, "display_name": title}

    return asyncio.run(_resolve())


def fetch_channel_messages(identifier: str, hours: int = 24) -> list[str]:
    """Return text messages from the last `hours` hours for the given channel."""
    identifier = identifier.strip()
    if not identifier.startswith("@"):
        identifier = "@" + identifier
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    async def _fetch():
        texts = []
        async with TelegramClient(_session(), API_ID, API_HASH) as client:
            async for msg in client.iter_messages(identifier, reverse=False, limit=500):
                if msg.date < since:
                    break
                if msg.text and msg.text.strip():
                    texts.append(msg.text.strip())
        return texts

    return asyncio.run(_fetch())
