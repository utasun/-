"""Google Drive アップロード。サービスアカウント認証前提。"""
from __future__ import annotations

import io
import logging
import os
import re
from datetime import datetime

log = logging.getLogger(__name__)


def _service():
    from google.oauth2 import service_account  # type: ignore
    from googleapiclient.discovery import build  # type: ignore

    creds = service_account.Credentials.from_service_account_file(
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _safe_name(s: str, limit: int = 80) -> str:
    s = re.sub(r"[\\/\x00-\x1f:*?\"<>|]+", "_", s).strip()
    return s[:limit] or "untitled"


def _find_or_create_folder(svc, parent_id: str, name: str) -> str:
    q = (
        f"name = '{name}' and '{parent_id}' in parents "
        "and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    res = svc.files().list(q=q, fields="files(id, name)").execute()
    files = res.get("files", [])
    if files:
        return files[0]["id"]
    meta = {
        "name": name,
        "parents": [parent_id],
        "mimeType": "application/vnd.google-apps.folder",
    }
    created = svc.files().create(body=meta, fields="id").execute()
    return created["id"]


def upload_pdf(pdf_bytes: bytes, filename: str, date_folder: str | None = None) -> str | None:
    """Driveにアップロードして webViewLink を返す。失敗時は None。"""
    from googleapiclient.http import MediaIoBaseUpload  # type: ignore

    parent = os.environ.get("GDRIVE_FOLDER_ID")
    if not parent:
        log.warning("GDRIVE_FOLDER_ID not set; skipping Drive upload")
        return None
    try:
        svc = _service()
        date_folder = date_folder or datetime.utcnow().strftime("%Y-%m-%d")
        folder_id = _find_or_create_folder(svc, parent, date_folder)
        media = MediaIoBaseUpload(io.BytesIO(pdf_bytes), mimetype="application/pdf", resumable=False)
        meta = {"name": _safe_name(filename), "parents": [folder_id]}
        created = svc.files().create(
            body=meta, media_body=media, fields="id, webViewLink"
        ).execute()
        return created.get("webViewLink")
    except Exception as e:
        log.warning("Drive upload failed (%s): %s", filename, e)
        return None
