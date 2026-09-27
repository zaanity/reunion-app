from __future__ import annotations

import re
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from .config import settings

SCOPES = ["https://www.googleapis.com/auth/drive"]
FOLDER_MIME = "application/vnd.google-apps.folder"


def _resolve_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parents[1] / path


def _service():
    token_path = _resolve_path(settings.google_drive_token_file)
    credentials_path = _resolve_path(settings.google_drive_credentials_file)

    if not credentials_path.is_file():
        raise FileNotFoundError(
            f"Google OAuth client credentials not found: {credentials_path}"
        )
    if not token_path.is_file():
        raise FileNotFoundError(
            f"Google Drive OAuth token not found: {token_path}. "
            "Run: python authorize_drive.py"
        )

    credentials = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        token_path.write_text(credentials.to_json(), encoding="utf-8")

    if not credentials.valid:
        raise RuntimeError(
            "Google Drive authorization is invalid or expired. "
            "Run: python authorize_drive.py"
        )

    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def sanitize_folder_name(name: str) -> str:
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[: settings.max_name_length]


def sanitize_filename(filename: str) -> str:
    name = Path(filename or "memory-file").name
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    name = re.sub(r"[\\/:*?\"<>|]", "_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return (name or "memory-file")[: settings.max_filename_length]


def _escape_drive_query_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def get_or_create_user_folder(user_name: str, contributor_id: str) -> tuple[str, str]:
    """Use a stable browser-generated contributor ID to avoid same-name collisions."""
    service = _service()
    readable_name = sanitize_folder_name(user_name)
    folder_name = f"{readable_name}__{contributor_id[:8]}"
    parent_id = settings.google_drive_parent_folder_id

    escaped = _escape_drive_query_value(folder_name)
    query = (
        f"name = '{escaped}' and '{parent_id}' in parents and "
        f"mimeType = '{FOLDER_MIME}' and trashed = false"
    )
    result = (
        service.files()
        .list(q=query, spaces="drive", fields="files(id,name)", pageSize=10)
        .execute()
    )
    folders = result.get("files", [])
    if folders:
        return folders[0]["id"], folders[0]["name"]

    metadata = {
        "name": folder_name,
        "mimeType": FOLDER_MIME,
        "parents": [parent_id],
        "appProperties": {
            "source": "samaagam-2026-memory-drop",
            "uploader_name": readable_name,
            "contributor_id": contributor_id,
        },
    }
    folder = service.files().create(body=metadata, fields="id,name").execute()
    return folder["id"], folder["name"]


def upload_file(
    folder_id: str,
    filename: str,
    content_type: str,
    file_obj,
    uploader_name: str,
    contributor_id: str,
) -> str:
    service = _service()
    safe_filename = sanitize_filename(filename)
    metadata = {
        "name": safe_filename,
        "parents": [folder_id],
        "appProperties": {
            "source": "samaagam-2026-memory-drop",
            "uploader_name": uploader_name,
            "contributor_id": contributor_id,
        },
    }
    file_obj.seek(0)
    media = MediaIoBaseUpload(
        file_obj,
        mimetype=content_type or "application/octet-stream",
        resumable=True,
        chunksize=8 * 1024 * 1024,
    )
    created = (
        service.files()
        .create(body=metadata, media_body=media, fields="id,name,size")
        .execute()
    )
    return created["id"]
