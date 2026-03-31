import os
import sqlite3

# Fly.io mounts a persistent volume at /data — store everything there.
_DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
os.makedirs(_DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(_DATA_DIR, "summaries.db")


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS channels (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                username     TEXT    UNIQUE NOT NULL,
                display_name TEXT,
                active       INTEGER DEFAULT 1,
                added_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS summaries (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id    INTEGER REFERENCES channels(id) ON DELETE CASCADE,
                summary       TEXT,
                message_count INTEGER,
                generated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------

def add_channel(username: str, display_name: str = None):
    with _conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO channels (username, display_name) VALUES (?, ?)",
            (username, display_name or username),
        )


def remove_channel(channel_id: int):
    with _conn() as conn:
        conn.execute("DELETE FROM channels WHERE id = ?", (channel_id,))


def get_channels() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM channels WHERE active = 1 ORDER BY added_at"
        ).fetchall()
        return [dict(r) for r in rows]

# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------

def save_summary(channel_id: int, summary: str, message_count: int):
    with _conn() as conn:
        conn.execute(
            "INSERT INTO summaries (channel_id, summary, message_count) VALUES (?, ?, ?)",
            (channel_id, summary, message_count),
        )


def get_latest_summaries() -> list[dict]:
    """One row per active channel, containing its most recent summary."""
    with _conn() as conn:
        rows = conn.execute("""
            SELECT
                c.id, c.username, c.display_name,
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
