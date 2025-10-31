# MCP Server Dario

Personal MCP server that exposes a minimal FastAPI application focused on a Facebook Graph API connector and Google Drive utilities.  
It is inspired by the shared internal MCP server but ships with only the Facebook and Drive integrations to keep things lean for personal usage.

## Features
- Fetch profile or page information via `POST /facebook/profile`.
- Retrieve feed posts with advanced filters via `POST /facebook/feed`.
- Publish new posts (immediate or scheduled) with `POST /facebook/posts`.
- List, download, and upload Google Drive files via `/google-drive/*` endpoints.
- Simple health-check endpoint available at `GET /health`.

## Getting Started
The project targets Python 3.11+.

1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy the example environment configuration and fill in your values:
   ```bash
   cp config.example.env .env
   ```
4. Start the FastAPI server:
   ```bash
   uvicorn app.main:app --reload
   ```
5. Access the interactive API docs at http://127.0.0.1:8000/docs

## Configuration
All settings can be provided through `.env` or the environment:

| Variable | Description |
| --- | --- |
| `FACEBOOK_ACCESS_TOKEN` | **Required.** Long-lived user or page access token. |
| `FACEBOOK_GRAPH_API_VERSION` | Graph API version (default `v19.0`). |
| `FACEBOOK_BASE_URL` | Override the Graph API base URL if needed. |
| `FACEBOOK_TIMEOUT` | Timeout in seconds for outbound Facebook requests (default `10`). |
| `FACEBOOK_DEFAULT_FIELDS` | Comma separated default fields when none are provided. |
| `FACEBOOK_DEFAULT_FEED_LIMIT` | Default feed page size (default `25`, max `100`). |
| `FACEBOOK_ENABLE_DEBUG` | Set to `true` to enable verbose logging for troubleshooting. |
| `GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE` | Path to the JSON key for a Google service account with Drive access. |
| `GOOGLE_DRIVE_DELEGATED_USER` | Optional user to impersonate when using domain-wide delegation. |
| `GOOGLE_DRIVE_SCOPES` | JSON array of Drive scopes (default `["https://www.googleapis.com/auth/drive"]`). |
| `GOOGLE_DRIVE_DOWNLOAD_CHUNK_SIZE` | Chunk size in bytes for Drive downloads (default `4194304`). |

## Example Requests

Fetch basic profile information:
```bash
curl -X POST http://127.0.0.1:8000/facebook/profile \
  -H "Content-Type: application/json" \
  -d '{"fields": ["id", "name", "email"]}'
```

Read the latest feed posts:
```bash
curl -X POST http://127.0.0.1:8000/facebook/feed \
  -H "Content-Type: application/json" \
  -d '{"limit": 10}'
```

Create a new post:
```bash
curl -X POST http://127.0.0.1:8000/facebook/posts \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello from my MCP server!",
    "published": true
  }'
```

List Drive files:
```bash
curl -X POST http://127.0.0.1:8000/google-drive/files \
  -H "Content-Type: application/json" \
  -d '{"page_size": 10}'
```

Download a Drive file (Base64 payload in the response):
```bash
curl -X POST http://127.0.0.1:8000/google-drive/files/download \
  -H "Content-Type: application/json" \
  -d '{"file_id": "your-file-id"}'
```

Upload a Drive file from local data:
```bash
curl -X POST http://127.0.0.1:8000/google-drive/files/upload \
  -H "Content-Type: application/json" \
  -d '{
    "name": "hello.txt",
    "mime_type": "text/plain",
    "content_base64": "SGVsbG8gR29vZ2xlIERyaXZlIQ=="
  }'
```

## Development Notes
- The `.mcp_cache` directory is automatically created to mirror the structure of the original MCP server.
- To run the application in production, consider invoking `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- The project bundles Facebook and Google Drive connectors; additional integrations can be added following the same patterns.
