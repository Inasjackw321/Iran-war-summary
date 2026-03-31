import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, render_template, request, session
from apscheduler.schedulers.background import BackgroundScheduler
import database as db
import telegram_client as tg
import gemini_client as gemini

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

db.init_db()
tg.start()

# ---------------------------------------------------------------------------
# Background refresh job
# ---------------------------------------------------------------------------

def refresh_all():
    """Fetch last-24h messages for every active channel and summarise them."""
    channels = db.get_channels()
    for ch in channels:
        try:
            messages = tg.fetch_channel_messages(ch["username"])
            summary = gemini.summarize(ch["display_name"] or ch["username"], messages)
            db.save_summary(ch["id"], summary, len(messages))
        except Exception as e:
            db.save_summary(ch["id"], f"Error fetching summary: {e}", 0)


scheduler = BackgroundScheduler()
scheduler.add_job(refresh_all, "interval", minutes=30, id="refresh_all")
scheduler.start()

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/status")
def api_status():
    try:
        authorized = tg.is_authorized()
    except Exception:
        authorized = False
    return jsonify({"authorized": authorized})


@app.post("/api/auth/send-code")
def api_send_code():
    phone = request.json.get("phone", os.environ.get("TELEGRAM_PHONE", ""))
    try:
        tg.send_code(phone)
        session["auth_phone"] = phone
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.post("/api/auth/verify")
def api_verify():
    code = request.json.get("code", "")
    password = request.json.get("password", "") or None
    phone = session.get("auth_phone", os.environ.get("TELEGRAM_PHONE", ""))
    try:
        tg.sign_in(code, password=password, phone=phone)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


# --- Channels ---

@app.get("/api/channels")
def api_get_channels():
    return jsonify(db.get_channels())


@app.post("/api/channels")
def api_add_channel():
    identifier = (request.json or {}).get("channel", "").strip()
    if not identifier:
        return jsonify({"ok": False, "error": "No channel provided"}), 400
    try:
        info = tg.resolve_channel(identifier)
        db.add_channel(info["username"], info["display_name"])
        return jsonify({"ok": True, **info})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.delete("/api/channels/<int:channel_id>")
def api_remove_channel(channel_id):
    db.remove_channel(channel_id)
    return jsonify({"ok": True})


# --- Summaries ---

@app.get("/api/summaries")
def api_summaries():
    return jsonify(db.get_latest_summaries())


@app.post("/api/refresh")
def api_refresh():
    try:
        refresh_all()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
