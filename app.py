import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, render_template, request, session
from apscheduler.schedulers.background import BackgroundScheduler
import database as db
import telegram_client as tg
import gemini_client as gemini

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

db.init_db()
tg.start()

# ---------------------------------------------------------------------------
# Scheduler — refresh summaries every 30 minutes
# ---------------------------------------------------------------------------

def refresh_all():
    for ch in db.get_channels():
        try:
            messages = tg.fetch_channel_messages(ch["username"])
            summary  = gemini.summarize(ch["display_name"] or ch["username"], messages)
            db.save_summary(ch["id"], summary, len(messages))
        except Exception as exc:
            db.save_summary(ch["id"], f"Error: {exc}", 0)


_scheduler = BackgroundScheduler(daemon=True)
_scheduler.add_job(refresh_all, "interval", minutes=30, id="refresh")
_scheduler.start()

# ---------------------------------------------------------------------------
# Routes — pages
# ---------------------------------------------------------------------------

@app.get("/")
def index():
    return render_template("index.html")

# ---------------------------------------------------------------------------
# Routes — auth
# ---------------------------------------------------------------------------

@app.get("/api/status")
def api_status():
    try:
        ok = tg.is_authorized()
    except Exception:
        ok = False
    return jsonify({"authorized": ok})


@app.post("/api/auth/send-code")
def api_send_code():
    phone = (request.json or {}).get("phone", "").strip()
    if not phone:
        return jsonify({"ok": False, "error": "Phone number required"}), 400
    try:
        tg.send_code(phone)
        session["auth_phone"] = phone
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.post("/api/auth/verify")
def api_verify():
    data     = request.json or {}
    code     = data.get("code", "").strip()
    password = data.get("password") or None
    phone    = session.get("auth_phone", "")
    if not code:
        return jsonify({"ok": False, "error": "Code required"}), 400
    try:
        tg.sign_in(phone, code, password=password)
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

# ---------------------------------------------------------------------------
# Routes — channels
# ---------------------------------------------------------------------------

@app.get("/api/channels")
def api_channels_get():
    return jsonify(db.get_channels())


@app.post("/api/channels")
def api_channels_add():
    identifier = (request.json or {}).get("channel", "").strip()
    if not identifier:
        return jsonify({"ok": False, "error": "No channel provided"}), 400
    try:
        info = tg.resolve_channel(identifier)
        db.add_channel(info["username"], info["display_name"])
        return jsonify({"ok": True, **info})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.delete("/api/channels/<int:channel_id>")
def api_channels_delete(channel_id):
    db.remove_channel(channel_id)
    return jsonify({"ok": True})

# ---------------------------------------------------------------------------
# Routes — summaries
# ---------------------------------------------------------------------------

@app.get("/api/summaries")
def api_summaries():
    return jsonify(db.get_latest_summaries())


@app.post("/api/refresh")
def api_refresh():
    try:
        refresh_all()
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
