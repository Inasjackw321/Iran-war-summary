"""
Telethon wrapper for Flask.

Session persistence strategy:
  - If TELEGRAM_SESSION env var is set, use StringSession (survives restarts).
  - Otherwise fall back to a file-based session (works locally / Fly.io).
After signing in, call get_session_string() to get the serialised string
and save it as TELEGRAM_SESSION in your host's env vars.
"""

import asyncio
import os
import threading
import time
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_DATA_DIR    = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
_SESSION_STR = os.environ.get("TELEGRAM_SESSION", "").strip()
SESSION_FILE = os.path.join(_DATA_DIR, "telegram.session")

API_ID   = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
PHONE    = os.environ.get("TELEGRAM_PHONE", "")

# ---------------------------------------------------------------------------
# Background event loop + client
# ---------------------------------------------------------------------------

_loop:   asyncio.AbstractEventLoop | None = None
_client: TelegramClient | None           = None
_phone_code_hash: str | None             = None


def _make_session():
    """Use StringSession if env var is set, otherwise file-based session."""
    if _SESSION_STR:
        return StringSession(_SESSION_STR)
    return SESSION_FILE


def _run_loop():
    global _loop, _client
    _loop   = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    _client = TelegramClient(_make_session(), API_ID, API_HASH)
    _loop.run_until_complete(_client.connect())
    _loop.run_forever()


def start():
    t = threading.Thread(target=_run_loop, daemon=True, name="telegram-loop")
    t.start()
    for _ in range(100):
        if _loop is not None:
            break
        time.sleep(0.1)


def _run(coro, timeout: int = 60):
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


def get_session_string() -> str:
    """Return the serialised session string — save this as TELEGRAM_SESSION."""
    if _client is None:
        return ""
    return _client.session.save()

# ---------------------------------------------------------------------------
# Channel helpers
# ---------------------------------------------------------------------------

def _normalise(identifier: str) -> str:
    s = identifier.strip()
    if s.startswith("https://t.me/") or s.startswith("t.me/"):
        s = s.split("t.me/")[-1].split("/")[0]
    return s if s.startswith("@") else f"@{s}"


def resolve_channel(identifier: str) -> dict:
    tag = _normalise(identifier)

    async def _resolve():
        entity = await _client.get_entity(tag)
        return {
            "username":     getattr(entity, "username", None) or tag.lstrip("@"),
            "display_name": getattr(entity, "title",    tag.lstrip("@")),
        }

    return _run(_resolve())


def fetch_channel_messages(username: str, hours: int = 24) -> list[str]:
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
