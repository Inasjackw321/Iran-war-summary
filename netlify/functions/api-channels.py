import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "_shared"))
import db
import tg


def _ok(body):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def _err(msg, status=400):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"ok": False, "error": msg}),
    }


def handler(event, context):
    method = event["httpMethod"]

    if method == "GET":
        channels = db.get_channels()
        return _ok(channels)

    elif method == "POST":
        body = json.loads(event.get("body") or "{}")
        identifier = body.get("channel", "").strip()
        if not identifier:
            return _err("No channel provided")
        try:
            info = tg.resolve_channel(identifier)
            db.add_channel(info["username"], info["display_name"])
            return _ok({"ok": True, **info})
        except Exception as e:
            return _err(str(e))

    elif method == "DELETE":
        body = json.loads(event.get("body") or "{}")
        channel_id = body.get("id")
        if channel_id is None:
            return _err("No id provided")
        db.remove_channel(int(channel_id))
        return _ok({"ok": True})

    return _err("Method not allowed", 405)
