from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import EMAIL_PATTERN, JWT_EXPIRE_HOURS


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Name must be at least 2 characters")
        if len(value) > 100:
            raise ValueError("Name is too long")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_PATTERN.match(value):
            raise ValueError("Enter a valid email address")
        if len(value) > 255:
            raise ValueError("Email is too long")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be no more than 72 UTF-8 bytes")
        return value


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_PATTERN.match(value):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not value:
            raise ValueError("Password is required")
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be no more than 72 UTF-8 bytes")
        return value


class UserPublic(BaseModel):
    id: int
    name: str
    email: str
    role: str
    created_at: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = JWT_EXPIRE_HOURS * 3600
    user: UserPublic


class AdminBootstrapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2 or len(value) > 100:
            raise ValueError("Name must be between 2 and 100 characters")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_PATTERN.match(value) or len(value) > 255:
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 12 or len(value) > 128:
            raise ValueError("Administrator password must be at least 12 characters")
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be no more than 72 UTF-8 bytes")
        return value


class OfficerCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2 or len(value) > 100:
            raise ValueError("Name must be between 2 and 100 characters")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_PATTERN.match(value) or len(value) > 255:
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8 or len(value) > 128:
            raise ValueError("Password must be between 8 and 128 characters")
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be no more than 72 UTF-8 bytes")
        return value
