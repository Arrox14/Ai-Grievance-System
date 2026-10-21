from typing import Optional

from fastapi import APIRouter, Depends, Header

from app.core.security import get_current_user
from app.schemas.auth import (
    AdminBootstrapRequest,
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    UserPublic,
)
from app.services.auth import (
    authenticate_user,
    bootstrap_first_admin,
    invalidate_user_tokens,
    register_citizen,
)


router = APIRouter()


@router.post("/admin/bootstrap", response_model=AuthResponse)
def bootstrap_admin(
    payload: AdminBootstrapRequest,
    bootstrap_token: Optional[str] = Header(default=None, alias="X-Admin-Bootstrap-Token"),
):
    return bootstrap_first_admin(payload, bootstrap_token)


@router.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest):
    return register_citizen(payload)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest):
    return authenticate_user(payload)


@router.post("/logout")
def logout(current_user: dict = Depends(get_current_user)):
    invalidate_user_tokens(current_user["id"])
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserPublic)
def me(current_user: dict = Depends(get_current_user)):
    return current_user
