"""
Fetches the last 24 hours of messages from every channel listed in
channels.txt, summarises them with Gemini 2.5 Flash, and writes the
result to docs/summaries.json — which GitHub Pages serves to the world.
"""

import asyncio
import json
import os
import re
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
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=24)

    try:
        entity       = await client.get_entity(identifier)
        display_name = getattr(entity, "title",    identifier.lstrip("@"))
        username     = getattr(entity, "username", identifier.lstrip("@")) or identifier.lstrip("@")

        texts      = []
        timestamps = []
        async for msg in client.iter_messages(entity, limit=500):
            if msg.date < since:
                break
            if msg.text and msg.text.strip():
                texts.append(msg.text.strip())
                timestamps.append(msg.date)

        # Build 24-bucket hourly activity (index 0 = oldest hour, 23 = most recent)
        hourly_counts = [0] * 24
        hourly_labels = [
            (now - timedelta(hours=23 - i)).strftime("%H:00")
            for i in range(24)
        ]
        for ts in timestamps:
            h = int((now - ts).total_seconds() / 3600)
            if 0 <= h < 24:
                hourly_counts[23 - h] += 1

        if texts:
            prompt = (
                f'You are a senior news analyst. Analyse these {len(texts)} messages from the Telegram channel '
                f'"{display_name}" covering the last 24 hours.\n\n'
                f'Return ONLY a valid JSON object — no markdown fences, no extra text — in exactly this structure:\n'
                f'{{"summary":"<detailed 400-500 word analysis. Use numbered sections:\\n'
                f'1. Main Events\\n2. Key Figures\\n3. Important Developments\\n'
                f'4. Context & Implications\\n5. Overall Narrative\\n'
                f'Be specific: include names, dates, numbers from the messages.>","topics":[{{"label":"<topic name>","score":<integer>}}],'
                f'"tone":"<positive|negative|neutral|mixed>"}}\n\n'
                f'Rules:\n'
                f'- topics: 3 to 6 items, scores are integers that sum to exactly 100\n'
                f'- summary: write in clear English paragraphs under each numbered heading\n\n'
                f'Messages:\n'
                + "\n---\n".join(texts[:400])
            )

            raw = model.generate_content(prompt).text.strip()
            raw = re.sub(r'^```(?:json)?\s*', '', raw)
            raw = re.sub(r'\s*```$', '', raw.strip())

            try:
                parsed = json.loads(raw)
                summary = parsed.get("summary", raw)
                topics  = [
                    t for t in parsed.get("topics", [])
                    if isinstance(t, dict) and "label" in t and "score" in t
                ]
                tone = parsed.get("tone", "neutral")
            except (json.JSONDecodeError, AttributeError):
                summary = raw
                topics  = []
                tone    = "neutral"
        else:
            summary = "No messages in the last 24 hours."
            topics  = []
            tone    = "neutral"

        return {
            "username":      username,
            "display_name":  display_name,
            "summary":       summary,
            "message_count": len(texts),
            "updated_at":    now.isoformat(),
            "error":         False,
            "hourly_counts": hourly_counts,
            "hourly_labels": hourly_labels,
            "topics":        topics,
            "tone":          tone,
        }

    except Exception as exc:
        print(f"Error processing {identifier}: {exc}")
        return {
            "username":      identifier.lstrip("@"),
            "display_name":  identifier.lstrip("@"),
            "summary":       f"Could not fetch channel: {exc}",
            "message_count": 0,
            "updated_at":    now.isoformat(),
            "error":         True,
            "hourly_counts": [0] * 24,
            "hourly_labels": [
                (now - timedelta(hours=23 - i)).strftime("%H:00")
                for i in range(24)
            ],
            "topics":        [],
            "tone":          "neutral",
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
