"""SQLite-backed storage for the BYOK 衣帽间 layer.

Schema is minimal on purpose:

    user_keys
      user_token              TEXT PRIMARY KEY     -- the short code we hand back
      label                   TEXT NOT NULL        -- user-supplied nickname
      encrypted_semrush_key   BLOB NOT NULL        -- Fernet ciphertext
      created_at              TEXT NOT NULL        -- iso utc
      last_used_at            TEXT                 -- iso utc, updated each call
      total_request_count     INTEGER DEFAULT 0    -- lifetime
      day_request_count       INTEGER DEFAULT 0    -- resets at midnight UTC
      day_window_start        TEXT                 -- iso utc date 'YYYY-MM-DD'
      month_request_count     INTEGER DEFAULT 0    -- resets on 1st of month UTC
      month_window_start      TEXT                 -- iso utc 'YYYY-MM'
      daily_quota             INTEGER              -- nullable → uses default
      monthly_quota           INTEGER              -- nullable → uses default
      status                  TEXT NOT NULL        -- active | revoked

We deliberately keep this synchronous + single-file so the project boots
with zero infra dependencies.  Swap to Postgres later by replacing this
module — the rest of the code only sees the public functions below.
"""
from __future__ import annotations

import secrets
import sqlite3
import string
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from app.config import settings


# ----- public dataclass returned to callers (no SQL exposed outward) -----

@dataclass
class UserKeyRecord:
    user_token: str
    label: str
    semrush_api_key: str        # decrypted, only present when fetched via get_decrypted
    created_at: str
    last_used_at: Optional[str]
    total_request_count: int
    day_request_count: int
    month_request_count: int
    daily_quota: Optional[int]
    monthly_quota: Optional[int]
    status: str


# ----- token format -----
# floor-XXXX-XXXX with an alphabet that excludes look-alike chars.
_TOKEN_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no I, L, O, 0, 1


def generate_user_token() -> str:
    a = "".join(secrets.choice(_TOKEN_ALPHABET) for _ in range(4))
    b = "".join(secrets.choice(_TOKEN_ALPHABET) for _ in range(4))
    return f"floor-{a}-{b}"


# ----- DB helpers -----

_DB_INITIALIZED = False


def _connect() -> sqlite3.Connection:
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.database_path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    global _DB_INITIALIZED
    if _DB_INITIALIZED:
        return
    with _connect() as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS user_keys (
            user_token            TEXT PRIMARY KEY,
            label                 TEXT NOT NULL,
            encrypted_semrush_key BLOB NOT NULL,
            created_at            TEXT NOT NULL,
            last_used_at          TEXT,
            total_request_count   INTEGER NOT NULL DEFAULT 0,
            day_request_count     INTEGER NOT NULL DEFAULT 0,
            day_window_start      TEXT,
            month_request_count   INTEGER NOT NULL DEFAULT 0,
            month_window_start    TEXT,
            daily_quota           INTEGER,
            monthly_quota         INTEGER,
            status                TEXT NOT NULL DEFAULT 'active'
        )
        """)
    _DB_INITIALIZED = True


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


# ----- public CRUD -----

def create_user_key(
    label: str,
    encrypted_key: bytes,
    daily_quota: Optional[int] = None,
    monthly_quota: Optional[int] = None,
) -> str:
    init_db()
    token = generate_user_token()
    with _connect() as c:
        c.execute("""
            INSERT INTO user_keys (
                user_token, label, encrypted_semrush_key, created_at,
                day_window_start, month_window_start,
                daily_quota, monthly_quota, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
        """, (token, label, encrypted_key, _now_iso(), _today(), _month(),
              daily_quota, monthly_quota))
    return token


def revoke(user_token: str) -> bool:
    init_db()
    with _connect() as c:
        cur = c.execute(
            "UPDATE user_keys SET status='revoked' WHERE user_token=? AND status='active'",
            (user_token,),
        )
        return cur.rowcount > 0


def get_active_record(user_token: str) -> Optional[sqlite3.Row]:
    """Internal use — returns the raw row (with encrypted blob) for the analyze flow."""
    init_db()
    with _connect() as c:
        row = c.execute(
            "SELECT * FROM user_keys WHERE user_token=? AND status='active'",
            (user_token,),
        ).fetchone()
    return row


def get_summary(user_token: str) -> Optional[UserKeyRecord]:
    """Public-safe summary (no decrypted key)."""
    row = get_active_record(user_token)
    if not row:
        return None
    return UserKeyRecord(
        user_token=row["user_token"],
        label=row["label"],
        semrush_api_key="",  # never exposed in summary
        created_at=row["created_at"],
        last_used_at=row["last_used_at"],
        total_request_count=row["total_request_count"],
        day_request_count=row["day_request_count"],
        month_request_count=row["month_request_count"],
        daily_quota=row["daily_quota"],
        monthly_quota=row["monthly_quota"],
        status=row["status"],
    )


def record_usage(user_token: str) -> None:
    """Bumps counters; rolls daily/monthly windows if needed.  Idempotent
    enough for our purposes — quota check happens before this fires."""
    init_db()
    today = _today()
    month = _month()
    with _connect() as c:
        row = c.execute(
            "SELECT day_window_start, month_window_start FROM user_keys WHERE user_token=?",
            (user_token,),
        ).fetchone()
        if not row:
            return

        # roll windows if needed
        if row["day_window_start"] != today:
            c.execute(
                "UPDATE user_keys SET day_window_start=?, day_request_count=0 WHERE user_token=?",
                (today, user_token),
            )
        if row["month_window_start"] != month:
            c.execute(
                "UPDATE user_keys SET month_window_start=?, month_request_count=0 WHERE user_token=?",
                (month, user_token),
            )

        c.execute("""
            UPDATE user_keys
               SET total_request_count = total_request_count + 1,
                   day_request_count   = day_request_count + 1,
                   month_request_count = month_request_count + 1,
                   last_used_at        = ?
             WHERE user_token = ?
        """, (_now_iso(), user_token))
