# Google Drive Skill for Claude Code

A Claude Code plugin that provides comprehensive Google Drive integration — search, list, download, upload, create, update, share, comment, and trash operations.

## Quick Start

### Install as a Claude Code Plugin

```bash
claude --plugin-dir /path/to/this/repo
```

Or add to your Claude Code settings for persistent use.

### First-Time Authentication

Each user registers their own OAuth Desktop client:

1. Go to https://console.cloud.google.com/apis/credentials
2. Create an **OAuth client ID** → **Desktop app**
3. Copy the Client ID and Client Secret
4. Claude will guide you through running the auth setup script

Credentials are stored securely in macOS Keychain — never on disk.

## Skills

### `drive` — Full Drive Operations

- **Search** files by text content, MIME type, or folder
- **List** folder contents with pagination and ordering
- **Download/Export** files with inline comments (Google Docs → Markdown with comments appended)
- **Upload** local files to Drive
- **Create** Google Docs, Sheets, Slides, and Folders
- **Update** file metadata (rename, move, star, describe)
- **Share** files and manage permissions
- **Comments** — list, add, and reply to comments
- **Info** — detailed file metadata

### `drive-trash` — Trash Operations (User-Confirmed Only)

- **Trash** — move files to trash (soft delete)
- **Restore** — recover files from trash

This skill has `disable-model-invocation: true` — Claude will never autonomously trash your files.

## Architecture

```
.claude-plugin/
  marketplace.json          # Plugin catalog

skills/
  drive/
    SKILL.md                # Main skill definition
    references/
      export-formats.md     # Export format reference
    scripts/
      contracts.py          # Design by Contract decorators
      auth.py               # Keychain credential management
      auth_status.py        # Dynamic context: auth check
      setup_auth.py         # Browser-based OAuth flow
      search.py             # Search Drive files
      list_files.py         # List folder contents
      download.py           # Download/export with inline comments
      upload.py             # Upload local files
      create.py             # Create Docs/Sheets/Slides/Folders
      update.py             # Rename, move, star, describe
      share.py              # Manage sharing permissions
      info.py               # Get file metadata
      comments.py           # List/add comments & replies
    tests/                  # 80 unit tests (TDD)

  drive-trash/
    SKILL.md                # Trash skill (disable-model-invocation)
    scripts/
      contracts.py          # DbC decorators (shared)
      auth.py               # Keychain auth (shared)
      auth_status.py        # Auth status check (shared)
      trash.py              # Trash & restore operations
    tests/                  # 6 unit tests
```

## Technical Details

- **Python**: ≥3.11, all scripts use PEP 723 inline metadata
- **Runtime**: `uv run` for isolated, sandboxed execution (no global installs)
- **Auth**: Google OAuth 2.0 Desktop flow via `google-auth-oauthlib`
- **Storage**: macOS Keychain via `keyring` library
- **API**: Google Drive API v3 with `supportsAllDrives=True` on all calls
- **Testing**: Design by Contract (DbC) + TDD — 86 tests total
- **Scope**: `https://www.googleapis.com/auth/drive` (full read/write, no delete)

## Running Tests

```bash
uv run --with pytest --with pytest-mock --with google-auth --with google-auth-oauthlib \
  --with google-auth-httplib2 --with google-api-python-client --with keyring \
  pytest skills/ -v
```

## License

MIT
