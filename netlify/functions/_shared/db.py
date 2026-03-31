import os
import psycopg2
import psycopg2.extras


def _conn():
    return psycopg2.connect(os.environ["SUPABASE_DB_URL"], connect_timeout=10)


def init_db():
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    display_name TEXT,
                    active BOOLEAN DEFAULT TRUE,
                    added_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS summaries (
                    id SERIAL PRIMARY KEY,
                    channel_id INT REFERENCES channels(id) ON DELETE CASCADE,
                    summary TEXT,
                    message_count INT,
                    generated_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)


# --- Channels ---

def add_channel(username, display_name=None):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO channels (username, display_name) VALUES (%s, %s) ON CONFLICT (username) DO NOTHING",
                (username, display_name or username),
            )


def remove_channel(channel_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM channels WHERE id = %s", (channel_id,))


def get_channels():
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM channels WHERE active = TRUE ORDER BY added_at")
            return [dict(r) for r in cur.fetchall()]


def update_display_name(channel_id, display_name):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE channels SET display_name = %s WHERE id = %s",
                (display_name, channel_id),
            )


# --- Summaries ---

def save_summary(channel_id, summary, message_count):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO summaries (channel_id, summary, message_count) VALUES (%s, %s, %s)",
                (channel_id, summary, message_count),
            )


def get_latest_summaries():
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT c.id, c.username, c.display_name,
                       s.summary, s.message_count,
                       s.generated_at::text AS generated_at
                FROM channels c
                LEFT JOIN summaries s ON s.id = (
                    SELECT id FROM summaries
                    WHERE channel_id = c.id
                    ORDER BY generated_at DESC
                    LIMIT 1
                )
                WHERE c.active = TRUE
                ORDER BY c.added_at
            """)
            return [dict(r) for r in cur.fetchall()]
