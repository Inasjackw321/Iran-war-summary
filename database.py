import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "summaries.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                display_name TEXT,
                active INTEGER DEFAULT 1,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,
                summary TEXT,
                message_count INTEGER,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)


# --- Channels ---

def add_channel(username, display_name=None):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO channels (username, display_name) VALUES (?, ?)",
            (username, display_name or username),
        )


def remove_channel(channel_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM channels WHERE id = ?", (channel_id,))


def get_channels():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM channels WHERE active = 1 ORDER BY added_at"
        ).fetchall()
        return [dict(r) for r in rows]


def update_channel_display_name(channel_id, display_name):
    with get_conn() as conn:
        conn.execute(
            "UPDATE channels SET display_name = ? WHERE id = ?",
            (display_name, channel_id),
        )


# --- Summaries ---

def save_summary(channel_id, summary, message_count):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO summaries (channel_id, summary, message_count) VALUES (?, ?, ?)",
            (channel_id, summary, message_count),
        )


def get_latest_summaries():
    """Return the most recent summary for each active channel."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT c.id, c.username, c.display_name,
                   s.summary, s.message_count, s.generated_at
            FROM channels c
            LEFT JOIN summaries s ON s.id = (
                SELECT id FROM summaries
                WHERE channel_id = c.id
                ORDER BY generated_at DESC
                LIMIT 1
            )
            WHERE c.active = 1
            ORDER BY c.added_at
        """).fetchall()
        return [dict(r) for r in rows]
