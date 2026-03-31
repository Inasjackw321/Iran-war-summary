"""
Telethon wrapper that runs in a dedicated background thread with its own
asyncio event loop, so Flask (sync) can safely call into it.
"""

import asyncio
import os
import threading
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import Channel, Chat

_DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(__file__))
SESSION_FILE = os.path.join(_DATA_DIR, "telegram.session")
API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
PHONE = os.environ["TELEGRAM_PHONE"]

# Shared state
_loop: asyncio.AbstractEventLoop | None = None
_client: TelegramClient | None = None
_thread: threading.Thread | None = None
_phone_code_hash: str | None = None


def _start_loop():
    global _loop, _client
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    # loop parameter removed in Telethon ≥1.24; client picks up the current loop
    _client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    _loop.run_until_complete(_client.connect())
    _loop.run_forever()


def start():
    global _thread
    _thread = threading.Thread(target=_start_loop, daemon=True)
    _thread.start()
    # Wait until the loop is ready
    import time
    for _ in range(50):
        if _loop is not None:
            break
        time.sleep(0.1)


def _run(coro):
    """Submit a coroutine to the background loop and block until result."""
    if _loop is None:
        raise RuntimeError("Telegram client not started")
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result(timeout=60)


# --- Auth ---

def is_authorized() -> bool:
    return _run(_client.is_user_authorized())


def send_code(phone: str = PHONE) -> str:
    global _phone_code_hash
    result = _run(_client.send_code_request(phone))
    _phone_code_hash = result.phone_code_hash
    return _phone_code_hash


def sign_in(code: str, password: str | None = None, phone: str = PHONE):
    global _phone_code_hash
    try:
        _run(_client.sign_in(phone, code, phone_code_hash=_phone_code_hash))
    except SessionPasswordNeededError:
        if not password:
            raise
        _run(_client.sign_in(password=password))


# --- Channel helpers ---

async def _resolve_entity(identifier: str):
    """Accept @username, username, or t.me/… links."""
    identifier = identifier.strip()
    if identifier.startswith("https://t.me/") or identifier.startswith("t.me/"):
        identifier = identifier.split("t.me/")[-1].split("/")[0]
    if not identifier.startswith("@"):
        identifier = "@" + identifier
    return await _client.get_entity(identifier)


def resolve_channel(identifier: str) -> dict:
    """Return display name + canonical username for a channel identifier."""
    entity = _run(_resolve_entity(identifier))
    username = getattr(entity, "username", None) or identifier.lstrip("@")
    title = getattr(entity, "title", username)
    return {"username": username, "display_name": title}


async def _fetch_messages(identifier: str, hours: int = 24) -> list[str]:
    entity = await _resolve_entity(identifier)
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    texts = []
    async for msg in _client.iter_messages(entity, reverse=False, limit=None):
        if msg.date < since:
            break
        text = msg.text or ""
        if text.strip():
            texts.append(text.strip())
    return texts


def fetch_channel_messages(identifier: str, hours: int = 24) -> list[str]:
    return _run(_fetch_messages(identifier, hours))
