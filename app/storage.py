import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DB_PATH = Path(os.getenv("APP_DB_PATH", Path(__file__).resolve().parent.parent / "data" / "app.sqlite3"))
PBKDF2_ITERATIONS = 260_000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                gemini_api_key TEXT,
                pinecone_api_key TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS auth_tokens (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS connections (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                connection_string TEXT NOT NULL,
                db_dialect TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 0,
                added_at TEXT NOT NULL,
                UNIQUE(user_id, name),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                generated_sql TEXT,
                query_results_json TEXT,
                chart_config_json TEXT,
                response_mode TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        ).hex()
        return hmac.compare_digest(digest, expected)
    except Exception:
        return False


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "has_gemini_api_key": bool(user.get("gemini_api_key")),
        "has_pinecone_api_key": bool(user.get("pinecone_api_key")),
        "created_at": user["created_at"],
    }


def create_user(
    name: str,
    email: str,
    password: str,
    gemini_api_key: str | None = None,
    pinecone_api_key: str | None = None,
) -> dict[str, Any]:
    init_db()
    user = {
        "id": secrets.token_urlsafe(16),
        "name": name.strip(),
        "email": email.strip().lower(),
        "password_hash": hash_password(password),
        "gemini_api_key": gemini_api_key or None,
        "pinecone_api_key": pinecone_api_key or None,
        "created_at": _now(),
    }
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO users (id, name, email, password_hash, gemini_api_key, pinecone_api_key, created_at)
            VALUES (:id, :name, :email, :password_hash, :gemini_api_key, :pinecone_api_key, :created_at)
            """,
            user,
        )
    return user


def authenticate_user(email: str, password: str) -> dict[str, Any] | None:
    init_db()
    with _connect() as conn:
        user = _row_to_dict(
            conn.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
        )
    if not user or not verify_password(password, user["password_hash"]):
        return None
    return user


def create_auth_token(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    with _connect() as conn:
        conn.execute(
            "INSERT INTO auth_tokens (token_hash, user_id, created_at) VALUES (?, ?, ?)",
            (_hash_token(token), user_id, _now()),
        )
    return token


def get_user_by_token(token: str) -> dict[str, Any] | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT users.*
            FROM auth_tokens
            JOIN users ON users.id = auth_tokens.user_id
            WHERE auth_tokens.token_hash = ?
            """,
            (_hash_token(token),),
        ).fetchone()
    return _row_to_dict(row)


def update_user_keys(
    user_id: str,
    gemini_api_key: str | None = None,
    pinecone_api_key: str | None = None,
) -> dict[str, Any]:
    with _connect() as conn:
        conn.execute(
            """
            UPDATE users
            SET gemini_api_key = COALESCE(?, gemini_api_key),
                pinecone_api_key = COALESCE(?, pinecone_api_key)
            WHERE id = ?
            """,
            (gemini_api_key or None, pinecone_api_key or None, user_id),
        )
        user = _row_to_dict(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())
    if not user:
        raise ValueError("User not found")
    return user


def add_connection(user_id: str, name: str, connection_string: str, db_dialect: str) -> dict[str, Any]:
    init_db()
    conn_id = secrets.token_urlsafe(16)
    with _connect() as conn:
        has_active = conn.execute(
            "SELECT 1 FROM connections WHERE user_id = ? AND is_active = 1",
            (user_id,),
        ).fetchone()
        is_active = 0 if has_active else 1
        conn.execute(
            """
            INSERT INTO connections (id, user_id, name, connection_string, db_dialect, is_active, added_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, name) DO UPDATE SET
                connection_string = excluded.connection_string,
                db_dialect = excluded.db_dialect
            """,
            (conn_id, user_id, name, connection_string, db_dialect, is_active, _now()),
        )
        row = conn.execute(
            """
            SELECT name, connection_string, db_dialect, added_at, is_active
            FROM connections
            WHERE user_id = ? AND is_active = 1
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        return _row_to_dict(row) or {}


def list_connections(user_id: str) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT name, connection_string, db_dialect, added_at, is_active
            FROM connections
            WHERE user_id = ?
            ORDER BY added_at ASC
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_active_connection(user_id: str) -> dict[str, Any] | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT name, connection_string, db_dialect, added_at, is_active
            FROM connections
            WHERE user_id = ? AND is_active = 1
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    return _row_to_dict(row)


def switch_connection(user_id: str, name: str) -> bool:
    with _connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM connections WHERE user_id = ? AND name = ?",
            (user_id, name),
        ).fetchone()
        if not exists:
            return False
        conn.execute("UPDATE connections SET is_active = 0 WHERE user_id = ?", (user_id,))
        conn.execute(
            "UPDATE connections SET is_active = 1 WHERE user_id = ? AND name = ?",
            (user_id, name),
        )
    return True


def remove_connection(user_id: str, name: str) -> bool:
    with _connect() as conn:
        existing = conn.execute(
            "SELECT is_active FROM connections WHERE user_id = ? AND name = ?",
            (user_id, name),
        ).fetchone()
        if not existing:
            return False
        conn.execute("DELETE FROM connections WHERE user_id = ? AND name = ?", (user_id, name))
        if existing["is_active"]:
            next_conn = conn.execute(
                "SELECT id FROM connections WHERE user_id = ? ORDER BY added_at ASC LIMIT 1",
                (user_id,),
            ).fetchone()
            if next_conn:
                conn.execute("UPDATE connections SET is_active = 1 WHERE id = ?", (next_conn["id"],))
    return True


# Keep at most this many messages per user to stay within free-tier storage limits.
MAX_CHAT_MESSAGES_PER_USER = 50


def save_chat_message(
    user_id: str,
    role: str,
    content: str,
    generated_sql: str | None = None,
    query_results_json: str | None = None,
    chart_config_json: str | None = None,
    response_mode: str | None = None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO chat_messages
                (id, user_id, role, content, generated_sql, query_results_json, chart_config_json, response_mode, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                secrets.token_urlsafe(16),
                user_id,
                role,
                content,
                generated_sql,
                query_results_json,
                chart_config_json,
                response_mode,
                _now(),
            ),
        )
        # Auto-prune: keep only the newest N messages per user
        conn.execute(
            """
            DELETE FROM chat_messages
            WHERE user_id = ? AND id NOT IN (
                SELECT id FROM chat_messages
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            )
            """,
            (user_id, user_id, MAX_CHAT_MESSAGES_PER_USER),
        )


def get_chat_history(user_id: str, limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT role, content, generated_sql, query_results_json, chart_config_json, response_mode, created_at
            FROM chat_messages
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


init_db()
