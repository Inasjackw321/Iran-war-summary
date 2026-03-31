"""
Telethon wrapper for Flask.

Telethon is async; Flask is sync. This module runs a dedicated asyncio event
loop on a background thread and exposes a simple synchronous API to the rest
of the app via run_coroutine_threadsafe().
"""

import asyncio
import os
import threading
import time
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

# ---------------------------------------------------------------------------
# Config — read from environment
# ---------------------------------------------------------------------------

_DATA_DIR   = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
SESSION_FILE = os.path.join(_DATA_DIR, "telegram.session")
API_ID      = int(os.environ["TELEGRAM_API_ID"])
API_HASH    = os.environ["TELEGRAM_API_HASH"]
PHONE       = os.environ.get("TELEGRAM_PHONE", "")

# ---------------------------------------------------------------------------
# Background event loop + client
# ---------------------------------------------------------------------------

_loop:   asyncio.AbstractEventLoop | None = None
_client: TelegramClient | None           = None
_phone_code_hash: str | None             = None


def _run_loop():
    global _loop, _client
    _loop   = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    _client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    _loop.run_until_complete(_client.connect())
    _loop.run_forever()


def start():
    """Start the background Telegram event loop. Call once at app startup."""
    t = threading.Thread(target=_run_loop, daemon=True, name="telegram-loop")
    t.start()
    for _ in range(100):          # wait up to 10 s for loop to be ready
        if _loop is not None:
            break
        time.sleep(0.1)


def _run(coro, timeout: int = 60):
    """Submit a coroutine to the background loop and block until done."""
    if _loop is None:
        raise RuntimeError("Telegram client not started")
    return asyncio.run_coroutine_threadsafe(coro, _loop).result(timeout=timeout)

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def is_authorized() -> bool:
    return _run(_client.is_user_authorized())


def send_code(phone: str) -> None:
    global _phone_code_hash
    result = _run(_client.send_code_request(phone))
    _phone_code_hash = result.phone_code_hash


def sign_in(phone: str, code: str, password: str | None = None) -> None:
    global _phone_code_hash
    try:
        _run(_client.sign_in(phone, code, phone_code_hash=_phone_code_hash))
    except SessionPasswordNeededError:
        if not password:
            raise ValueError("2FA password required")
        _run(_client.sign_in(password=password))

# ---------------------------------------------------------------------------
# Channel helpers
# ---------------------------------------------------------------------------

def _normalise(identifier: str) -> str:
    """Turn a t.me link or bare name into @username."""
    s = identifier.strip()
    if s.startswith("https://t.me/") or s.startswith("t.me/"):
        s = s.split("t.me/")[-1].split("/")[0]
    return s if s.startswith("@") else f"@{s}"


def resolve_channel(identifier: str) -> dict:
    """Return {username, display_name} for a channel identifier."""
    tag = _normalise(identifier)

    async def _resolve():
        entity = await _client.get_entity(tag)
        return {
            "username":     getattr(entity, "username", None) or tag.lstrip("@"),
            "display_name": getattr(entity, "title",    tag.lstrip("@")),
        }

    return _run(_resolve())


def fetch_channel_messages(username: str, hours: int = 24) -> list[str]:
    """Return text messages posted in the last `hours` hours."""
    tag   = _normalise(username)
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    async def _fetch():
        texts = []
        async for msg in _client.iter_messages(tag, limit=500):
            if msg.date < since:
                break
            if msg.text and msg.text.strip():
                texts.append(msg.text.strip())
        return texts

    return _run(_fetch(), timeout=120)
