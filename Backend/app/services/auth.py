import hmac
import os
import sqlite3
from datetime import datetime
from typing import Optional

from fastapi import HTTPException

from app.core.security import (
    create_access_token,
    get_jwt_secret,
    hash_password,
    user_public,
    verify_password,
)
from app.database import db_transaction, fetch_user_auth_by_email
from app.schemas.auth import (
    AdminBootstrapRequest,
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    UserPublic,
)


def register_citizen(payload: RegisterRequest) -> AuthResponse:
    get_jwt_secret()
    created_at = datetime.now().isoformat()
    password_hash = hash_password(payload.password)
    try:
        with db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users (name, email, password_hash, role, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (payload.name, payload.email, password_hash, "citizen", created_at),
            )
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=400,
            detail="An account with this email already exists",
        )

    user = UserPublic(
        id=user_id,
        name=payload.name,
        email=payload.email,
        role="citizen",
        created_at=created_at,
    )
    return AuthResponse(
        access_token=create_access_token(user.id, user.email, user.role),
        user=user,
    )


def authenticate_user(payload: LoginRequest) -> AuthResponse:
    get_jwt_secret()
    row = fetch_user_auth_by_email(payload.email)
    if not row or not verify_password(payload.password, row[3]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user = UserPublic(
        id=row[0],
        name=row[1],
        email=row[2],
        role=row[4],
        created_at=row[5],
    )
    return AuthResponse(
        access_token=create_access_token(user.id, user.email, user.role, row[6]),
        user=user,
    )


def bootstrap_first_admin(
    payload: AdminBootstrapRequest,
    bootstrap_token: Optional[str],
) -> AuthResponse:
    get_jwt_secret()
    configured_token = os.environ.get("ADMIN_BOOTSTRAP_TOKEN")
    if not configured_token or len(configured_token) < 32:
        raise HTTPException(status_code=404, detail="Administrator bootstrap is disabled")
    if not bootstrap_token or not hmac.compare_digest(bootstrap_token, configured_token):
        raise HTTPException(status_code=403, detail="Invalid bootstrap token")

    created_at = datetime.now().isoformat()
    try:
        with db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute("SELECT 1 FROM users WHERE role = 'admin' LIMIT 1")
            if cursor.fetchone() is not None:
                raise HTTPException(status_code=409, detail="An administrator already exists")
            cursor.execute(
                """
                INSERT INTO users (name, email, password_hash, role, created_at)
                VALUES (?, ?, ?, 'admin', ?)
                """,
                (payload.name, payload.email, hash_password(payload.password), created_at),
            )
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists",
        )
    user = UserPublic(
        id=user_id,
        name=payload.name,
        email=payload.email,
        role="admin",
        created_at=created_at,
    )
    return AuthResponse(
        access_token=create_access_token(user.id, user.email, user.role),
        user=user,
    )


def invalidate_user_tokens(user_id: int) -> None:
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET token_version = token_version + 1 WHERE id = ?",
            (user_id,),
        )
        if cursor.rowcount != 1:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
