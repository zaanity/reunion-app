from __future__ import annotations

import logging
import time
import threading
import uuid
from collections import defaultdict, deque
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .drive import get_or_create_user_folder, sanitize_folder_name, upload_file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("samaagam-memory-drop")

DOCS = "/docs" if settings.enable_docs else None
REDOC = "/redoc" if settings.enable_docs else None
OPENAPI = "/openapi.json" if settings.enable_docs else None

app = FastAPI(
    title="Samaagam Memory Drop API",
    version="1.2.0",
    docs_url=DOCS,
    redoc_url=REDOC,
    openapi_url=OPENAPI,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=False,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["content-type"],
)

ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "video/mp4",
    "video/quicktime",
    "video/webm",
}

# Signatures are checked server-side so a client cannot simply rename an arbitrary
# file to .jpg/.mp4 and bypass the MIME check.
MAGIC = {
    "image/jpeg": lambda b: b.startswith(b"\xff\xd8\xff"),
    "image/png": lambda b: b.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/webp": lambda b: len(b) >= 12 and b[:4] == b"RIFF" and b[8:12] == b"WEBP",
    "video/webm": lambda b: b.startswith(b"\x1a\x45\xdf\xa3"),
    "video/mp4": lambda b: len(b) >= 12 and b[4:8] == b"ftyp",
    "video/quicktime": lambda b: len(b) >= 12 and b[4:8] == b"ftyp",
}

_rate_lock = threading.Lock()
_request_history: dict[str, deque[float]] = defaultdict(deque)
_file_history: dict[str, deque[tuple[float, int]]] = defaultdict(deque)
_upload_semaphore = threading.BoundedSemaphore(settings.max_concurrent_uploads)


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _trim_rate_history(now: float, key: str) -> None:
    requests = _request_history[key]
    while requests and now - requests[0] > settings.rate_limit_window_seconds:
        requests.popleft()
    files = _file_history[key]
    while files and now - files[0][0] > settings.rate_limit_file_window_seconds:
        files.popleft()


def _check_rate_limit(request: Request, file_count: int) -> None:
    key = _client_key(request)
    now = time.time()
    with _rate_lock:
        _trim_rate_history(now, key)
        if len(_request_history[key]) >= settings.rate_limit_requests:
            raise HTTPException(
                status_code=429,
                detail="Too many upload attempts from this connection. Please try again later.",
            )
        used_files = sum(item[1] for item in _file_history[key])
        if used_files + file_count > settings.rate_limit_files:
            raise HTTPException(
                status_code=429,
                detail="The upload limit for this connection has been reached. Please try again later.",
            )
        _request_history[key].append(now)
        _file_history[key].append((now, file_count))


def _get_upload_size(upload: UploadFile) -> int:
    upload.file.seek(0, 2)
    size = upload.file.tell()
    upload.file.seek(0)
    return size


def _validate_uuid(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid contributor identifier.")


def _validate_magic(upload: UploadFile, content_type: str) -> None:
    upload.file.seek(0)
    header = upload.file.read(32)
    upload.file.seek(0)
    validator = MAGIC[content_type]
    if not validator(header):
        raise HTTPException(
            status_code=400,
            detail=f"{upload.filename or 'A file'} does not match its declared file type.",
        )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/memory-drop")
async def memory_drop(
    request: Request,
    user_name: Annotated[str, Form(...)],
    contributor_id: Annotated[str, Form(...)],
    files: Annotated[list[UploadFile], File(...)],
):
    name = sanitize_folder_name(user_name)
    contributor_id = _validate_uuid(contributor_id)

    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Please enter a valid name.")
    if len(files) == 0:
        raise HTTPException(status_code=400, detail="Please select at least one file.")
    if len(files) > settings.max_files_per_request:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {settings.max_files_per_request} files per upload.",
        )

    _check_rate_limit(request, len(files))
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    max_total_bytes = settings.max_total_upload_mb * 1024 * 1024
    total_size = 0

    try:
        for upload in files:
            content_type = (upload.content_type or "").lower()
            if content_type not in ALLOWED_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {content_type or 'unknown'}",
                )
            size = _get_upload_size(upload)
            if size == 0:
                raise HTTPException(status_code=400, detail=f"{upload.filename or 'A file'} is empty.")
            if size > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"{upload.filename or 'A file'} exceeds the {settings.max_file_size_mb} MB per-file limit.",
                )
            total_size += size
            if total_size > max_total_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"The total upload exceeds the {settings.max_total_upload_mb} MB request limit.",
                )
            _validate_magic(upload, content_type)

        acquired = _upload_semaphore.acquire(timeout=5)
        if not acquired:
            raise HTTPException(
                status_code=503,
                detail="The upload server is busy. Please try again in a moment.",
            )

        try:
            folder_id, folder_name = get_or_create_user_folder(name, contributor_id)
            uploaded_ids: list[str] = []
            for upload in files:
                drive_id = upload_file(
                    folder_id=folder_id,
                    filename=upload.filename or "memory-file",
                    content_type=upload.content_type or "application/octet-stream",
                    file_obj=upload.file,
                    uploader_name=name,
                    contributor_id=contributor_id,
                )
                uploaded_ids.append(drive_id)
        finally:
            _upload_semaphore.release()

        logger.info(
            "Memory drop uploaded | user=%s | contributor=%s | files=%d | bytes=%d",
            name,
            contributor_id,
            len(uploaded_ids),
            total_size,
        )
        return {
            "success": True,
            "uploaded": len(uploaded_ids),
            "folder_name": name,
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("Memory drop upload failed for user=%s", name)
        raise HTTPException(
            status_code=500,
            detail="The memory drop could not be completed. Please try again.",
        )
    finally:
        for upload in files:
            await upload.close()
