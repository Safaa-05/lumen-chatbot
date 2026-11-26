import sqlite3

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    pw_hash  TEXT NOT NULL,
    created  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Privacy by design: there is no column for message text.
CREATE TABLE IF NOT EXISTS mood_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    emotion    TEXT NOT NULL,
    intensity  REAL NOT NULL,
    confidence REAL,
    risk       TEXT NOT NULL DEFAULT 'none',
    created    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mood_user_time ON mood_logs (user_id, created);
"""


def get_db():
    """One database connection per request."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()