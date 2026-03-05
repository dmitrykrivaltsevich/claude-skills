# Google Drive Skill

Search, list, download/export, upload, create, update, share, and comment on Google Drive files and folders. Supports both My Drive and Shared Drives.

## First-Time Authentication

Each user registers their own OAuth Desktop client:

1. Go to https://console.cloud.google.com/apis/credentials
2. Click **"+ CREATE CREDENTIALS"** → **"OAuth client ID"**
3. Application type: **Desktop app**
4. Copy the **Client ID** and **Client Secret**
5. Claude will guide you through running the auth setup script

Credentials are stored securely in macOS Keychain (service: `claude-skill-google-drive`) — never on disk.

## Operations

| Script | Purpose |
|--------|---------|
| `search.py` | Full-text search across My Drive and Shared Drives |
| `list_files.py` | List folder contents with pagination and ordering |
| `download.py` | Download/export files with inline comments |
| `upload.py` | Upload local files |
| `create.py` | Create Docs, Sheets, Slides, Folders |
| `update.py` | Rename, move, star, set description |
| `share.py` | Manage sharing permissions |
| `info.py` | Get detailed file metadata |
| `comments.py` | List, add, and reply to comments |
| `setup_auth.py` | Browser-based OAuth flow |
| `auth_status.py` | Dynamic context: auth check |

See [references/export-formats.md](references/export-formats.md) for all supported Google Workspace export format mappings.

## Architecture

```
SKILL.md                    # Claude runtime instructions (frontmatter + ops)
references/
  export-formats.md         # Export format reference table
scripts/
  contracts.py              # Design by Contract decorators
  auth.py                   # Keychain credential management
  auth_status.py            # Dynamic context: auth check
  setup_auth.py             # Browser-based OAuth flow
  search.py                 # Search Drive files
  list_files.py             # List folder contents
  download.py               # Download/export with inline comments
  upload.py                 # Upload local files
  create.py                 # Create Docs/Sheets/Slides/Folders
  update.py                 # Rename, move, star, describe
  share.py                  # Manage sharing permissions
  info.py                   # Get file metadata
  comments.py               # List/add comments & replies
tests/                      # 80 unit tests
```

## Technical Details

- **Python** ≥3.11 — all scripts use PEP 723 inline metadata
- **Runtime** — `uv run` for isolated, sandboxed execution (no global installs)
- **Auth** — Google OAuth 2.0 Desktop flow via `google-auth-oauthlib`, `InstalledAppFlow.from_client_config()`
- **Storage** — macOS Keychain via `keyring` library
- **API** — Google Drive API v3, `supportsAllDrives=True` on all calls
- **Scope** — `https://www.googleapis.com/auth/drive` (full read/write, no delete)
- **Testing** — Design by Contract (DbC) + TDD — 80 unit tests

## Running Tests

```bash
uv run --with pytest --with pytest-mock --with google-auth --with google-auth-oauthlib \
  --with google-auth-httplib2 --with google-api-python-client --with keyring \
  pytest tests/ -v
```
