import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "_shared"))
import db
import tg
import gemini


def refresh_all():
    channels = db.get_channels()
    for ch in channels:
        try:
            messages = tg.fetch_channel_messages(ch["username"])
            summary  = gemini.summarize(ch["display_name"] or ch["username"], messages)
            db.save_summary(ch["id"], summary, len(messages))
        except Exception as e:
            db.save_summary(ch["id"], f"Error: {e}", 0)


def handler(event, context):
    try:
        refresh_all()
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"ok": True}),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"ok": False, "error": str(e)}),
        }
