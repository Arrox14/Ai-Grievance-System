from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Depends, Query, Header, Path as PathParam
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Annotated, Literal, Optional, List
import pickle
import os
import re
import hmac
import logging
import unicodedata
import base64
import io
import json
import zipfile
import sqlite3
import mimetypes
import tempfile
from datetime import date, datetime, timedelta, timezone
from importlib.metadata import version as package_version
import uuid
import bcrypt
import jwt

logger = logging.getLogger(__name__)

from app.core.config import (
    APP_DATA_DIR,
    BASE_DIR,
    DATABASE_DIR,
    EMAIL_PATTERN,
    JWT_ALGORITHM,
    JWT_EXPIRE_HOURS,
    UPLOADS_DIR,
    load_backend_environment,
)
from app.core.errors import install_error_handlers
from app.core import security as auth_security
from app.core.security import (
    create_access_token,
    get_current_user,
    get_jwt_secret,
    hash_password,
    require_admin,
    require_citizen,
    require_officer,
    require_roles,
    verify_password,
)
from app.database import (
    connect_db,
    db_connection,
    db_transaction,
    fetch_user_auth_by_email as db_fetch_user_auth_by_email,
    fetch_user_by_id as db_fetch_user_by_id,
    get_db_path as db_get_db_path,
)
from app.migrations.runner import require_current_schema
from app.routes.auth import router as auth_router
from app.schemas.auth import AdminBootstrapRequest, OfficerCreateRequest
from app.services.complaints import (
    assign_complaint as persist_complaint_assignment,
    transition_complaint_status,
    validate_admin_status_transition,
)
from app.services.files import managed_file_path, save_upload
from app.services.vision import (
    IMAGE_EXTENSIONS,
    LIVE_FRAME_MAX_BYTES,
    LIVE_FRAME_MAX_HEIGHT,
    LIVE_FRAME_MAX_WIDTH,
    VIDEO_EXTENSIONS,
    analyze_video as analyze_video_file,
    decode_image_bytes,
    detect_image,
    encode_annotated_image,
    live_inference_limiter,
    load_yolo_model,
    read_image,
)
from starlette.concurrency import run_in_threadpool

app = FastAPI(title="Public Grievance Intelligence System API")
install_error_handlers(app)
PositiveId = Annotated[int, PathParam(gt=0)]

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(APP_DATA_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
ANNOTATED_DIR = os.path.join(UPLOADS_DIR, "annotated")
os.makedirs(ANNOTATED_DIR, exist_ok=True)
ANNOTATED_VIDEO_DIR = os.path.join(ANNOTATED_DIR, "videos")
os.makedirs(ANNOTATED_VIDEO_DIR, exist_ok=True)
os.makedirs(DATABASE_DIR, exist_ok=True)
load_backend_environment()

def init_db():
    require_current_schema(get_db_path())

@app.on_event("startup")
def verify_database_schema():
    init_db()

app.include_router(auth_router)

# Load text-classification models independently from object detection.
try:
    model_category = pickle.load(open(os.path.join(BASE_DIR, "category_model.pkl"), "rb"))
    model_priority = pickle.load(open(os.path.join(BASE_DIR, "priority_model.pkl"), "rb"))
    vectorizer = pickle.load(open(os.path.join(BASE_DIR, "vectorizer.pkl"), "rb"))
    le_category = pickle.load(open(os.path.join(BASE_DIR, "le_category.pkl"), "rb"))
    le_priority = pickle.load(open(os.path.join(BASE_DIR, "le_priority.pkl"), "rb"))
except Exception:
    logger.exception("Text classification model initialization failed")
    model_category = None
    model_priority = None
    vectorizer = None
    le_category = None
    le_priority = None

YOLO_WEIGHTS_PATH = os.path.join(BASE_DIR, "yolov8n.pt")
YOLO_MODEL_NAME = os.path.splitext(os.path.basename(YOLO_WEIGHTS_PATH))[0]
YOLO_MODEL_VERSION = f"ultralytics-{package_version('ultralytics')}"
try:
    yolo_model = load_yolo_model(YOLO_WEIGHTS_PATH)
except Exception:
    logger.exception("YOLO model initialization failed")
    yolo_model = None


def detect_objects(path):
    if not yolo_model:
        return []
    if os.path.splitext(path)[1].lower() not in IMAGE_EXTENSIONS:
        return []
    try:
        image = read_image(path)
        detections, _ = detect_image(yolo_model, image)
        return list(dict.fromkeys(item["class_name"] for item in detections))
    except Exception:
        logger.exception("Object detection failed")
        return []

# Pydantic models
class ComplaintRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=10000)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)

class ComplaintResponse(BaseModel):
    id: str
    text: str
    category: str
    priority: str
    file_path: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    timestamp: str
    status: str
    assigned_officer_id: Optional[int] = None
    assigned_officer: Optional[str] = None
    assigned_at: Optional[str] = None
    resolution_date: Optional[str] = None
    resolution_remarks: Optional[str] = None
    resolution_findings: Optional[str] = None
    resolution_officer: Optional[str] = None
    resolution_submitted_at: Optional[str] = None
    resolution_attachment_name: Optional[str] = None
    resolution_attachment_url: Optional[str] = None
    department_id: Optional[int] = None
    department: Optional[str] = None


class ComplaintHistoryItem(BaseModel):
    id: str
    timestamp: str
    category: str
    status: str


class ComplaintHistoryPage(BaseModel):
    items: List[ComplaintHistoryItem]
    total: int
    limit: int
    offset: int


class ComplaintStatusEvent(BaseModel):
    previous_status: Optional[str] = None
    status: str
    changed_at: str
    actor_name: str
    remarks: Optional[str]


class ComplaintResolution(BaseModel):
    date: str
    remarks: Optional[str]
    findings: Optional[str] = None
    submitted_at: Optional[str] = None
    officer_name: Optional[str] = None
    attachment_name: Optional[str] = None
    attachment_url: Optional[str] = None
    completed_by: Optional[str] = None
    completed_at: Optional[str] = None
    administrator_remarks: Optional[str] = None


class ResolutionSubmissionItem(BaseModel):
    id: int
    complaint_id: str
    officer_name: str
    findings: str
    remarks: str
    resolution_date: str
    attachment_name: str
    content_type: str
    file_size: int
    submitted_at: str
    attachment_url: str
    review_status: str = "pending_review"
    reviewed_at: Optional[str] = None
    review_remarks: Optional[str] = None
    reviewed_by_name: Optional[str] = None


class ResolutionReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    remarks: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("remarks")
    @classmethod
    def validate_remarks(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if len(value) > 2000:
            raise ValueError("Review remarks must be 2000 characters or fewer")
        return value or None


class InvestigationNote(BaseModel):
    id: int
    author_name: str
    note_type: str
    note: str
    created_at: str


class ComplaintDetails(BaseModel):
    id: str
    text: str
    category: str
    priority: str
    timestamp: str
    evidence_url: Optional[str]
    evidence_type: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    status: str
    history: List[ComplaintStatusEvent]
    resolution: Optional[ComplaintResolution]
    citizen_messages: List[InvestigationNote] = Field(default_factory=list)


class NotificationItem(BaseModel):
    id: int
    complaint_id: Optional[str]
    notification_type: str
    title: str
    message: str
    created_at: str
    is_read: bool


class NotificationList(BaseModel):
    notifications: List[NotificationItem]
    unread_count: int


class ComplaintAssignmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    officer_id: int = Field(gt=0)


class OfficerComplaintItem(BaseModel):
    id: str
    description: str
    category: str
    priority: str
    submitted_at: str
    assigned_at: Optional[str] = None
    status: str


class OfficerComplaintDetails(BaseModel):
    id: str
    text: str
    category: str
    priority: str
    timestamp: str
    evidence_url: Optional[str]
    evidence_type: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    assigned_at: Optional[str]
    assigned_officer: Optional[str]
    status: str
    history: List[ComplaintStatusEvent]
    notes: List[InvestigationNote] = Field(default_factory=list)
    resolution_submission: Optional[ResolutionSubmissionItem] = None


class InvestigationNoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note_type: Literal["internal", "citizen_visible"]
    note: str = Field(min_length=1, max_length=5000)

    @field_validator("note_type")
    @classmethod
    def validate_note_type(cls, value: str) -> str:
        if value not in ("internal", "citizen_visible"):
            raise ValueError("Note type must be internal or citizen_visible")
        return value

    @field_validator("note")
    @classmethod
    def validate_note(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Note cannot be empty")
        if len(value) > 5000:
            raise ValueError("Note must be 5000 characters or fewer")
        return value


class OfficerStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["In Progress"]
    remarks: Optional[str] = Field(default=None, max_length=2000)
    resolution_date: Optional[date] = None

    @field_validator("remarks")
    @classmethod
    def validate_remarks(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if len(value) > 2000:
            raise ValueError("Remarks must be 2000 characters or fewer")
        return value or None


class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["Pending", "In Progress", "Resolved"]
    remarks: Optional[str] = Field(default=None, max_length=2000)
    resolution_date: Optional[date] = None

    @field_validator("remarks")
    @classmethod
    def validate_remarks(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if len(value) > 2000:
            raise ValueError("Remarks must be 2000 characters or fewer")
        return value or None

# Authentication
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
bearer_scheme = HTTPBearer(auto_error=False)


def get_db_path():
    return db_get_db_path()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def get_jwt_secret() -> str:
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


def fetch_user_by_id(user_id: int):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, email, role, created_at, token_version FROM users WHERE id = ?",
        (user_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return row


def fetch_user_auth_by_email(email: str):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, name, email, password_hash, role, created_at, token_version
        FROM users WHERE email = ?
        """,
        (email,),
    )
    row = cursor.fetchone()
    conn.close()
    return row


def user_public(row) -> dict:
    return {
        "id": row[0],
        "name": row[1],
        "email": row[2],
        "role": row[3],
        "created_at": row[4],
    }


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    email: str
    password: str

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

    email: str
    password: str

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
    if not row:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if payload.get("sv", 0) != row[5]:
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


# Routes
def bootstrap_admin(
    payload: AdminBootstrapRequest,
    bootstrap_token: Optional[str] = Header(default=None, alias="X-Admin-Bootstrap-Token"),
):
    get_jwt_secret()
    configured_token = os.environ.get("ADMIN_BOOTSTRAP_TOKEN")
    if not configured_token or len(configured_token) < 32:
        raise HTTPException(status_code=404, detail="Administrator bootstrap is disabled")
    if not bootstrap_token or not hmac.compare_digest(bootstrap_token, configured_token):
        raise HTTPException(status_code=403, detail="Invalid bootstrap token")

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("BEGIN IMMEDIATE")
    cursor.execute("SELECT 1 FROM users WHERE role = 'admin' LIMIT 1")
    if cursor.fetchone() is not None:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=409, detail="An administrator already exists")

    created_at = datetime.now().isoformat()
    try:
        cursor.execute(
            """
            INSERT INTO users (name, email, password_hash, role, created_at)
            VALUES (?, ?, ?, 'admin', ?)
            """,
            (payload.name, payload.email, hash_password(payload.password), created_at),
        )
        user_id = cursor.lastrowid
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    conn.close()
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


@app.get("/")
def home():
    return {"message": "AI Grievance System Running", "version": "1.0.0"}


def register(payload: RegisterRequest):
    get_jwt_secret()
    created_at = datetime.now().isoformat()
    password_hash = hash_password(payload.password)
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO users (name, email, password_hash, role, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (payload.name, payload.email, password_hash, "citizen", created_at),
        )
        conn.commit()
        user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    conn.close()

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


def login(payload: LoginRequest):
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


def logout(current_user: dict = Depends(get_current_user)):
    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET token_version = token_version + 1 WHERE id = ?",
            (current_user["id"],),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        conn.commit()
    finally:
        conn.close()
    return {"message": "Successfully logged out"}


def me(current_user: dict = Depends(get_current_user)):
    return current_user

# Keep legacy imports on the shared modular authentication implementation.
create_access_token = auth_security.create_access_token
fetch_user_auth_by_email = db_fetch_user_auth_by_email
fetch_user_by_id = db_fetch_user_by_id
get_current_user = auth_security.get_current_user
get_jwt_secret = auth_security.get_jwt_secret
hash_password = auth_security.hash_password
require_admin = auth_security.require_admin
require_citizen = auth_security.require_citizen
require_officer = auth_security.require_officer
require_roles = auth_security.require_roles
user_public = auth_security.user_public
verify_password = auth_security.verify_password

@app.post("/predict")
def predict(text: str = Query(..., min_length=1, max_length=10000)):
    if not all([model_category, model_priority, vectorizer, le_category, le_priority]):
        raise HTTPException(status_code=500, detail="ML models not loaded")
    
    vec = vectorizer.transform([text])
    category = le_category.inverse_transform(model_category.predict(vec))[0]
    priority = le_priority.inverse_transform(model_priority.predict(vec))[0]
    
    return {"category": category, "priority": priority}

@app.post("/upload")
async def upload(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_citizen),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    filename = unicodedata.normalize("NFC", file.filename.strip())
    if (
        not filename
        or len(filename) > 255
        or "/" in filename
        or "\\" in filename
        or any(unicodedata.category(char).startswith("C") for char in filename)
    ):
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path, expected_type, file_size = await save_upload(file, filename, UPLOADS_DIR)
    try:
        with db_transaction() as conn:
            conn.execute(
                """
                INSERT INTO uploaded_files (file_path, owner_id, created_at)
                VALUES (?, ?, ?)
                """,
                (file_path, current_user["id"], datetime.now(timezone.utc).isoformat()),
            )
        return {
            "message": "File uploaded successfully",
            "filename": filename,
            "file_path": file_path,
            "content_type": expected_type,
            "file_size": file_size,
        }
    except Exception:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise

@app.post("/analyze-image")
async def analyze_image(
    file_path: str = Query(..., min_length=1, max_length=4096),
    confidence: float = Query(default=0.5, ge=0.05, le=0.95),
    iou: float = Query(default=0.45, ge=0.1, le=0.95),
    current_user: dict = Depends(require_citizen),
):
    absolute_path = os.path.abspath(file_path)
    with db_connection() as conn:
        owned_upload = conn.execute(
            "SELECT 1 FROM uploaded_files WHERE file_path = ? AND owner_id = ?",
            (absolute_path, current_user["id"]),
        ).fetchone()
        owned_complaint_file = conn.execute(
            "SELECT id FROM complaints WHERE file = ? AND user_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (absolute_path, current_user["id"]),
        ).fetchone()
    resolved_path = managed_file_path(
        absolute_path,
        UPLOADS_DIR,
        os.path.join(BASE_DIR, "uploads"),
    )
    if resolved_path is None or (owned_upload is None and owned_complaint_file is None):
        raise HTTPException(status_code=404, detail="File not found")
    if not yolo_model:
        raise HTTPException(status_code=503, detail="YOLO model not loaded")

    try:
        image = read_image(resolved_path)
        detections, annotated_image = detect_image(
            yolo_model,
            image,
            confidence=confidence,
            iou=iou,
        )
        annotated_bytes = encode_annotated_image(annotated_image)
        analysis_id = uuid.uuid4()
        annotated_path = os.path.abspath(
            os.path.join(ANNOTATED_DIR, f"{analysis_id.hex}.jpg")
        )
        descriptor, temporary_path = tempfile.mkstemp(
            prefix=".analysis-", suffix=".tmp", dir=ANNOTATED_DIR
        )
        try:
            with os.fdopen(descriptor, "wb") as output_file:
                output_file.write(annotated_bytes)
                output_file.flush()
                os.fsync(output_file.fileno())
            os.replace(temporary_path, annotated_path)
            analyzed_at = datetime.now(timezone.utc).isoformat()
            with db_transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO uploaded_files (file_path, owner_id, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (
                        annotated_path,
                        current_user["id"],
                        analyzed_at,
                    ),
                )
                if owned_complaint_file is not None:
                    analysis_metadata = {
                        "detection_count": len(detections),
                        "confidence_scores": [
                            item["confidence"] for item in detections
                        ],
                        "image_dimensions": {
                            "width": int(image.shape[1]),
                            "height": int(image.shape[0]),
                        },
                        "detections": detections,
                        "annotated_image_id": analysis_id.hex,
                        "confidence_threshold": confidence,
                        "iou_threshold": iou,
                    }
                    conn.execute(
                        """
                        INSERT INTO ai_analysis_results
                            (complaint_id, analysis_type, model_name, model_version,
                             result_json, confidence, created_at)
                        VALUES (?, 'image_object_detection', ?, ?, ?, NULL, ?)
                        """,
                        (
                            owned_complaint_file[0],
                            YOLO_MODEL_NAME,
                            YOLO_MODEL_VERSION,
                            json.dumps(analysis_metadata, ensure_ascii=False),
                            analyzed_at,
                        ),
                    )
        except Exception:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)
            if os.path.exists(annotated_path):
                os.remove(annotated_path)
            raise

        height, width = image.shape[:2]
        return {
            "complaint_id": (
                owned_complaint_file[0]
                if owned_complaint_file is not None
                else None
            ),
            "analysis_persisted": owned_complaint_file is not None,
            "detections": detections,
            "image_dimensions": {"width": width, "height": height},
            "annotated_result": {
                "id": analysis_id.hex,
                "download_url": f"/analysis-images/annotated/{analysis_id.hex}",
            },
            "detected_objects": [
                {"object": item["class_name"], "confidence": item["confidence"]}
                for item in detections
            ],
            "total_objects": len(detections),
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Image analysis failed")
        raise HTTPException(status_code=500, detail="Image analysis failed")


@app.post("/live-detect")
async def live_detect(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_citizen),
):
    if file.content_type != "image/jpeg":
        raise HTTPException(status_code=415, detail="Live frames must be JPEG images")
    if not yolo_model:
        raise HTTPException(status_code=503, detail="YOLO model not loaded")

    contents = await file.read(LIVE_FRAME_MAX_BYTES + 1)
    if len(contents) > LIVE_FRAME_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Live frame must be 512 KB or smaller")
    image = decode_image_bytes(
        contents,
        ".jpg",
        LIVE_FRAME_MAX_BYTES,
        max_width=LIVE_FRAME_MAX_WIDTH,
        max_height=LIVE_FRAME_MAX_HEIGHT,
    )
    if not live_inference_limiter.acquire(current_user["id"]):
        raise HTTPException(
            status_code=429,
            detail="Live inference is limited to one frame per second",
            headers={"Retry-After": "1"},
        )
    try:
        detections, annotated_image = await run_in_threadpool(
            detect_image,
            yolo_model,
            image,
            0.5,
            0.45,
        )
        annotated_bytes = encode_annotated_image(annotated_image)
    except Exception as error:
        logger.exception("Live camera inference failed")
        raise HTTPException(status_code=500, detail="Live inference failed") from error
    finally:
        live_inference_limiter.release()

    height, width = image.shape[:2]
    return {
        "detections": detections,
        "image_dimensions": {"width": width, "height": height},
        "annotated_frame": (
            "data:image/jpeg;base64,"
            + base64.b64encode(annotated_bytes).decode("ascii")
        ),
    }


@app.post("/analyze-video")
def analyze_video(
    file_path: str = Query(..., min_length=1, max_length=4096),
    confidence: float = Query(default=0.5, ge=0.05, le=0.95),
    iou: float = Query(default=0.45, ge=0.1, le=0.95),
    frame_interval: int = Query(default=30, ge=1, le=600),
    include_frame_detections: bool = Query(default=False),
    annotate_video: bool = Query(default=False),
    current_user: dict = Depends(require_citizen),
):
    absolute_path = os.path.abspath(file_path)
    with db_connection() as conn:
        owned_upload = conn.execute(
            "SELECT 1 FROM uploaded_files WHERE file_path = ? AND owner_id = ?",
            (absolute_path, current_user["id"]),
        ).fetchone()
        owned_complaint_file = conn.execute(
            "SELECT id FROM complaints WHERE file = ? AND user_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (absolute_path, current_user["id"]),
        ).fetchone()
    resolved_path = managed_file_path(
        absolute_path,
        UPLOADS_DIR,
        os.path.join(BASE_DIR, "uploads"),
    )
    if (
        resolved_path is None
        or os.path.splitext(resolved_path)[1].lower() not in VIDEO_EXTENSIONS
        or (owned_upload is None and owned_complaint_file is None)
    ):
        raise HTTPException(status_code=404, detail="Video file not found")
    if not yolo_model:
        raise HTTPException(status_code=503, detail="YOLO model not loaded")

    analysis_id = uuid.uuid4()
    annotated_id = uuid.uuid4() if annotate_video else None
    annotated_path = (
        os.path.abspath(
            os.path.join(ANNOTATED_VIDEO_DIR, f"{annotated_id.hex}.mp4")
        )
        if annotated_id
        else None
    )
    try:
        analysis = analyze_video_file(
            resolved_path,
            yolo_model,
            confidence=confidence,
            iou=iou,
            frame_interval=frame_interval,
            include_frame_detections=include_frame_detections,
            annotated_output_path=annotated_path,
        )
        analyzed_at = datetime.now(timezone.utc).isoformat()
        metadata = {
            "video_analysis_id": analysis_id.hex,
            "detection_count": analysis["total_detections"],
            "detection_counts": analysis["detection_counts"],
            "confidence_scores": analysis["confidence_scores"],
            "duration_seconds": analysis["duration_seconds"],
            "frames_processed": analysis["frames_processed"],
            "frames_sampled": analysis["frames_sampled"],
            "frame_interval": frame_interval,
            "confidence_threshold": confidence,
            "iou_threshold": iou,
        }
        if include_frame_detections:
            metadata["frame_detections"] = analysis["frame_detections"]
        if annotated_id:
            metadata["annotated_video_id"] = annotated_id.hex

        try:
            with db_transaction() as conn:
                if annotated_path:
                    conn.execute(
                        """
                        INSERT INTO uploaded_files (file_path, owner_id, created_at)
                        VALUES (?, ?, ?)
                        """,
                        (annotated_path, current_user["id"], analyzed_at),
                    )
                if owned_complaint_file is not None:
                    conn.execute(
                        """
                        INSERT INTO ai_analysis_results
                            (complaint_id, analysis_type, model_name, model_version,
                             result_json, confidence, created_at)
                        VALUES (?, 'video_object_detection', ?, ?, ?, NULL, ?)
                        """,
                        (
                            owned_complaint_file[0],
                            YOLO_MODEL_NAME,
                            YOLO_MODEL_VERSION,
                            json.dumps(metadata, ensure_ascii=False),
                            analyzed_at,
                        ),
                    )
        except Exception:
            if annotated_path and os.path.exists(annotated_path):
                os.remove(annotated_path)
            raise

        return {
            "analysis_id": analysis_id.hex,
            "complaint_id": (
                owned_complaint_file[0]
                if owned_complaint_file is not None
                else None
            ),
            "analysis_persisted": owned_complaint_file is not None,
            "processing_status": "completed",
            "model": {"name": YOLO_MODEL_NAME, "version": YOLO_MODEL_VERSION},
            "analyzed_at": analyzed_at,
            "video_dimensions": analysis["video_dimensions"],
            "duration_seconds": analysis["duration_seconds"],
            "frames_processed": analysis["frames_processed"],
            "frames_sampled": analysis["frames_sampled"],
            "frame_interval": analysis["frame_interval"],
            "detection_counts": analysis["detection_counts"],
            "total_detections": analysis["total_detections"],
            "confidence_scores": analysis["confidence_scores"],
            "frame_detections": analysis["frame_detections"],
            "annotated_video": (
                {
                    "id": annotated_id.hex,
                    "download_url": f"/analysis-videos/annotated/{annotated_id.hex}",
                }
                if annotated_id
                else None
            ),
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Video analysis failed")
        if annotated_path and os.path.exists(annotated_path):
            os.remove(annotated_path)
        raise HTTPException(status_code=500, detail="Video analysis failed")


@app.get("/analysis-videos/annotated/{video_id}")
def get_annotated_video(
    video_id: uuid.UUID,
    current_user: dict = Depends(require_citizen),
):
    expected_path = os.path.abspath(
        os.path.join(ANNOTATED_VIDEO_DIR, f"{video_id.hex}.mp4")
    )
    with db_connection() as conn:
        owned_file = conn.execute(
            "SELECT 1 FROM uploaded_files WHERE file_path = ? AND owner_id = ?",
            (expected_path, current_user["id"]),
        ).fetchone()
    resolved_path = managed_file_path(
        expected_path,
        ANNOTATED_VIDEO_DIR,
        ANNOTATED_VIDEO_DIR,
    )
    if owned_file is None or resolved_path is None:
        raise HTTPException(status_code=404, detail="Annotated video not found")
    return FileResponse(
        resolved_path,
        filename=os.path.basename(resolved_path),
        media_type="video/mp4",
    )


@app.get("/analysis-images/annotated/{image_id}")
def get_annotated_image(
    image_id: uuid.UUID,
    current_user: dict = Depends(require_citizen),
):
    expected_path = os.path.abspath(
        os.path.join(ANNOTATED_DIR, f"{image_id.hex}.jpg")
    )
    with db_connection() as conn:
        owned_file = conn.execute(
            "SELECT 1 FROM uploaded_files WHERE file_path = ? AND owner_id = ?",
            (expected_path, current_user["id"]),
        ).fetchone()
    resolved_path = managed_file_path(
        expected_path,
        ANNOTATED_DIR,
        ANNOTATED_DIR,
    )
    if owned_file is None or resolved_path is None:
        raise HTTPException(status_code=404, detail="Annotated image not found")
    return FileResponse(
        resolved_path,
        filename=os.path.basename(resolved_path),
        media_type="image/jpeg",
    )

@app.post("/submit-complaint", response_model=ComplaintResponse)
async def submit_complaint(
    text: str = Form(..., min_length=1, max_length=10000),
    file: Optional[UploadFile] = File(None),
    latitude: Optional[float] = Form(None, ge=-90, le=90),
    longitude: Optional[float] = Form(None, ge=-180, le=180),
    current_user: dict = Depends(require_citizen),
):
    if not text.strip():
        raise HTTPException(status_code=400, detail="Complaint text is required")
    
    # Get prediction from existing NLP model
    if not all([model_category, model_priority, vectorizer, le_category, le_priority]):
        raise HTTPException(status_code=500, detail="ML models not loaded")
    
    vec = vectorizer.transform([text])
    category = le_category.inverse_transform(model_category.predict(vec))[0]
    priority = le_priority.inverse_transform(model_priority.predict(vec))[0]
    
    # Handle file upload and run YOLO detection
    file_path = None
    detected_objects = []
    if file and file.filename:
        upload_result = await upload(file, current_user)
        file_path = upload_result["file_path"]
        # Run YOLOv8 detection on uploaded file
        detected_objects = detect_objects(file_path)
    
    # Generate timestamp
    timestamp = datetime.now().isoformat()
    
    # Store in database using new schema
    try:
        with db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO complaints
                (text, category, priority, file, lat, lon, status, timestamp, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                text,
                category,
                priority,
                file_path,
                latitude,
                longitude,
                "Pending",
                timestamp,
                current_user["id"],
            ))
            complaint_id = cursor.lastrowid
            cursor.execute(
                """
                INSERT INTO complaint_status_history
                (complaint_id, status, changed_at, actor_id, actor_name, actor_email, remarks)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    complaint_id,
                    "Pending",
                    timestamp,
                    current_user["id"],
                    current_user["name"],
                    current_user["email"],
                    None,
                ),
            )
            cursor.execute(
                """
                INSERT INTO notifications
                (user_id, complaint_id, notification_type, title, message, created_at)
                VALUES (?, ?, 'complaint_submitted', ?, ?, ?)
                """,
                (
                    current_user["id"],
                    complaint_id,
                    "Complaint submitted",
                    f"Your complaint #{complaint_id} was submitted successfully.",
                    timestamp,
                ),
            )
            cursor.execute(
                """
                INSERT INTO ai_analysis_results
                (complaint_id, analysis_type, model_name, result_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    complaint_id,
                    "text_classification",
                    "tfidf_svm_category_priority",
                    json.dumps(
                        {"category": category, "priority": priority},
                        ensure_ascii=False,
                    ),
                    timestamp,
                ),
            )
    except Exception:
        if file_path:
            try:
                with db_transaction() as conn:
                    conn.execute("DELETE FROM uploaded_files WHERE file_path = ?", (file_path,))
            finally:
                if os.path.exists(file_path):
                    os.remove(file_path)
        raise
    
    return ComplaintResponse(
        id=str(complaint_id),
        text=text,
        category=category,
        priority=priority,
        file_path=file_path,
        latitude=latitude,
        longitude=longitude,
        timestamp=timestamp,
        status="Pending"
    )

@app.get("/complaints", response_model=List[ComplaintResponse])
def get_complaints(current_user: dict = Depends(require_admin)):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT c.*, u.name, rs.findings, rs.original_filename, rs.id,
               rs.officer_name, rs.submitted_at
        FROM complaints c
        LEFT JOIN users u ON u.id = c.officer_id
        LEFT JOIN complaint_resolution_submissions rs
          ON rs.id = (
              SELECT s.id
              FROM complaint_resolution_submissions s
              WHERE s.complaint_id = c.id AND s.review_status = 'approved'
              ORDER BY s.reviewed_at DESC, s.id DESC
              LIMIT 1
          )
        ORDER BY c.timestamp DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    
    complaints = []
    for row in rows:
        complaints.append(ComplaintResponse(
            id=str(row[0]),
            text=row[1],
            category=row[2],
            priority=row[3],
            file_path=row[4],
            latitude=row[5],
            longitude=row[6],
            timestamp=row[8],
            status=row[7],
            assigned_officer_id=row[12],
            assigned_at=row[13],
            assigned_officer=row[14],
            resolution_date=row[10],
            resolution_remarks=row[11],
            resolution_findings=row[15],
            resolution_attachment_name=row[16],
            resolution_attachment_url=(
                f"/resolution-submissions/{row[17]}/file" if row[17] else None
            ),
            resolution_officer=row[18],
            resolution_submitted_at=row[19],
        ))
    
    return complaints


@app.get("/admin/complaint-filter-options")
def get_admin_complaint_filter_options(
    current_user: dict = Depends(require_admin),
):
    with db_connection() as conn:
        categories = [
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT category FROM complaints "
                "WHERE category IS NOT NULL AND trim(category) <> '' "
                "ORDER BY category COLLATE NOCASE"
            )
        ]
        departments = [
            {"id": row[0], "name": row[1]}
            for row in conn.execute(
                """
                SELECT id, name FROM departments
                WHERE is_active = 1 ORDER BY name COLLATE NOCASE, id
                """
            )
        ]
        officers = [
            {"id": row[0], "name": row[1], "email": row[2],
             "department_id": row[3], "department": row[4]}
            for row in conn.execute(
                """
                SELECT u.id, u.name, u.email, op.department_id, d.name
                FROM users u
                LEFT JOIN officer_profiles op ON op.user_id = u.id
                LEFT JOIN departments d ON d.id = op.department_id
                WHERE u.role = 'officer' AND u.is_active = 1
                  AND op.user_id IS NOT NULL
                  AND (op.department_id IS NULL OR d.is_active = 1)
                ORDER BY u.name COLLATE NOCASE, u.id
                """
            )
        ]
    return {
        "categories": categories,
        "departments": departments,
        "officers": officers,
        "statuses": ["Pending", "In Progress", "Resolved"],
        "priorities": ["High", "Medium", "Low"],
    }


@app.get("/admin/complaints")
def search_admin_complaints(
    search: Optional[str] = Query(default=None, max_length=200),
    status: Optional[Literal["Pending", "In Progress", "Resolved"]] = None,
    priority: Optional[Literal["High", "Medium", "Low"]] = None,
    category: Optional[str] = Query(default=None, max_length=100),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    department_id: Optional[int] = Query(default=None, gt=0),
    officer_id: Optional[int] = Query(default=None, gt=0),
    sort: Literal["newest", "oldest", "priority", "status"] = "newest",
    page: int = Query(default=1, ge=1, le=1_000_000),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(require_admin),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail="date_from must be on or before date_to",
        )

    conditions = []
    params = []
    if search and search.strip():
        term = f"%{search.strip()}%"
        conditions.append(
            """
            (CAST(c.id AS TEXT) LIKE ? OR c.text LIKE ? OR c.category LIKE ?
             OR c.priority LIKE ? OR c.status LIKE ? OR u.name LIKE ?
             OR u.email LIKE ? OR d.name LIKE ? OR citizen.name LIKE ?
             OR citizen.email LIKE ?)
            """
        )
        params.extend([term] * 10)
    if status:
        conditions.append("c.status = ?")
        params.append(status)
    if priority:
        conditions.append("lower(c.priority) = lower(?)")
        params.append(priority)
    if category:
        conditions.append("c.category = ?")
        params.append(category)
    if date_from:
        conditions.append("date(c.timestamp) >= date(?)")
        params.append(date_from.isoformat())
    if date_to:
        conditions.append("date(c.timestamp) <= date(?)")
        params.append(date_to.isoformat())
    if department_id is not None:
        conditions.append("op.department_id = ?")
        params.append(department_id)
    if officer_id is not None:
        conditions.append("c.officer_id = ?")
        params.append(officer_id)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    order_by = {
        "newest": "c.timestamp DESC, c.id DESC",
        "oldest": "c.timestamp ASC, c.id ASC",
        "priority": (
            "CASE lower(c.priority) WHEN 'high' THEN 0 "
            "WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END, "
            "c.timestamp DESC, c.id DESC"
        ),
        "status": (
            "CASE c.status WHEN 'Pending' THEN 0 "
            "WHEN 'In Progress' THEN 1 WHEN 'Resolved' THEN 2 ELSE 3 END, "
            "c.timestamp DESC, c.id DESC"
        ),
    }[sort]
    joins = """
        FROM complaints c
        LEFT JOIN users u ON u.id = c.officer_id
        LEFT JOIN users citizen ON citizen.id = c.user_id
        LEFT JOIN officer_profiles op ON op.user_id = c.officer_id
        LEFT JOIN departments d ON d.id = op.department_id
    """

    with db_connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) {joins} {where_clause}", params
        ).fetchone()[0]
        aggregate = conn.execute(
            f"""
            SELECT
                SUM(CASE WHEN c.status = 'Pending' THEN 1 ELSE 0 END),
                SUM(CASE WHEN c.status = 'In Progress' THEN 1 ELSE 0 END),
                SUM(CASE WHEN c.status = 'Resolved' THEN 1 ELSE 0 END),
                SUM(CASE WHEN lower(c.priority) = 'high' THEN 1 ELSE 0 END),
                SUM(CASE WHEN lower(c.priority) = 'medium' THEN 1 ELSE 0 END),
                SUM(CASE WHEN lower(c.priority) = 'low' THEN 1 ELSE 0 END)
            {joins} {where_clause}
            """,
            params,
        ).fetchone()
        rows = conn.execute(
            f"""
            SELECT c.id, c.text, c.category, c.priority, c.file, c.lat, c.lon,
                   c.status, c.timestamp, c.resolution_date, c.resolution_remarks,
                   c.officer_id, c.assigned_at, u.name, d.id, d.name,
                   rs.findings, rs.original_filename, rs.id, rs.officer_name,
                   rs.submitted_at
            {joins}
            LEFT JOIN complaint_resolution_submissions rs
              ON rs.id = (
                  SELECT s.id FROM complaint_resolution_submissions s
                  WHERE s.complaint_id = c.id AND s.review_status = 'approved'
                  ORDER BY s.reviewed_at DESC, s.id DESC LIMIT 1
              )
            {where_clause}
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, (page - 1) * page_size],
        ).fetchall()

    items = [
        ComplaintResponse(
            id=str(row[0]),
            text=row[1],
            category=row[2],
            priority=row[3],
            file_path=row[4],
            latitude=row[5],
            longitude=row[6],
            status=row[7] or "Pending",
            timestamp=row[8],
            resolution_date=row[9],
            resolution_remarks=row[10],
            assigned_officer_id=row[11],
            assigned_at=row[12],
            assigned_officer=row[13],
            department_id=row[14],
            department=row[15],
            resolution_findings=row[16],
            resolution_attachment_name=row[17],
            resolution_attachment_url=(
                f"/resolution-submissions/{row[18]}/file" if row[18] else None
            ),
            resolution_officer=row[19],
            resolution_submitted_at=row[20],
        ).model_dump()
        for row in rows
    ]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "stats": {
            "total": total,
            "pending": aggregate[0] or 0,
            "in_progress": aggregate[1] or 0,
            "resolved": aggregate[2] or 0,
            "high": aggregate[3] or 0,
            "medium": aggregate[4] or 0,
            "low": aggregate[5] or 0,
        },
    }


@app.get("/admin/complaints/{complaint_id}")
def get_admin_complaint_details(
    complaint_id: PositiveId,
    current_user: dict = Depends(require_admin),
):
    with db_connection() as conn:
        complaint = conn.execute(
            """
            SELECT c.id, c.text, c.category, c.priority, c.timestamp, c.file,
                   c.lat, c.lon, c.status, c.resolution_date,
                   c.resolution_remarks, c.officer_id, c.assigned_at,
                   u.name, op.department_id, d.name
            FROM complaints c
            LEFT JOIN users u ON u.id = c.officer_id
            LEFT JOIN officer_profiles op ON op.user_id = c.officer_id
            LEFT JOIN departments d ON d.id = op.department_id
            WHERE c.id = ?
            """,
            (complaint_id,),
        ).fetchone()
        if complaint is None:
            raise HTTPException(status_code=404, detail="Complaint not found")

        status_history = conn.execute(
            """
            SELECT h.previous_status, h.status, h.changed_at,
                   CASE WHEN u.role = 'citizen' THEN 'Citizen'
                        WHEN u.role IS NULL THEN 'Authorized user'
                        ELSE h.actor_name END,
                   h.remarks
            FROM complaint_status_history h
            LEFT JOIN users u ON u.id = h.actor_id
            WHERE h.complaint_id = ?
            ORDER BY h.changed_at ASC, h.id ASC
            """,
            (complaint_id,),
        ).fetchall()
        assignment_history = conn.execute(
            """
            SELECT h.previous_officer_id, previous.name, h.new_officer_id,
                   current.name, h.assigned_by, assigner.name, h.assigned_at,
                   h.reason, h.department_id, d.name
            FROM complaint_assignment_history h
            LEFT JOIN users previous ON previous.id = h.previous_officer_id
            LEFT JOIN users current ON current.id = h.new_officer_id
            LEFT JOIN users assigner ON assigner.id = h.assigned_by
            LEFT JOIN departments d ON d.id = h.department_id
            WHERE h.complaint_id = ?
            ORDER BY h.assigned_at ASC, h.id ASC
            """,
            (complaint_id,),
        ).fetchall()
        resolution = conn.execute(
            """
            SELECT resolution_date, resolution_remarks
            FROM complaints WHERE id = ?
            """,
            (complaint_id,),
        ).fetchone()
        approved_resolution = conn.execute(
            """
            SELECT s.findings, s.remarks, s.resolution_date, s.officer_name,
                   s.submitted_at, s.original_filename, s.id, s.review_status,
                   s.reviewed_at, s.review_remarks, reviewer.name
            FROM complaint_resolution_submissions s
            LEFT JOIN users reviewer ON reviewer.id = s.reviewed_by
            WHERE s.complaint_id = ? AND s.review_status = 'approved'
            ORDER BY s.reviewed_at DESC, s.id DESC LIMIT 1
            """,
            (complaint_id,),
        ).fetchone()
        latest_resolution_submission = conn.execute(
            """
            SELECT s.id, s.review_status, s.officer_name, s.submitted_at,
                   s.reviewed_at, s.review_remarks, reviewer.name
            FROM complaint_resolution_submissions s
            LEFT JOIN users reviewer ON reviewer.id = s.reviewed_by
            WHERE s.complaint_id = ?
            ORDER BY s.submitted_at DESC, s.id DESC LIMIT 1
            """,
            (complaint_id,),
        ).fetchone()

    return {
        "id": str(complaint[0]),
        "text": complaint[1],
        "category": complaint[2],
        "priority": complaint[3],
        "timestamp": complaint[4],
        "status": complaint[8] or "Pending",
        "latitude": complaint[6],
        "longitude": complaint[7],
        "evidence_url": (
            f"/admin/complaints/{complaint_id}/evidence" if complaint[5] else None
        ),
        "evidence_type": mimetypes.guess_type(complaint[5])[0] if complaint[5] else None,
        "assignment": {
            "officer_id": complaint[11],
            "officer_name": complaint[13],
            "assigned_at": complaint[12],
            "department_id": complaint[14],
            "department": complaint[15],
            "history": [
                {
                    "previous_officer_id": event[0],
                    "previous_officer": event[1],
                    "officer_id": event[2],
                    "officer": event[3],
                    "assigned_by": event[4],
                    "assigned_by_name": event[5],
                    "assigned_at": event[6],
                    "reason": event[7],
                    "department_id": event[8],
                    "department": event[9],
                }
                for event in assignment_history
            ],
        },
        "resolution": (
            {
                "date": approved_resolution[2] or resolution[0],
                "remarks": approved_resolution[1],
                "findings": approved_resolution[0],
                "officer_name": approved_resolution[3],
                "submitted_at": approved_resolution[4],
                "attachment_name": approved_resolution[5],
                "attachment_url": (
                    f"/resolution-submissions/{approved_resolution[6]}/file"
                ),
                "completed_by": approved_resolution[10],
                "completed_at": approved_resolution[8],
                "administrator_remarks": approved_resolution[9],
            }
            if approved_resolution
            else (
                {
                    "date": resolution[0],
                    "remarks": resolution[1],
                    "findings": None,
                    "officer_name": None,
                    "submitted_at": None,
                    "attachment_name": None,
                    "attachment_url": None,
                    "completed_by": None,
                    "completed_at": None,
                    "administrator_remarks": None,
                }
                if resolution[0] or resolution[1]
                else None
            )
        ),
        "resolution_review": (
            {
                "submission_id": latest_resolution_submission[0],
                "status": latest_resolution_submission[1],
                "officer_name": latest_resolution_submission[2],
                "submitted_at": latest_resolution_submission[3],
                "reviewed_at": latest_resolution_submission[4],
                "administrator_remarks": latest_resolution_submission[5],
                "reviewed_by": latest_resolution_submission[6],
            }
            if latest_resolution_submission
            else None
        ),
        "history": [
            {
                "previous_status": event[0],
                "status": event[1],
                "changed_at": event[2],
                "actor_name": event[3],
                "remarks": event[4],
            }
            for event in status_history
        ],
    }


@app.get("/admin/complaints/{complaint_id}/evidence")
def get_admin_complaint_evidence(
    complaint_id: PositiveId,
    current_user: dict = Depends(require_admin),
):
    with db_connection() as conn:
        row = conn.execute(
            "SELECT file FROM complaints WHERE id = ?", (complaint_id,)
        ).fetchone()
    if row is None or not row[0]:
        raise HTTPException(status_code=404, detail="Complaint evidence not found")
    file_path = managed_file_path(
        row[0], UPLOADS_DIR, os.path.join(BASE_DIR, "uploads")
    )
    if file_path is None:
        raise HTTPException(status_code=404, detail="Complaint evidence not found")
    return FileResponse(file_path, filename=os.path.basename(file_path))


@app.post("/admin/officers", status_code=201)
def create_officer(
    payload: OfficerCreateRequest,
    current_user: dict = Depends(require_admin),
):
    created_at = datetime.now().isoformat()
    try:
        with db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users (name, email, password_hash, role, created_at)
                VALUES (?, ?, ?, 'officer', ?)
                """,
                (payload.name, payload.email, hash_password(payload.password), created_at),
            )
            officer_id = cursor.lastrowid
            cursor.execute(
                """
                INSERT INTO officer_profiles (user_id, department_id, created_at)
                VALUES (?, NULL, ?)
                """,
                (officer_id, created_at),
            )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    return {
        "id": officer_id,
        "name": payload.name,
        "email": payload.email,
        "role": "officer",
        "created_at": created_at,
    }


@app.get("/admin/officers")
def list_officers(current_user: dict = Depends(require_admin)):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT u.id, u.name, u.email
        FROM users u
        JOIN officer_profiles op ON op.user_id = u.id
        LEFT JOIN departments d ON d.id = op.department_id
        WHERE u.role = 'officer' AND u.is_active = 1
          AND (op.department_id IS NULL OR d.is_active = 1)
        ORDER BY u.name, u.id
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"id": row[0], "name": row[1], "email": row[2]} for row in rows]


@app.put("/admin/complaints/{complaint_id}/assignment")
def assign_complaint(
    complaint_id: PositiveId,
    assignment: ComplaintAssignmentRequest,
    current_user: dict = Depends(require_admin),
):
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        result = persist_complaint_assignment(
            conn,
            complaint_id,
            assignment.officer_id,
            current_user["id"],
        )
        if not result["changed"]:
            return {
                "message": "Complaint is already assigned to this officer",
                "complaint_id": str(complaint_id),
                "officer_id": assignment.officer_id,
                "assigned_at": result["assigned_at"],
            }

        if result["owner_id"] is not None:
            cursor.execute(
                """
                INSERT INTO notifications
                (user_id, complaint_id, notification_type, title, message, created_at)
                VALUES (?, ?, 'complaint_assigned', ?, ?, ?)
                """,
                (
                    result["owner_id"],
                    complaint_id,
                    "Complaint assigned",
                    f"Your complaint #{complaint_id} has been assigned for handling.",
                    result["assigned_at"],
                ),
            )
    return {
        "message": "Complaint assigned successfully",
        "complaint_id": str(complaint_id),
        "officer_id": result["officer_id"],
        "assigned_at": result["assigned_at"],
    }


@app.get("/officer/complaints", response_model=List[OfficerComplaintItem])
def get_officer_complaints(
    search: Optional[str] = Query(default=None, max_length=100),
    status: Optional[Literal["Pending", "In Progress", "Resolved"]] = None,
    current_user: dict = Depends(require_officer),
):
    valid_statuses = ["Pending", "In Progress", "Resolved"]
    if status is not None and status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status filter")

    query = """
        SELECT id, text, category, priority, timestamp, assigned_at, status
        FROM complaints
        WHERE officer_id = ?
    """
    params = [current_user["id"]]
    if status:
        query += " AND status = ?"
        params.append(status)
    if search and search.strip():
        term = f"%{search.strip()}%"
        if search.strip().isdigit():
            query += " AND (CAST(id AS TEXT) LIKE ? OR category LIKE ? OR priority LIKE ?)"
        else:
            query += " AND (category LIKE ? OR priority LIKE ?)"
        params.extend([term] * (3 if search.strip().isdigit() else 2))
    query += " ORDER BY assigned_at DESC, id DESC"

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [
        OfficerComplaintItem(
            id=str(row[0]),
            description=row[1],
            category=row[2],
            priority=row[3],
            submitted_at=row[4],
            assigned_at=row[5],
            status=row[6],
        )
        for row in rows
    ]


@app.get("/officer/complaints/{complaint_id}", response_model=OfficerComplaintDetails)
def get_officer_complaint_details(
    complaint_id: PositiveId,
    current_user: dict = Depends(require_officer),
):
    conn = connect_db()
    cursor = conn.cursor()
    query = """
        SELECT c.id, c.text, c.category, c.priority, c.timestamp, c.file,
               c.lat, c.lon, c.assigned_at, c.status, u.name, c.officer_id
        FROM complaints c
        LEFT JOIN users u ON u.id = c.officer_id
        WHERE c.id = ?
    """
    cursor.execute(query, (complaint_id,))
    complaint = cursor.fetchone()
    if complaint is None or (
        current_user["role"] == "officer"
        and complaint[11] != current_user["id"]
    ):
        conn.close()
        raise HTTPException(status_code=404, detail="Complaint not found")

    cursor.execute(
        """
        SELECT h.previous_status, h.status, h.changed_at,
               CASE
                   WHEN u.role = 'citizen' THEN 'Citizen'
                   WHEN u.role IS NULL THEN 'Authorized user'
                   ELSE h.actor_name
               END,
               h.remarks
        FROM complaint_status_history h
        LEFT JOIN users u ON u.id = h.actor_id
        WHERE h.complaint_id = ?
        ORDER BY h.changed_at ASC, h.id ASC
        """,
        (complaint_id,),
    )
    history = cursor.fetchall()
    cursor.execute(
        """
        SELECT n.id, n.author_name, n.note_type, n.note, n.created_at
        FROM complaint_investigation_notes n
        WHERE n.complaint_id = ?
        ORDER BY n.created_at ASC, n.id ASC
        """,
        (complaint_id,),
    )
    notes = cursor.fetchall()
    cursor.execute(
        """
        SELECT s.id, s.officer_name, s.findings, s.remarks, s.resolution_date,
               s.original_filename, s.content_type, s.file_size, s.submitted_at,
               s.review_status, s.reviewed_at, s.review_remarks, reviewer.name
        FROM complaint_resolution_submissions s
        LEFT JOIN users reviewer ON reviewer.id = s.reviewed_by
        WHERE s.complaint_id = ?
        ORDER BY s.submitted_at DESC, s.id DESC
        LIMIT 1
        """,
        (complaint_id,),
    )
    submission = cursor.fetchone()
    conn.close()

    return OfficerComplaintDetails(
        id=str(complaint[0]),
        text=complaint[1],
        category=complaint[2],
        priority=complaint[3],
        timestamp=complaint[4],
        evidence_url=(
            f"/officer/complaints/{complaint_id}/evidence" if complaint[5] else None
        ),
        evidence_type=mimetypes.guess_type(complaint[5])[0] if complaint[5] else None,
        latitude=complaint[6],
        longitude=complaint[7],
        assigned_at=complaint[8],
        status=complaint[9],
        assigned_officer=complaint[10],
        history=[
            ComplaintStatusEvent(
                previous_status=event[0],
                status=event[1],
                changed_at=event[2],
                actor_name=event[3],
                remarks=event[4],
            )
            for event in history
        ],
        notes=[
            InvestigationNote(
                id=note[0],
                author_name=note[1],
                note_type=note[2],
                note=note[3],
                created_at=note[4],
            )
            for note in notes
        ],
        resolution_submission=(
            ResolutionSubmissionItem(
                id=submission[0],
                complaint_id=str(complaint_id),
                officer_name=submission[1],
                findings=submission[2],
                remarks=submission[3],
                resolution_date=submission[4],
                attachment_name=submission[5],
                content_type=submission[6],
                file_size=submission[7],
                submitted_at=submission[8],
                attachment_url=f"/resolution-submissions/{submission[0]}/file",
                review_status=submission[9],
                reviewed_at=submission[10],
                review_remarks=submission[11],
                reviewed_by_name=submission[12],
            )
            if submission is not None
            else None
        ),
    )


@app.post("/officer/complaints/{complaint_id}/notes", response_model=InvestigationNote)
def add_investigation_note(
    complaint_id: PositiveId,
    payload: InvestigationNoteRequest,
    current_user: dict = Depends(require_officer),
):
    created_at = datetime.now().isoformat()
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM complaints WHERE id = ? AND officer_id = ?",
            (complaint_id, current_user["id"]),
        )
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Complaint not found")
        cursor.execute(
            """
            INSERT INTO complaint_investigation_notes
            (complaint_id, officer_id, author_name, note_type, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                complaint_id,
                current_user["id"],
                current_user["name"],
                payload.note_type,
                payload.note,
                created_at,
            ),
        )
        note_id = cursor.lastrowid
    return InvestigationNote(
        id=note_id,
        author_name=current_user["name"],
        note_type=payload.note_type,
        note=payload.note,
        created_at=created_at,
    )


@app.post(
    "/officer/complaints/{complaint_id}/resolution",
    response_model=ResolutionSubmissionItem,
)
async def submit_officer_resolution(
    complaint_id: PositiveId,
    findings: str = Form(..., min_length=1, max_length=10000),
    remarks: str = Form(..., min_length=1, max_length=5000),
    resolution_date: date = Form(...),
    file: UploadFile = File(...),
    current_user: dict = Depends(require_officer),
):
    filename = unicodedata.normalize("NFC", (file.filename or "").strip())
    if (
        not filename
        or len(filename) > 255
        or "/" in filename
        or "\\" in filename
        or any(unicodedata.category(char).startswith("C") for char in filename)
    ):
        raise HTTPException(status_code=400, detail="Invalid attachment filename")

    extension = os.path.splitext(filename)[1].lower()
    allowed_types = {
        ".jpg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
        ".jpeg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
        ".png": ("image/png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
        ".webp": (
            "image/webp",
            lambda data: len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP",
        ),
        ".pdf": ("application/pdf", lambda data: data.startswith(b"%PDF-")),
        ".docx": (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            lambda data: _valid_docx(data),
        ),
    }
    if extension not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Attachment must be a JPEG, PNG, WebP, PDF, or DOCX file",
        )

    expected_type, validate_signature = allowed_types[extension]
    supplied_type = (file.content_type or "").lower()
    if supplied_type not in (expected_type, "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Attachment type does not match its filename")

    clean_findings = findings.strip()
    clean_remarks = remarks.strip()
    if not clean_findings or not clean_remarks:
        raise HTTPException(status_code=400, detail="Findings and resolution remarks are required")
    if resolution_date > datetime.now(timezone.utc).date():
        raise HTTPException(
            status_code=422,
            detail="Resolution date cannot be in the future",
        )

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT status FROM complaints WHERE id = ? AND officer_id = ?",
        (complaint_id, current_user["id"]),
    )
    complaint = cursor.fetchone()
    if complaint is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Complaint not found")
    if complaint[0] != "In Progress":
        conn.close()
        raise HTTPException(status_code=409, detail="Complaint must be in progress before submitting resolution")
    cursor.execute(
        """
        SELECT 1 FROM complaint_resolution_submissions
        WHERE complaint_id = ? AND review_status = 'pending_review'
        LIMIT 1
        """,
        (complaint_id,),
    )
    if cursor.fetchone() is not None:
        conn.close()
        raise HTTPException(status_code=409, detail="A resolution submission is already awaiting review")
    conn.close()

    stored_path, expected_type, file_size = await save_upload(
        file, filename, UPLOADS_DIR, allowed_types
    )

    submitted_at = datetime.now(timezone.utc).isoformat()
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            """
            SELECT status FROM complaints WHERE id = ? AND officer_id = ?
            """,
            (complaint_id, current_user["id"]),
        )
        complaint = cursor.fetchone()
        if complaint is None:
            raise HTTPException(status_code=404, detail="Complaint not found")
        if complaint[0] != "In Progress":
            raise HTTPException(status_code=409, detail="Complaint must be in progress before submitting resolution")
        cursor.execute(
            """
            SELECT 1 FROM complaint_resolution_submissions
            WHERE complaint_id = ? AND review_status = 'pending_review'
            LIMIT 1
            """,
            (complaint_id,),
        )
        if cursor.fetchone() is not None:
            raise HTTPException(status_code=409, detail="A resolution submission is already awaiting review")
        cursor.execute(
            """
            INSERT INTO complaint_resolution_submissions
            (complaint_id, officer_id, officer_name, findings, remarks, resolution_date,
             file_path, original_filename, content_type, file_size, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                complaint_id,
                current_user["id"],
                current_user["name"],
                clean_findings,
                clean_remarks,
                resolution_date.isoformat(),
                stored_path,
                filename,
                expected_type,
                file_size,
                submitted_at,
            ),
        )
        submission_id = cursor.lastrowid
        conn.commit()
    except HTTPException:
        if "conn" in locals():
            conn.rollback()
            conn.close()
        if os.path.exists(stored_path):
            os.remove(stored_path)
        raise
    except Exception:
        if "conn" in locals():
            conn.rollback()
            conn.close()
        if os.path.exists(stored_path):
            os.remove(stored_path)
        raise
    conn.close()
    return ResolutionSubmissionItem(
        id=submission_id,
        complaint_id=str(complaint_id),
        officer_name=current_user["name"],
        findings=clean_findings,
        remarks=clean_remarks,
        resolution_date=resolution_date.isoformat(),
        attachment_name=filename,
        content_type=expected_type,
        file_size=file_size,
        submitted_at=submitted_at,
        attachment_url=f"/resolution-submissions/{submission_id}/file",
    )


@app.put("/officer/complaints/{complaint_id}/status")
def update_officer_complaint_status(
    complaint_id: PositiveId,
    status_update: OfficerStatusUpdate,
    current_user: dict = Depends(require_officer),
):
    transitions = {"Pending": "In Progress"}
    if status_update.status not in transitions.values():
        raise HTTPException(status_code=400, detail="Officers must submit resolution for administrator approval")

    with db_transaction() as conn:
        conn.execute("BEGIN IMMEDIATE")
        result = transition_complaint_status(
            conn,
            complaint_id,
            status_update.status,
            current_user,
            status_update.remarks,
            required_previous_status="Pending",
            officer_id=current_user["id"],
        )
        if result["owner_id"] is not None:
            conn.execute(
                """
                INSERT INTO notifications
                (user_id, complaint_id, notification_type, title, message, created_at)
                VALUES (?, ?, 'complaint_status_updated', ?, ?, ?)
                """,
                (
                    result["owner_id"],
                    complaint_id,
                    "Complaint status updated",
                    f"Your complaint #{complaint_id} status is now {status_update.status}.",
                    result["changed_at"],
                ),
            )
    return {
        "message": "Status updated successfully",
        "complaint_id": str(complaint_id),
        "previous_status": result["previous_status"],
        "new_status": status_update.status,
        "changed_at": result["changed_at"],
    }


@app.get("/officer/complaints/{complaint_id}/evidence")
def get_officer_complaint_evidence(
    complaint_id: PositiveId,
    current_user: dict = Depends(require_officer),
):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT file FROM complaints WHERE id = ? AND officer_id = ?",
        (complaint_id, current_user["id"]),
    )
    row = cursor.fetchone()
    conn.close()
    if row is None or not row[0]:
        raise HTTPException(status_code=404, detail="Evidence not found")

    file_path = managed_file_path(
        row[0], UPLOADS_DIR, os.path.join(BASE_DIR, "uploads")
    )
    if file_path is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return FileResponse(
        file_path,
        media_type=mimetypes.guess_type(file_path)[0] or "application/octet-stream",
    )


@app.get("/my-complaints", response_model=ComplaintHistoryPage)
def get_my_complaints(
    status: Optional[Literal["Pending", "In Progress", "Resolved"]] = None,
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(require_citizen),
):
    valid_statuses = ["Pending", "In Progress", "Resolved"]
    if status is not None and status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status filter")

    conn = connect_db()
    cursor = conn.cursor()
    where_clause = "WHERE user_id = ?"
    params = [current_user["id"]]
    if status is not None:
        where_clause += " AND status = ?"
        params.append(status)

    cursor.execute(f"SELECT COUNT(*) FROM complaints {where_clause}", params)
    total = cursor.fetchone()[0]
    cursor.execute(
        f"""
        SELECT id, timestamp, category, status
        FROM complaints
        {where_clause}
        ORDER BY timestamp DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        [*params, limit, offset],
    )
    rows = cursor.fetchall()
    conn.close()

    return ComplaintHistoryPage(
        items=[
            ComplaintHistoryItem(
                id=str(row[0]),
                timestamp=row[1],
                category=row[2],
                status=row[3],
            )
            for row in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get("/my-complaints/{complaint_id}", response_model=ComplaintDetails)
def get_my_complaint_details(
    complaint_id: PositiveId,
    current_user: dict = Depends(require_citizen),
):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, text, category, priority, timestamp, file, lat, lon, status,
               resolution_date, resolution_remarks
        FROM complaints
        WHERE id = ? AND user_id = ?
        """,
        (complaint_id, current_user["id"]),
    )
    complaint = cursor.fetchone()
    if complaint is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Complaint not found")

    cursor.execute(
        """
        SELECT previous_status, status, changed_at, actor_name, remarks
        FROM complaint_status_history
        WHERE complaint_id = ?
        ORDER BY changed_at ASC, id ASC
        """,
        (complaint_id,),
    )
    history = cursor.fetchall()
    cursor.execute(
        """
        SELECT id, author_name, note_type, note, created_at
        FROM complaint_investigation_notes
        WHERE complaint_id = ? AND note_type = 'citizen_visible'
        ORDER BY created_at ASC, id ASC
        """,
        (complaint_id,),
    )
    citizen_messages = cursor.fetchall()
    cursor.execute(
        """
        SELECT s.findings, s.officer_name, s.submitted_at,
               s.original_filename, s.id, s.reviewed_at,
               s.review_remarks, reviewer.name
        FROM complaint_resolution_submissions s
        LEFT JOIN users reviewer ON reviewer.id = s.reviewed_by
        WHERE s.complaint_id = ? AND s.review_status = 'approved'
        ORDER BY s.reviewed_at DESC, s.id DESC
        LIMIT 1
        """,
        (complaint_id,),
    )
    approved_resolution = cursor.fetchone()
    conn.close()

    return ComplaintDetails(
        id=str(complaint[0]),
        text=complaint[1],
        category=complaint[2],
        priority=complaint[3],
        timestamp=complaint[4],
        evidence_url=(
            f"/my-complaints/{complaint_id}/evidence" if complaint[5] else None
        ),
        evidence_type=mimetypes.guess_type(complaint[5])[0] if complaint[5] else None,
        latitude=complaint[6],
        longitude=complaint[7],
        status=complaint[8],
        history=[
            ComplaintStatusEvent(
                previous_status=event[0],
                status=event[1],
                changed_at=event[2],
                actor_name=event[3],
                remarks=event[4],
            )
            for event in history
        ],
        citizen_messages=[
            InvestigationNote(
                id=message[0],
                author_name=message[1],
                note_type=message[2],
                note=message[3],
                created_at=message[4],
            )
            for message in citizen_messages
        ],
        resolution=(
            ComplaintResolution(
                date=complaint[9],
                remarks=complaint[10],
                findings=approved_resolution[0] if approved_resolution else None,
                officer_name=approved_resolution[1] if approved_resolution else None,
                submitted_at=approved_resolution[2] if approved_resolution else None,
                attachment_name=approved_resolution[3] if approved_resolution else None,
                attachment_url=(
                    f"/resolution-submissions/{approved_resolution[4]}/file"
                    if approved_resolution
                    else None
                ),
                completed_by=approved_resolution[7] if approved_resolution else None,
                completed_at=approved_resolution[5] if approved_resolution else None,
                administrator_remarks=(
                    approved_resolution[6] if approved_resolution else None
                ),
            )
            if complaint[8] == "Resolved" and complaint[9] is not None
            else None
        ),
    )


@app.get("/my-complaints/{complaint_id}/evidence")
def get_my_complaint_evidence(
    complaint_id: PositiveId,
    current_user: dict = Depends(require_citizen),
):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT file FROM complaints WHERE id = ? AND user_id = ?",
        (complaint_id, current_user["id"]),
    )
    row = cursor.fetchone()
    conn.close()
    if row is None or not row[0]:
        raise HTTPException(status_code=404, detail="Evidence not found")

    file_path = managed_file_path(
        row[0], UPLOADS_DIR, os.path.join(BASE_DIR, "uploads")
    )
    if file_path is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return FileResponse(
        file_path,
        media_type=mimetypes.guess_type(file_path)[0] or "application/octet-stream",
    )


@app.get("/notifications", response_model=NotificationList)
def get_notifications(current_user: dict = Depends(require_citizen)):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
        (current_user["id"],),
    )
    unread_count = cursor.fetchone()[0]
    cursor.execute(
        """
        SELECT id, complaint_id, notification_type, title, message, created_at,
               is_read
        FROM notifications
        WHERE user_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 100
        """,
        (current_user["id"],),
    )
    rows = cursor.fetchall()
    conn.close()
    return NotificationList(
        notifications=[
            NotificationItem(
                id=row[0],
                complaint_id=str(row[1]) if row[1] is not None else None,
                notification_type=row[2],
                title=row[3],
                message=row[4],
                created_at=row[5],
                is_read=bool(row[6]),
            )
            for row in rows
        ],
        unread_count=unread_count,
    )


@app.patch("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: PositiveId,
    current_user: dict = Depends(require_citizen),
):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
        (notification_id, current_user["id"]),
    )
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Notification not found")
    conn.commit()
    conn.close()
    return {"message": "Notification marked as read", "notification_id": notification_id}


@app.get(
    "/admin/resolution-submissions",
    response_model=List[ResolutionSubmissionItem],
)
def get_pending_resolution_submissions(
    current_user: dict = Depends(require_admin),
):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT s.id, s.complaint_id, s.officer_name, s.findings, s.remarks,
               s.resolution_date, s.original_filename, s.content_type,
               s.file_size, s.submitted_at, s.review_status, s.reviewed_at,
               s.review_remarks, reviewer.name
        FROM complaint_resolution_submissions s
        LEFT JOIN users reviewer ON reviewer.id = s.reviewed_by
        WHERE s.review_status = 'pending_review'
        ORDER BY s.submitted_at ASC, s.id ASC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        ResolutionSubmissionItem(
            id=row[0],
            complaint_id=str(row[1]),
            officer_name=row[2],
            findings=row[3],
            remarks=row[4],
            resolution_date=row[5],
            attachment_name=row[6],
            content_type=row[7],
            file_size=row[8],
            submitted_at=row[9],
            attachment_url=f"/resolution-submissions/{row[0]}/file",
            review_status=row[10],
            reviewed_at=row[11],
            review_remarks=row[12],
            reviewed_by_name=row[13],
        )
        for row in rows
    ]


def _valid_docx(contents: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(contents)) as archive:
            names = set(archive.namelist())
            return "[Content_Types].xml" in names and "word/document.xml" in names
    except (OSError, zipfile.BadZipFile):
        return False


@app.post("/admin/resolution-submissions/{submission_id}/approve")
def approve_resolution_submission(
    submission_id: PositiveId,
    review: ResolutionReviewRequest,
    current_user: dict = Depends(require_admin),
):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("BEGIN IMMEDIATE")
    cursor.execute(
        """
        SELECT s.complaint_id, s.findings, s.remarks, s.resolution_date, c.status, c.user_id
        FROM complaint_resolution_submissions s
        JOIN complaints c ON c.id = s.complaint_id
        WHERE s.id = ? AND s.review_status = 'pending_review'
        """,
        (submission_id,),
    )
    submission = cursor.fetchone()
    if submission is None:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=404, detail="Pending resolution submission not found")
    complaint_id, findings, resolution_remarks, resolution_date, previous_status, owner_id = submission
    if previous_status != "In Progress":
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=409, detail="Complaint is no longer awaiting resolution")

    reviewed_at = datetime.now(timezone.utc).isoformat()
    try:
        cursor.execute(
            """
            UPDATE complaint_resolution_submissions
            SET review_status = 'approved', reviewed_by = ?, reviewed_at = ?, review_remarks = ?
            WHERE id = ? AND review_status = 'pending_review'
            """,
            (
                current_user["id"],
                reviewed_at,
                review.remarks,
                submission_id,
            ),
        )
        if cursor.rowcount != 1:
            raise HTTPException(status_code=409, detail="Resolution submission was already reviewed")
        history_remarks = resolution_remarks
        if review.remarks:
            history_remarks = f"{resolution_remarks}\nAdministrator review: {review.remarks}"
        transition = transition_complaint_status(
            conn,
            complaint_id,
            "Resolved",
            current_user,
            history_remarks,
            changed_at=reviewed_at,
            required_previous_status="In Progress",
            update_resolution=True,
            resolution_date=resolution_date,
            resolution_remarks=resolution_remarks,
        )
        if not transition["changed"]:
            raise HTTPException(
                status_code=409,
                detail="Complaint is no longer awaiting resolution",
            )
        if owner_id is not None:
            cursor.execute(
                """
                INSERT INTO notifications
                (user_id, complaint_id, notification_type, title, message, created_at)
                VALUES (?, ?, 'complaint_resolved', ?, ?, ?)
                """,
                (
                    owner_id,
                    complaint_id,
                    "Complaint resolved",
                    f"Your complaint #{complaint_id} has been resolved.",
                    reviewed_at,
                ),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()
    return {
        "message": "Resolution approved and complaint resolved",
        "submission_id": submission_id,
        "complaint_id": str(complaint_id),
        "previous_status": previous_status,
        "status": "Resolved",
        "approved_at": reviewed_at,
    }


@app.post("/admin/resolution-submissions/{submission_id}/reject")
def reject_resolution_submission(
    submission_id: PositiveId,
    review: ResolutionReviewRequest,
    current_user: dict = Depends(require_admin),
):
    conn = connect_db()
    cursor = conn.cursor()
    reviewed_at = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        """
        UPDATE complaint_resolution_submissions
        SET review_status = 'rejected', reviewed_by = ?, reviewed_at = ?, review_remarks = ?
        WHERE id = ? AND review_status = 'pending_review'
        """,
        (current_user["id"], reviewed_at, review.remarks, submission_id),
    )
    if cursor.rowcount != 1:
        conn.close()
        raise HTTPException(status_code=404, detail="Pending resolution submission not found")
    conn.commit()
    conn.close()
    return {"message": "Resolution submission rejected", "submission_id": submission_id}


@app.get("/resolution-submissions/{submission_id}/file")
def get_resolution_submission_file(
    submission_id: PositiveId,
    current_user: dict = Depends(get_current_user),
):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT s.file_path, s.original_filename, s.content_type, s.review_status,
               c.user_id, c.officer_id
        FROM complaint_resolution_submissions s
        JOIN complaints c ON c.id = s.complaint_id
        WHERE s.id = ?
        """,
        (submission_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Resolution attachment not found")
    permitted = (
        current_user["role"] == "admin"
        or (current_user["role"] == "officer" and row[5] == current_user["id"])
        or (
            current_user["role"] == "citizen"
            and row[4] == current_user["id"]
            and row[3] == "approved"
        )
    )
    if not permitted:
        raise HTTPException(status_code=404, detail="Resolution attachment not found")
    file_path = managed_file_path(
        row[0], UPLOADS_DIR, os.path.join(BASE_DIR, "uploads")
    )
    if file_path is None:
        raise HTTPException(status_code=404, detail="Resolution attachment not found")
    return FileResponse(file_path, filename=row[1], media_type=row[2])


@app.put("/update-status/{complaint_id}")
def update_status(
    complaint_id: PositiveId,
    status_update: StatusUpdate,
    current_user: dict = Depends(require_admin),
):
    if status_update.status == "Resolved":
        raise HTTPException(
            status_code=409,
            detail="Approve an officer resolution submission to resolve this complaint",
        )
    
    next_resolution_date = (
        status_update.resolution_date.isoformat()
        if status_update.status == "Resolved"
        else None
    )
    next_resolution_remarks = (
        status_update.remarks if status_update.status == "Resolved" else None
    )

    with db_transaction() as conn:
        conn.execute("BEGIN IMMEDIATE")
        validate_admin_status_transition(
            conn,
            complaint_id,
            status_update.status,
        )
        result = transition_complaint_status(
            conn,
            complaint_id,
            status_update.status,
            current_user,
            status_update.remarks,
            update_resolution=True,
            resolution_date=next_resolution_date,
            resolution_remarks=next_resolution_remarks,
        )
        if not result["updated"]:
            return {
                "message": "Status is unchanged",
                "complaint_id": str(complaint_id),
                "new_status": status_update.status,
            }
        if result["changed"] and result["owner_id"] is not None:
            is_resolution = status_update.status == "Resolved"
            event_title = (
                "Complaint resolved" if is_resolution else "Complaint status updated"
            )
            event_message = (
                f"Your complaint #{complaint_id} has been resolved."
                if is_resolution
                else f"Your complaint #{complaint_id} status is now {status_update.status}."
            )
            conn.execute(
                """
                INSERT INTO notifications
                (user_id, complaint_id, notification_type, title, message, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    result["owner_id"],
                    complaint_id,
                    "complaint_resolved" if is_resolution else "complaint_status_updated",
                    event_title,
                    event_message,
                    result["changed_at"],
                ),
            )

    return {"message": "Status updated successfully", "complaint_id": complaint_id, "new_status": status_update.status}

@app.get("/complaints/filter", response_model=List[ComplaintResponse])
def filter_complaints(
    category: Optional[str] = Query(default=None, max_length=100),
    priority: Optional[str] = Query(default=None, max_length=100),
    current_user: dict = Depends(require_admin),
):
    conn = connect_db()
    cursor = conn.cursor()
    
    query = "SELECT * FROM complaints WHERE 1=1"
    params = []
    
    if category:
        query += " AND category = ?"
        params.append(category)
    
    if priority:
        query += " AND priority = ?"
        params.append(priority)
    
    query += " ORDER BY timestamp DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    complaints = []
    for row in rows:
        complaints.append(ComplaintResponse(
            id=str(row[0]),
            text=row[1],
            category=row[2],
            priority=row[3],
            file_path=row[4],
            latitude=row[5],
            longitude=row[6],
            timestamp=row[8],
            status=row[7]
        ))
    
    return complaints