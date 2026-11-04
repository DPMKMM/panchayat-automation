"""SQLite-backed portal session metadata and serialized report job status."""

from __future__ import annotations

import hashlib
import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path
from typing import Any


class PortalSQLStore:
    """Persist per-browser session metadata and the single-instance report queue.

    Live Playwright objects, credentials, OTPs, and cookies remain in memory only.
    Session identifiers are stored as SHA-256 hashes so the browser cookie value is
    never written to the database.
    """

    def __init__(self, database_path: str | Path):
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _session_key_hash(session_id: str) -> str:
        return hashlib.sha256(session_id.encode("utf-8")).hexdigest()

    def _initialize(self) -> None:
        with self._initialize_lock, closing(self._connect()) as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS portal_sessions (
                    session_key_hash TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'idle',
                    mode TEXT NOT NULL DEFAULT 'idle',
                    created_at REAL NOT NULL DEFAULT 0,
                    authenticated_at REAL NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS portal_report_jobs (
                    job_id TEXT PRIMARY KEY,
                    session_key_hash TEXT NOT NULL,
                    module TEXT NOT NULL,
                    report_date TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    percent INTEGER NOT NULL DEFAULT 0,
                    step INTEGER NOT NULL DEFAULT 0,
                    stage TEXT NOT NULL DEFAULT 'queued',
                    message TEXT NOT NULL DEFAULT '',
                    remark TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    FOREIGN KEY (session_key_hash)
                        REFERENCES portal_sessions(session_key_hash)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_portal_jobs_session_created
                    ON portal_report_jobs(session_key_hash, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_portal_jobs_status_created
                    ON portal_report_jobs(status, created_at);
            """)

    def reset_after_process_restart(self) -> None:
        """A process restart destroys its live browsers, so clear persisted login flags."""
        now = time.time()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE portal_sessions SET status='idle', mode='idle', authenticated_at=0, updated_at=?",
                (now,),
            )
            connection.execute("""
                UPDATE portal_report_jobs
                SET status='error', stage='interrupted',
                    message='Server restarted before this report finished. Please submit it again.',
                    remark='Server restarted before this report finished. Please submit it again.',
                    updated_at=?
                WHERE status IN ('queued', 'running')
            """, (now,))
            connection.execute("COMMIT")

    def save_session(self, session_id: str, state: dict[str, Any]) -> None:
        """Persist only status metadata; never persist credentials or browser state."""
        now = time.time()
        session_hash = self._session_key_hash(session_id)
        with closing(self._connect()) as connection:
            connection.execute("""
                INSERT INTO portal_sessions
                    (session_key_hash, status, mode, created_at, authenticated_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_key_hash) DO UPDATE SET
                    status=excluded.status,
                    mode=excluded.mode,
                    created_at=excluded.created_at,
                    authenticated_at=excluded.authenticated_at,
                    updated_at=excluded.updated_at
            """, (
                session_hash,
                str(state.get("status") or "idle"),
                str(state.get("mode") or "idle"),
                float(state.get("created_at") or now),
                float(state.get("authenticated_at") or 0),
                now,
            ))

    def clear_session(self, session_id: str) -> None:
        session_hash = self._session_key_hash(session_id)
        now = time.time()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("""
                INSERT INTO portal_sessions
                    (session_key_hash, status, mode, created_at, authenticated_at, updated_at)
                VALUES (?, 'idle', 'idle', ?, 0, ?)
                ON CONFLICT(session_key_hash) DO UPDATE SET
                    status='idle', mode='idle', authenticated_at=0, updated_at=excluded.updated_at
            """, (session_hash, now, now))
            connection.execute(
                "DELETE FROM portal_report_jobs WHERE session_key_hash=?",
                (session_hash,),
            )
            connection.execute("COMMIT")

    def enqueue_report(self, session_id: str, job_id: str, module: str, report_date: str) -> None:
        session_hash = self._session_key_hash(session_id)
        now = time.time()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("""
                INSERT INTO portal_sessions
                    (session_key_hash, status, mode, created_at, authenticated_at, updated_at)
                VALUES (?, 'idle', 'idle', ?, 0, ?)
                ON CONFLICT(session_key_hash) DO NOTHING
            """, (session_hash, now, now))
            active = connection.execute("""
                SELECT job_id FROM portal_report_jobs
                WHERE session_key_hash=? AND status IN ('queued', 'running')
                LIMIT 1
            """, (session_hash,)).fetchone()
            if active:
                connection.execute("ROLLBACK")
                raise RuntimeError("A report is already queued or running in this browser session.")
            connection.execute("""
                INSERT INTO portal_report_jobs
                    (job_id, session_key_hash, module, report_date, status, percent, step,
                     stage, message, remark, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'queued', 0, 1, 'queued',
                        'Waiting for another portal task to finish...',
                        'Waiting for another portal task to finish...', ?, ?)
            """, (job_id, session_hash, module, report_date, now, now))
            connection.execute("COMMIT")

    def update_report_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        percent: int | None = None,
        step: int | None = None,
        stage: str | None = None,
        message: str | None = None,
        remark: str | None = None,
    ) -> None:
        fields: dict[str, Any] = {"updated_at": time.time()}
        for key, value in {
            "status": status,
            "percent": percent,
            "step": step,
            "stage": stage,
            "message": message,
            "remark": remark,
        }.items():
            if value is not None:
                fields[key] = value
        assignments = ", ".join(f"{name}=?" for name in fields)
        with closing(self._connect()) as connection:
            connection.execute(
                f"UPDATE portal_report_jobs SET {assignments} WHERE job_id=?",
                (*fields.values(), job_id),
            )

    def latest_report_progress(self, session_id: str) -> dict[str, Any] | None:
        session_hash = self._session_key_hash(session_id)
        with closing(self._connect()) as connection:
            row = connection.execute("""
                SELECT status, percent, step, stage, message, remark
                FROM portal_report_jobs
                WHERE session_key_hash=?
                ORDER BY created_at DESC, rowid DESC
                LIMIT 1
            """, (session_hash,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["active"] = result["status"] in {"queued", "running"}
        return result
