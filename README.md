# Samaagam Memory Drop — Next.js + FastAPI

A public alumni media drop page for Samaagam 2026. Alumni enter their name and upload original photos/videos. FastAPI uploads the files into the owner's personal Google Drive using OAuth.

## Architecture

```text
Alumni browser
    ↓
Next.js
    ↓ multipart upload
FastAPI
    ↓ OAuth refresh token
Owner's Google Drive
    ↓
Samaagam 2026 Memory Drop/
    ├── Name__unique-id/
    └── ...
```

## Google authentication

This project does **not** use a service account for storage. `authorize_drive.py` performs a one-time OAuth authorization for the owner's personal Google account. `token.json` is then used by the backend and refreshed automatically.

Keep these private and never commit them:

- `backend/credentials/credentials.json`
- `backend/token.json`
- `backend/.env`

## Local setup

### Backend

```powershell
cd backend
pip install -r requirements.txt
python authorize_drive.py
```

Create `.env`:

```env
GOOGLE_DRIVE_CREDENTIALS_FILE=credentials/credentials.json
GOOGLE_DRIVE_TOKEN_FILE=token.json
GOOGLE_DRIVE_PARENT_FOLDER_ID=YOUR_FOLDER_ID
FRONTEND_ORIGIN=http://localhost:3000
MAX_FILE_SIZE_MB=500
MAX_FILES_PER_REQUEST=50
MAX_TOTAL_UPLOAD_MB=2048
MAX_NAME_LENGTH=120
MAX_FILENAME_LENGTH=180
RATE_LIMIT_REQUESTS=20
RATE_LIMIT_WINDOW_SECONDS=3600
RATE_LIMIT_FILES=120
RATE_LIMIT_FILE_WINDOW_SECONDS=3600
MAX_CONCURRENT_UPLOADS=3
APP_ENV=development
ENABLE_DOCS=true
```

Test Drive:

```powershell
python test_drive.py
```

Start API:

```powershell
uvicorn app.main:app --reload
```

### Frontend

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

Then:

```powershell
cd frontend
npm install
npm run dev
```

## Security hardening included

- Allowed MIME types only.
- Server-side magic-byte checks for supported formats.
- Per-file size limit.
- Total request upload limit.
- Maximum file count.
- Per-IP request/file rate limits for the single-process deployment.
- Maximum concurrent Drive upload operations.
- Filename sanitization.
- Contributor UUID stored in browser local storage so two visitors with the same name do not share a Drive folder.
- Google credentials remain server-side.
- CORS restricted to the configured frontend origin.
- No Drive browsing/download endpoint is exposed.
- Resumable Drive uploads avoid loading the entire file into Python RAM.

## Important production note

The in-memory rate limiter is appropriate for a single FastAPI instance. If you deploy multiple backend instances or workers, use a shared Redis-backed limiter. Also put the API behind HTTPS and a reverse proxy with a request-body limit appropriate for the configured upload size.

For a public event launch, consider adding CAPTCHA or another anti-abuse mechanism if the endpoint is exposed broadly on the internet.
