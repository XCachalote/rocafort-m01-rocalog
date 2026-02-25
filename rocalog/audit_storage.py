from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

import pyotp

DB_PATH = Path("data/audit_app.db")


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 390000)
    return f"{salt.hex()}:{digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split(":", 1)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 390000)
    return hmac.compare_digest(digest.hex(), digest_hex)


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                username TEXT UNIQUE NOT NULL,
                document_id TEXT NOT NULL,
                role TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                totp_secret TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS engagements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                tax_identifier TEXT NOT NULL,
                full_address TEXT NOT NULL,
                contact_person TEXT NOT NULL,
                auditor_name TEXT NOT NULL,
                auditor_document_id TEXT NOT NULL,
                audit_date TEXT NOT NULL,
                scope_text TEXT NOT NULL,
                liability_clause_text TEXT NOT NULL,
                remote_access_consent_text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'in_progress',
                created_by INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(created_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS controls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                engagement_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                code TEXT NOT NULL,
                title TEXT NOT NULL,
                criticality_weight REAL NOT NULL,
                max_score REAL NOT NULL DEFAULT 100,
                compliance_value REAL NOT NULL,
                evidence_text TEXT NOT NULL,
                risk_observation TEXT NOT NULL,
                entered_by INTEGER NOT NULL,
                entered_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(engagement_id, code),
                FOREIGN KEY(engagement_id) REFERENCES engagements(id),
                FOREIGN KEY(entered_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS report_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                engagement_id INTEGER NOT NULL,
                version_number INTEGER NOT NULL,
                pdf_path TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                created_by INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(engagement_id, version_number),
                FOREIGN KEY(engagement_id) REFERENCES engagements(id)
            );

            CREATE TABLE IF NOT EXISTS signatures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                engagement_id INTEGER NOT NULL,
                signer_type TEXT NOT NULL,
                signer_name TEXT NOT NULL,
                signer_document_id TEXT NOT NULL,
                signature_text TEXT NOT NULL,
                signed_at TEXT NOT NULL,
                FOREIGN KEY(engagement_id) REFERENCES engagements(id)
            );

            CREATE TABLE IF NOT EXISTS access_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS event_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_time TEXT NOT NULL,
                actor_user_id INTEGER NOT NULL,
                entity TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                operation TEXT NOT NULL,
                before_json TEXT,
                after_json TEXT,
                prev_event_hash TEXT,
                event_hash TEXT NOT NULL,
                FOREIGN KEY(actor_user_id) REFERENCES users(id)
            );
            """
        )

        existing_admin = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
        if not existing_admin:
            totp_secret = pyotp.random_base32()
            conn.execute(
                """
                INSERT INTO users(full_name, username, document_id, role, password_hash, totp_secret, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Administrador",
                    "admin",
                    "ADMIN-ID",
                    "admin",
                    hash_password("admin1234"),
                    totp_secret,
                    utc_now_iso(),
                ),
            )


def log_event(conn: sqlite3.Connection, user_id: int, entity: str, entity_id: str, operation: str, before_json: str = "", after_json: str = "") -> None:
    prev = conn.execute("SELECT event_hash FROM event_audit_log ORDER BY id DESC LIMIT 1").fetchone()
    prev_hash = prev["event_hash"] if prev else ""
    payload = f"{utc_now_iso()}|{user_id}|{entity}|{entity_id}|{operation}|{before_json}|{after_json}|{prev_hash}".encode("utf-8")
    event_hash = hashlib.sha256(payload).hexdigest()
    conn.execute(
        """
        INSERT INTO event_audit_log(event_time, actor_user_id, entity, entity_id, operation, before_json, after_json, prev_event_hash, event_hash)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (utc_now_iso(), user_id, entity, entity_id, operation, before_json, after_json, prev_hash, event_hash),
    )


def create_session(conn: sqlite3.Connection, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    expires = now + timedelta(hours=8)
    conn.execute(
        "INSERT INTO sessions(token, user_id, expires_at, created_at) VALUES(?,?,?,?)",
        (token, user_id, expires.isoformat(), now.isoformat()),
    )
    return token


def get_user_by_token(conn: sqlite3.Connection, token: str) -> sqlite3.Row | None:
    row = conn.execute(
        """
        SELECT u.* FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token = ? AND s.expires_at > ?
        """,
        (token, utc_now_iso()),
    ).fetchone()
    return row


def verify_totp(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def access_log(conn: sqlite3.Connection, user_id: int, action: str, resource_type: str, resource_id: str) -> None:
    conn.execute(
        "INSERT INTO access_logs(user_id, action, resource_type, resource_id, created_at) VALUES(?,?,?,?,?)",
        (user_id, action, resource_type, resource_id, utc_now_iso()),
    )


def as_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}
