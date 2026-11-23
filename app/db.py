import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone


def _path() -> str:
    return os.getenv("DB_PATH", "tickets.db")


@contextmanager
def conn():
    c = sqlite3.connect(_path())
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db() -> None:
    with conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                category TEXT, priority TEXT, sentiment TEXT,
                summary TEXT, suggested_reply TEXT,
                created_at TEXT NOT NULL)"""
        )


def insert_ticket(text: str, r) -> dict:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with conn() as c:
        cur = c.execute(
            "INSERT INTO tickets (text, category, priority, sentiment, summary, suggested_reply, created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (text, r.category, r.priority, r.sentiment, r.summary, r.suggested_reply, now),
        )
        row = c.execute("SELECT * FROM tickets WHERE id=?", (cur.lastrowid,)).fetchone()
    return dict(row)


def list_tickets(limit: int = 50) -> list[dict]:
    with conn() as c:
        rows = c.execute("SELECT * FROM tickets ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
