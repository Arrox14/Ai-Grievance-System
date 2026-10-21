import os
import tempfile
import uuid

from fastapi import HTTPException, UploadFile


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
UPLOAD_TYPES = {
    ".jpg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ".jpeg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ".png": ("image/png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    ".gif": (
        "image/gif",
        lambda data: data.startswith((b"GIF87a", b"GIF89a")),
    ),
    ".bmp": ("image/bmp", lambda data: data.startswith(b"BM")),
    ".mp4": (
        "video/mp4",
        lambda data: len(data) >= 12 and data[4:8] == b"ftyp",
    ),
    ".mov": (
        "video/quicktime",
        lambda data: len(data) >= 12
        and data[4:8] == b"ftyp"
        and data[8:12] in (b"qt  ", b"moov", b"wide"),
    ),
    ".avi": (
        "video/x-msvideo",
        lambda data: len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"AVI ",
    ),
}


def safe_upload_path(
    filename: str,
    upload_dir: str,
    allowed_types=UPLOAD_TYPES,
) -> tuple[str, str]:
    extension = os.path.splitext(filename)[1].lower()
    if extension not in allowed_types:
        raise HTTPException(status_code=400, detail="File type not supported")
    os.makedirs(upload_dir, exist_ok=True)
    final_path = os.path.abspath(os.path.join(upload_dir, f"{uuid.uuid4().hex}{extension}"))
    root = os.path.realpath(upload_dir)
    common = os.path.commonpath((root, os.path.realpath(final_path)))
    if os.path.normcase(common) != os.path.normcase(root):
        raise HTTPException(status_code=400, detail="Invalid upload path")
    return extension, final_path


async def save_upload(
    file: UploadFile,
    filename: str,
    upload_dir: str,
    allowed_types=UPLOAD_TYPES,
) -> tuple[str, str, int]:
    extension, final_path = safe_upload_path(filename, upload_dir, allowed_types)
    expected_type, signature_check = allowed_types[extension]
    supplied_type = (file.content_type or "").lower()
    if supplied_type not in (expected_type, "application/octet-stream"):
        raise HTTPException(status_code=400, detail="File content type does not match its extension")

    temporary_path = None
    try:
        contents = await file.read(MAX_UPLOAD_BYTES + 1)
        if not contents:
            raise HTTPException(status_code=400, detail="File cannot be empty")
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File must be 10 MB or smaller")
        if not signature_check(contents):
            raise HTTPException(status_code=400, detail="File content does not match its extension")

        descriptor, temporary_path = tempfile.mkstemp(
            prefix=".upload-", suffix=".tmp", dir=os.path.dirname(final_path)
        )
        with os.fdopen(descriptor, "wb") as output:
            written = output.write(contents)
            output.flush()
            os.fsync(output.fileno())
            if written != len(contents):
                raise OSError("Incomplete upload write")
        os.replace(temporary_path, final_path)
        temporary_path = None
        return final_path, expected_type, len(contents)
    except Exception:
        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)
        if os.path.exists(final_path):
            os.remove(final_path)
        raise


def managed_file_path(path: str, upload_dir: str, legacy_upload_dir: str) -> str | None:
    if not path:
        return None
    resolved_path = os.path.realpath(path)
    for directory in (upload_dir, legacy_upload_dir):
        root = os.path.realpath(directory)
        try:
            common = os.path.commonpath((root, resolved_path))
            if (
                os.path.normcase(common) == os.path.normcase(root)
                and os.path.isfile(resolved_path)
            ):
                return resolved_path
        except ValueError:
            continue
    return None
