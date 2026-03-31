import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "_shared"))
import db


def handler(event, context):
    summaries = db.get_latest_summaries()
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(summaries, default=str),
    }
