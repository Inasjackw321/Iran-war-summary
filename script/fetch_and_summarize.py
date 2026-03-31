"""
Fetches the last 24 hours of messages from every channel in channels.txt,
combines them all, and generates ONE unified intelligence briefing with Gemini.
Writes the result to docs/summaries.json for GitHub Pages to serve.
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
# Config
# ---------------------------------------------------------------------------
API_ID   = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION  = os.environ["TELEGRAM_SESSION"]
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.0-flash")

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
# Fetch messages from one channel
# ---------------------------------------------------------------------------
async def fetch_channel(client, identifier: str, since: datetime):
    try:
        entity       = await client.get_entity(identifier)
        display_name = getattr(entity, "title",    identifier.lstrip("@"))
        username     = getattr(entity, "username", identifier.lstrip("@")) or identifier.lstrip("@")

        texts      = []
        timestamps = []
        async for msg in client.iter_messages(entity, limit=200):
            if msg.date < since:
                break
            if msg.text and msg.text.strip():
                texts.append(msg.text.strip())
                timestamps.append(msg.date)

        return {
            "username":     username,
            "display_name": display_name,
            "texts":        texts,
            "timestamps":   timestamps,
            "error":        None,
        }
    except Exception as exc:
        print(f"  ✗ {identifier}: {exc}")
        return {
            "username":     identifier.lstrip("@"),
            "display_name": identifier.lstrip("@"),
            "texts":        [],
            "timestamps":   [],
            "error":        str(exc),
        }

# ---------------------------------------------------------------------------
# Build combined intelligence briefing
# ---------------------------------------------------------------------------
def build_briefing(channels_data, now):
    # Aggregate messages by channel for the prompt
    sections = []
    total = 0
    for ch in channels_data:
        if ch["texts"]:
            total += len(ch["texts"])
            # Max 60 messages per channel to keep prompt manageable
            sample = ch["texts"][:60]
            sections.append(
                f"=== SOURCE: {ch['display_name']} (@{ch['username']}) ===\n"
                + "\n".join(f"• {t}" for t in sample)
            )

    if not sections:
        return None, 0

    date_str = now.strftime("%d %B %Y, %H:%M UTC")
    source_list = ", ".join(
        ch["display_name"] for ch in channels_data if ch["texts"]
    )

    prompt = f"""You are a senior intelligence analyst. Based on the raw Telegram messages below from {len(sections)} sources covering the last 24 hours, produce a comprehensive intelligence briefing about the Iran war situation.

Date: {date_str}
Sources: {source_list}

FORMAT THE BRIEFING EXACTLY AS FOLLOWS (use these exact section headers):

EXECUTIVE SUMMARY
[2-3 sentence overview of the most critical developments]

SITUATION REPORT
[Detailed account of military and political events — what happened, where, when, with specific details from the messages]

KEY DEVELOPMENTS
[Numbered list of the 5-8 most significant events or facts]

THREAT ASSESSMENT
[Analysis of escalation risks, military posture, and danger areas]

REGIONAL & INTERNATIONAL RESPONSE
[How other countries, governments, and actors are responding]

INTELLIGENCE NOTES
[Contradictions between sources, unverified claims, or notable gaps]

Be specific. Use names, places, numbers, and dates from the raw messages. Write in clear professional English. Do not add disclaimers or commentary outside the briefing format.

--- RAW INTELLIGENCE FEED ---

{chr(10).join(sections)}
"""
    return prompt, total

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main():
    channels = load_channels()
    if not channels:
        print("No channels in channels.txt — nothing to do.")
        return

    now   = datetime.now(timezone.utc)
    since = now - timedelta(hours=24)

    print(f"Fetching {len(channels)} channel(s)…")
    channels_data = []

    async with TelegramClient(StringSession(SESSION), API_ID, API_HASH) as client:
        for ch in channels:
            print(f"  → {ch}")
            result = await fetch_channel(client, ch, since)
            channels_data.append(result)
            print(f"     {len(result['texts'])} messages")

    # Build hourly activity (24 buckets across all channels combined)
    hourly_counts = [0] * 24
    hourly_labels = [
        (now - timedelta(hours=23 - i)).strftime("%H:00")
        for i in range(24)
    ]
    for ch in channels_data:
        for ts in ch["timestamps"]:
            h = int((now - ts).total_seconds() / 3600)
            if 0 <= h < 24:
                hourly_counts[23 - h] += 1

    # Generate briefing
    prompt, total_messages = build_briefing(channels_data, now)

    if prompt:
        print(f"\nGenerating briefing from {total_messages} messages…")
        raw = model.generate_content(prompt).text.strip()
        briefing_text = raw
    else:
        briefing_text = "No messages found in the last 24 hours across monitored channels."

    # Sources list
    sources = [
        {"username": ch["username"], "display_name": ch["display_name"], "count": len(ch["texts"])}
        for ch in channels_data
    ]

    output = {
        "briefing":      briefing_text,
        "sources":       sources,
        "total_messages": total_messages,
        "updated_at":    now.isoformat(),
        "hourly_counts": hourly_counts,
        "hourly_labels": hourly_labels,
    }

    out = ROOT / "docs" / "summaries.json"
    out.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"\nBriefing written to {out}")


asyncio.run(main())
