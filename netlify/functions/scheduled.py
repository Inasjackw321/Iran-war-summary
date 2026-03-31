"""
Netlify Scheduled Function — runs every 30 minutes.
Fetches last-24h messages for every active channel and summarises them.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "_shared"))
import db
import tg
import gemini


def handler(event, context):
    channels = db.get_channels()
    for ch in channels:
        try:
            messages = tg.fetch_channel_messages(ch["username"])
            summary  = gemini.summarize(ch["display_name"] or ch["username"], messages)
            db.save_summary(ch["id"], summary, len(messages))
        except Exception as e:
            db.save_summary(ch["id"], f"Error: {e}", 0)
