import os
import uuid as uuidlib
from contextlib import contextmanager

import bcrypt
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

DATABASE_URL_ENV = "DATABASE_URL"


def _get_database_url():
    try:
        postgres_secrets = st.secrets.get("postgres", {})
    except StreamlitSecretNotFoundError:
        postgres_secrets = {}

    database_url = (
        postgres_secrets.get("database_url")
        or postgres_secrets.get("url")
        or os.getenv(DATABASE_URL_ENV)
    )
    if not database_url:
        raise RuntimeError(
            "PostgreSQL connection string is missing. Set [postgres] database_url "
            "in Streamlit secrets or the DATABASE_URL environment variable."
        )
    return database_url


def _ensure_schema(pool_):
    conn = pool_.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    uid TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    score INTEGER NOT NULL DEFAULT 0,
                    level INTEGER NOT NULL DEFAULT 1,
                    uses_hint INTEGER NOT NULL DEFAULT 0
                );
                """
            )
cur.execute(
                """
                CREATE TABLE IF NOT EXISTS oauth_states (
                    state TEXT PRIMARY KEY,
                    code_verifier TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    email TEXT PRIMARY KEY,
                    password_hash TEXT,
                    google_sub TEXT,
                    uid TEXT NOT NULL,
                    codename TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS oauth_states (
                    state TEXT PRIMARY KEY,
                    code_verifier TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                ALTER TABLE oauth_states
                ADD COLUMN IF NOT EXISTS code_verifier TEXT;
                """
            )
        conn.commit()
    finally:
        pool_.putconn(conn)


@st.cache_resource
def _get_pool():
    connection_pool = pool.SimpleConnectionPool(1, 10, dsn=_get_database_url())
    _ensure_schema(connection_pool)
    return connection_pool


@contextmanager
def _cursor(commit=False):
    connection_pool = _get_pool()
    conn = connection_pool.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        connection_pool.putconn(conn)


def _upsert_leaderboard(cur, username, score):
    cur.execute(
        """
        INSERT INTO leaderboard (username, score)
        VALUES (%s, %s)
        ON CONFLICT (username) DO UPDATE SET score = EXCLUDED.score;
        """,
        (username, score),
    )


# ---------- DATABASE FUNCTIONS ----------

def create_user(uid, username):
    """Create user account if not exists"""
    with _cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO users (uid, username, score, level, uses_hint)
            VALUES (%s, %s, 0, 1, 0)
            ON CONFLICT (uid) DO NOTHING;
            """,
            (uid, username),
        )


def get_user(uid):
    with _cursor() as cur:
        cur.execute(
            "SELECT username, score, level, uses_hint FROM users WHERE uid = %s;",
            (uid,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def update_score(uid, new_score):
    with _cursor(commit=True) as cur:
        cur.execute(
            "UPDATE users SET score = %s WHERE uid = %s RETURNING username;",
            (new_score, uid),
        )
        row = cur.fetchone()
        if row:
            _upsert_leaderboard(cur, row["username"], new_score)


def update_level(uid, new_level):
    with _cursor(commit=True) as cur:
        cur.execute("UPDATE users SET level = %s WHERE uid = %s;", (new_level, uid))


def increment_hint_usage(uid):
    with _cursor(commit=True) as cur:
        cur.execute(
            "UPDATE users SET uses_hint = uses_hint + 1 WHERE uid = %s;",
            (uid,),
        )


def update_leaderboard(username, score):
    """Leaderboard sorted by score"""
    with _cursor(commit=True) as cur:
        _upsert_leaderboard(cur, username, score)


def save_progress(uid, username, level, score):
    with _cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO users (uid, username, level, score)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (uid) DO UPDATE SET
                username = EXCLUDED.username,
                level = EXCLUDED.level,
                score = EXCLUDED.score;
            """,
            (uid, username, level, score),
        )


def get_progress(uid):
    return get_user(uid)


# ---------- ACCOUNT / AUTH FUNCTIONS ----------

def uid_for_email(email):
    """Stable user id derived from the account email."""
    return str(uuidlib.uuid5(uuidlib.NAMESPACE_DNS, email.lower().strip()))


def _hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _check_password(password, password_hash):
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except ValueError:
        return False


def create_account(email, password):
    """Register a new account. Returns True if created, False if email exists."""
    uid = uid_for_email(email)
    with _cursor(commit=True) as cur:
        cur.execute("SELECT 1 FROM accounts WHERE email = %s;", (email,))
        if cur.fetchone():
            return False
        cur.execute(
            """
            INSERT INTO accounts (email, password_hash, uid, codename)
            VALUES (%s, %s, %s, NULL);
            """,
            (email, _hash_password(password), uid),
        )
        return True


def get_account(email):
    with _cursor() as cur:
        cur.execute(
            "SELECT email, password_hash, google_sub, uid, codename "
            "FROM accounts WHERE email = %s;",
            (email,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def verify_account(email, password):
    """Return the account dict if credentials are valid, else None."""
    account = get_account(email)
    if not account or not account.get("password_hash"):
        return None
    if not _check_password(password, account["password_hash"]):
        return None
    return account


def set_codename(email, codename):
    with _cursor(commit=True) as cur:
        cur.execute(
            "UPDATE accounts SET codename = %s WHERE email = %s;",
            (codename, email),
        )


def upsert_google_account(email, google_sub):
    """Create or link an account for a Google sign-in."""
    uid = uid_for_email(email)
    with _cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO accounts (email, google_sub, uid, codename)
            VALUES (%s, %s, %s, NULL)
            ON CONFLICT (email) DO UPDATE SET google_sub = EXCLUDED.google_sub;
            """,
            (email, google_sub, uid),
        )
    return get_account(email)


# ---------- OAUTH STATE HELPERS ----------

def store_oauth_state(state, code_verifier):
    """Persist OAuth state and its PKCE verifier through the browser redirect."""
    if not state:
        return
    try:
        with _cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM oauth_states WHERE created_at < NOW() - INTERVAL '15 minutes';"
            )
            cur.execute(
                """
                INSERT INTO oauth_states (state, code_verifier)
                VALUES (%s, %s)
                ON CONFLICT (state) DO UPDATE
                SET code_verifier = EXCLUDED.code_verifier;
                """,
                (state, code_verifier),
            )
    except Exception:
        # Best-effort: if the DB is briefly unavailable, fall back to the
        # session-only state check rather than crashing the login page.
        pass


def consume_oauth_state(state):
    """Consume OAuth state and return its PKCE verifier, if it was persisted."""
    with _cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM oauth_states WHERE state = %s RETURNING state, code_verifier;",
            (state,),
        )
        return cur.fetchone()
