import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "_shared"))
import tg


def handler(event, context):
    try:
        authorized = tg.is_authorized()
    except Exception:
        authorized = False
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"authorized": authorized}),
    }
