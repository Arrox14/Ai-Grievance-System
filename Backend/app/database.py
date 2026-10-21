import os
import sqlite3
from contextlib import contextmanager

from app.core import config


def get_db_path():
    return os.path.join(config.BASE_DIR, "complaints.db")


def connect_db():
    connection = sqlite3.connect(get_db_path(), timeout=10)
    connection.execute("PRAGMA foreign_keys = ON")
    if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        connection.close()
        raise RuntimeError("SQLite foreign-key enforcement could not be enabled")
    return connection


@contextmanager
def db_connection():
    connection = connect_db()
    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@contextmanager
def db_transaction():
    with db_connection() as connection:
        yield connection
        connection.commit()


def fetch_user_by_id(user_id: int):
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, email, role, created_at, token_version FROM users WHERE id = ?",
            (user_id,),
        )
        return cursor.fetchone()


def fetch_user_auth_by_email(email: str):
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, name, email, password_hash, role, created_at, token_version
            FROM users WHERE email = ?
            """,
            (email,),
        )
        return cursor.fetchone()
