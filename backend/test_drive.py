"""Verify that the backend can access the configured personal Google Drive."""

from app.config import settings
from app.drive import _service


def main() -> None:
    service = _service()

    about = (
        service.about()
        .get(fields="user(displayName,emailAddress),storageQuota(limit,usage)")
        .execute()
    )

    user = about.get("user", {})
    quota = about.get("storageQuota", {})

    print("Google Drive connection: OK")
    print(f"Authorized account: {user.get('displayName', 'Unknown')}")
    print(f"Email: {user.get('emailAddress', 'Unknown')}")

    usage = quota.get("usage")
    limit = quota.get("limit")
    if usage:
        print(f"Storage used: {int(usage) / (1024**3):.2f} GB")
    if limit:
        print(f"Storage limit: {int(limit) / (1024**3):.2f} GB")

    folder_id = settings.google_drive_parent_folder_id
    folder = (
        service.files()
        .get(fileId=folder_id, fields="id,name,mimeType,trashed")
        .execute()
    )

    if folder.get("trashed"):
        raise RuntimeError("Configured parent folder is in Trash.")

    if folder.get("mimeType") != "application/vnd.google-apps.folder":
        raise RuntimeError("Configured parent ID is not a Drive folder.")

    print(f"Parent folder: {folder['name']}")
    print(f"Parent folder ID: {folder['id']}")
    print("Drive setup is ready for uploads.")


if __name__ == "__main__":
    main()
