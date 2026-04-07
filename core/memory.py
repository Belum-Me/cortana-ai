import sqlite3
import json
from datetime import datetime
from config import MEMORY_DB_PATH


def get_connection():
    return sqlite3.connect(MEMORY_DB_PATH)


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT NOT NULL,
            source TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            cortana_position TEXT NOT NULL,
            user_decision TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_message(role: str, content: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO conversations (role, content, timestamp) VALUES (?, ?, ?)",
        (role, content, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_recent_history(limit: int = 20) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT role, content FROM conversations ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]


def save_fact(key: str, value: str, source: str = None):
    conn = get_connection()
    now = datetime.now().isoformat()
    conn.execute("""
        INSERT INTO facts (key, value, source, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, source=excluded.source, updated_at=excluded.updated_at
    """, (key, value, source, now, now))
    conn.commit()
    conn.close()


def log_override(topic: str, cortana_position: str, user_decision: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO overrides (topic, cortana_position, user_decision, timestamp) VALUES (?, ?, ?, ?)",
        (topic, cortana_position, user_decision, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
