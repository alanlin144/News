"""
database.py
Quản lý toàn bộ dữ liệu của app bằng SQLite: nguồn tin (sources),
bài viết đã crawl (articles), và cài đặt chung (settings) như API key,
danh sách chủ đề quan tâm.
"""

import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager

APP_DIR = os.path.join(os.path.expanduser("~"), ".news_filter_app")
os.makedirs(APP_DIR, exist_ok=True)
DB_PATH = os.path.join(APP_DIR, "news_filter.db")


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                feed_url TEXT,
                enabled INTEGER DEFAULT 1,
                created_at TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER,
                title TEXT NOT NULL,
                link TEXT NOT NULL UNIQUE,
                original_summary TEXT,
                ai_summary TEXT,
                is_relevant INTEGER,
                topic_tag TEXT,
                published_at TEXT,
                fetched_at TEXT,
                FOREIGN KEY(source_id) REFERENCES sources(id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()


# ---------- Settings ----------

def set_setting(key: str, value: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def get_setting(key: str, default=None):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


# ---------- Sources ----------

def add_source(name: str, url: str, feed_url: str = None):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sources (name, url, feed_url, enabled, created_at) "
            "VALUES (?, ?, ?, 1, ?)",
            (name, url, feed_url, datetime.now().isoformat()),
        )


def remove_source(source_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM sources WHERE id=?", (source_id,))


def set_source_enabled(source_id: int, enabled: bool):
    with get_conn() as conn:
        conn.execute("UPDATE sources SET enabled=? WHERE id=?", (1 if enabled else 0, source_id))


def get_sources(enabled_only: bool = False):
    with get_conn() as conn:
        q = "SELECT * FROM sources"
        if enabled_only:
            q += " WHERE enabled=1"
        q += " ORDER BY id DESC"
        return [dict(r) for r in conn.execute(q).fetchall()]


# ---------- Articles ----------

def article_exists(link: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM articles WHERE link=?", (link,)).fetchone()
        return row is not None


def add_article(source_id, title, link, original_summary, ai_summary,
                 is_relevant, topic_tag, published_at):
    with get_conn() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO articles
               (source_id, title, link, original_summary, ai_summary,
                is_relevant, topic_tag, published_at, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (source_id, title, link, original_summary, ai_summary,
             1 if is_relevant else 0, topic_tag, published_at,
             datetime.now().isoformat()),
        )


def get_articles(relevant_only: bool = True, limit: int = 200, topic: str = None):
    with get_conn() as conn:
        q = """SELECT articles.*, sources.name as source_name
               FROM articles LEFT JOIN sources ON articles.source_id = sources.id
               WHERE 1=1"""
        params = []
        if relevant_only:
            q += " AND is_relevant=1"
        if topic:
            q += " AND topic_tag=?"
            params.append(topic)
        q += " ORDER BY fetched_at DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in conn.execute(q, params).fetchall()]


def get_stats():
    """Trả về thống kê số lượng bài theo chủ đề và theo nguồn (chỉ tin liên quan)."""
    with get_conn() as conn:
        by_topic = conn.execute(
            """SELECT COALESCE(topic_tag, 'Khác') as topic, COUNT(*) as count
               FROM articles WHERE is_relevant=1
               GROUP BY topic ORDER BY count DESC"""
        ).fetchall()
        by_source = conn.execute(
            """SELECT sources.name as source, COUNT(*) as count
               FROM articles LEFT JOIN sources ON articles.source_id = sources.id
               WHERE is_relevant=1
               GROUP BY sources.name ORDER BY count DESC"""
        ).fetchall()
        total_relevant = conn.execute(
            "SELECT COUNT(*) as c FROM articles WHERE is_relevant=1"
        ).fetchone()["c"]
        total_spam = conn.execute(
            "SELECT COUNT(*) as c FROM articles WHERE is_relevant=0"
        ).fetchone()["c"]
        return {
            "by_topic": [dict(r) for r in by_topic],
            "by_source": [dict(r) for r in by_source],
            "total_relevant": total_relevant,
            "total_spam": total_spam,
        }
