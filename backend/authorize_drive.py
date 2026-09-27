"""
One-time Google Drive OAuth authorization for Samaagam Memory Drop.

Run from the backend directory:

    python authorize_drive.py

This opens a browser and asks you to authorize the Google account whose
Drive should receive the alumni uploads.

Files:
    credentials/credentials.json  -> OAuth client credentials downloaded
                                     from Google Cloud Console
    token.json                    -> generated after successful authorization

DO NOT commit either file to Git.
"""

from pathlib import Path
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


BASE_DIR = Path(__file__).resolve().parent

CLIENT_SECRET_FILE = BASE_DIR / "credentials" / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"

# Full Drive access is required because the application creates folders
# and uploads media into your personal Google Drive.
SCOPES = ["https://www.googleapis.com/auth/drive"]


def main() -> None:
    if not CLIENT_SECRET_FILE.is_file():
        print()
        print("ERROR: OAuth credentials file was not found.")
        print()
        print(f"Expected location:")
        print(f"  {CLIENT_SECRET_FILE}")
        print()
        print("Download the OAuth Desktop App JSON from Google Cloud")
        print("and rename it to:")
        print("  credentials.json")
        print()
        sys.exit(1)

    credentials = None

    # Reuse an existing token if one has already been generated.
    if TOKEN_FILE.is_file():
        try:
            credentials = Credentials.from_authorized_user_file(
                str(TOKEN_FILE),
                SCOPES,
            )
        except Exception as exc:
            print(f"Existing token could not be read: {exc}")
            print("A fresh authorization will be started.")

    # Refresh an expired token when possible.
    if credentials and credentials.expired and credentials.refresh_token:
        try:
            print("Refreshing existing Google Drive authorization...")
            credentials.refresh(Request())
        except Exception as exc:
            print(f"Token refresh failed: {exc}")
            print("Starting a fresh authorization.")

    # Start browser-based OAuth if there is no usable authorization.
    if not credentials or not credentials.valid:
        print()
        print("Opening your browser for Google authorization...")
        print("Sign in with the Google account whose Drive will store")
        print("the Samaagam alumni photos and videos.")
        print()

        flow = InstalledAppFlow.from_client_secrets_file(
            str(CLIENT_SECRET_FILE),
            SCOPES,
        )

        credentials = flow.run_local_server(
            port=0,
            access_type="offline",
            prompt="consent",
        )

    # Save the credentials for the FastAPI backend.
    TOKEN_FILE.write_text(
        credentials.to_json(),
        encoding="utf-8",
    )

    print()
    print("=" * 60)
    print("GOOGLE DRIVE AUTHORIZATION SUCCESSFUL")
    print("=" * 60)
    print()
    print(f"Token saved to:")
    print(f"  {TOKEN_FILE}")
    print()
    print("Your FastAPI backend can now use your personal Google Drive")
    print("without asking you to log in for every upload.")
    print()
    print("IMPORTANT:")
    print("  - Keep token.json private.")
    print("  - Keep credentials/credentials.json private.")
    print("  - Do not commit either file to Git.")
    print()


if __name__ == "__main__":
    main()
