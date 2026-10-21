import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from typing import Optional

from app.core.config import JWT_ALGORITHM, JWT_EXPIRE_HOURS
from app.database import fetch_user_by_id


bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def get_jwt_secret() -> str:
    import os

    secret = os.environ.get("JWT_SECRET", "")
    if len(secret) < 32:
        raise HTTPException(
            status_code=503,
            detail="Authentication is unavailable until a JWT_SECRET of at least 32 characters is configured",
        )
    return secret


def create_access_token(user_id: int, email: str, role: str, token_version: int = 0) -> str:
    payload = {
        "sub": str(user_id),
        "sv": token_version,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def user_public(row) -> dict:
    return {
        "id": row[0],
        "name": row[1],
        "email": row[2],
        "role": row[3],
        "created_at": row[4],
    }


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(
            credentials.credentials,
            get_jwt_secret(),
            algorithms=[JWT_ALGORITHM],
        )
        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject.isdecimal():
            raise ValueError("Invalid subject")
        user_id = int(subject)
    except (jwt.InvalidTokenError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    row = fetch_user_by_id(user_id)
    if not row or payload.get("sv", 0) != row[5]:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user_public(row)


def require_roles(*allowed_roles: str):
    role_labels = {
        "citizen": "Citizen",
        "officer": "Officer",
        "admin": "Administrator",
    }
    required_access = " or ".join(
        f"{role_labels.get(role, role.title())} access" for role in allowed_roles
    )

    def role_dependency(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"{required_access} required",
            )
        return current_user

    return role_dependency


require_citizen = require_roles("citizen")
require_admin = require_roles("admin")
require_officer = require_roles("officer")
