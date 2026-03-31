"""
Fetches the last 24 hours of messages from every channel listed in
channels.txt, summarises them with Gemini 2.5 Flash, and writes the
result to docs/summaries.json — which GitHub Pages serves to the world.
"""

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession
import google.generativeai as genai

# ---------------------------------------------------------------------------
# Config from environment (stored as GitHub Secrets)
# ---------------------------------------------------------------------------
API_ID   = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION  = os.environ["TELEGRAM_SESSION"]
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.5-flash-preview-04-17")

ROOT = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Load channel list
# ---------------------------------------------------------------------------
def load_channels():
    lines = (ROOT / "channels.txt").read_text(encoding="utf-8").splitlines()
    channels = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("https://t.me/") or line.startswith("t.me/"):
            line = line.split("t.me/")[-1].split("/")[0]
        if not line.startswith("@"):
            line = "@" + line
        channels.append(line)
    return channels

# ---------------------------------------------------------------------------
# Summarise one channel
# ---------------------------------------------------------------------------
async def summarise_channel(client, identifier: str) -> dict:
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    try:
        entity       = await client.get_entity(identifier)
        display_name = getattr(entity, "title",    identifier.lstrip("@"))
        username     = getattr(entity, "username", identifier.lstrip("@")) or identifier.lstrip("@")

        texts = []
        async for msg in client.iter_messages(entity, limit=500):
            if msg.date < since:
                break
            if msg.text and msg.text.strip():
                texts.append(msg.text.strip())

        if texts:
            prompt = (
                f'You are a news analyst. Summarise the messages below from the Telegram channel '
                f'"{display_name}" (last 24 hours) in clear English.\n'
                f'Cover the main topics, key facts, and overall tone. '
                f'Use bullet points. Keep it under 300 words.\n\n'
                + "\n\n".join(texts[:400])
            )
            summary = model.generate_content(prompt).text
        else:
            summary = "No messages in the last 24 hours."

        return {
            "username":      username,
            "display_name":  display_name,
            "summary":       summary,
            "message_count": len(texts),
            "updated_at":    datetime.now(timezone.utc).isoformat(),
            "error":         False,
        }

    except Exception as exc:
        print(f"Error processing {identifier}: {exc}")
        return {
            "username":      identifier.lstrip("@"),
            "display_name":  identifier.lstrip("@"),
            "summary":       f"Could not fetch channel: {exc}",
            "message_count": 0,
            "updated_at":    datetime.now(timezone.utc).isoformat(),
            "error":         True,
        }

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main():
    channels = load_channels()
    if not channels:
        print("No channels in channels.txt — nothing to do.")
        return

    print(f"Processing {len(channels)} channel(s)…")
    results = []

    async with TelegramClient(StringSession(SESSION), API_ID, API_HASH) as client:
        for ch in channels:
            print(f"  → {ch}")
            result = await summarise_channel(client, ch)
            results.append(result)
            print(f"     {result['message_count']} messages, summarised.")

    out = ROOT / "docs" / "summaries.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\nWrote {len(results)} summaries to {out}")


asyncio.run(main())
