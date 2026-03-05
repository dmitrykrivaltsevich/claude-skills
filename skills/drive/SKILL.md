---
name: google-drive
description: Search, list, download, upload, create, update, share, and manage comments on Google Drive files and folders. Supports both My Drive and Shared Drives.
allowed-tools:
  - Bash(uv run *)
  - Read
  - Write
user-invocable: true
---

# Google Drive Skill

## Authentication Status

!"uv run ${CLAUDE_SKILL_DIR}/scripts/auth_status.py"

## First-Time Setup

If the auth status above shows NOT_AUTHENTICATED, guide the user through these steps:

### Step 1: Register an OAuth Desktop Client

The user must create their own OAuth Desktop application. Walk them through it:

1. Open: https://console.cloud.google.com/apis/credentials
2. Click **"+ CREATE CREDENTIALS"** → **"OAuth client ID"**
3. Application type: **"Desktop app"**
4. Name: anything (e.g. "Claude Drive Skill")
5. Click **Create**
6. Copy the **Client ID** and **Client Secret** shown in the confirmation dialog

If the user does not have a project yet, the credentials page will prompt them to create one — follow the on-screen instructions. Enable the **Google Drive API** if prompted.

### Step 2: Run OAuth Flow

Once the user provides their Client ID and Client Secret:

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/setup_auth.py --client-id "CLIENT_ID_HERE" --client-secret "CLIENT_SECRET_HERE"
```

This opens a browser window for Google sign-in. After authorization, credentials are stored in the macOS Keychain under the service `claude-skill-google-drive`.

## How to Choose the Right Script

Pick the script based on what the user wants. Do NOT blindly default to `search.py` for every request.

| User intent | Script | Why |
|---|---|---|
| **Find files by keyword** (content or name) | `search.py --query "term"` | Searches inside file content AND file/folder names |
| **Complex search** (date range, MIME type, starred, shared, boolean logic) | `search.py --q "raw API query"` | Passes query directly to Drive API — you construct the query syntax |
| **Find a folder or file by its name/path** | `tree.py --name-filter "text"` | Scans folder+file names in the hierarchy; finds things search misses (unindexed PDFs, folder names) |
| **Browse a known folder** | `list_files.py --folder-id ID` | Lists one folder level; use when you already have the folder ID |
| **Explore folder structure** (don't know where something is) | `tree.py --depth N` | Recursive traversal; shows the folder tree so you can locate the right folder |
| **Read/download a file** | `download.py --file-id ID` | Requires file ID (get it from search/list/tree first) |
| **Upload a local file** | `upload.py --file-path PATH` | Uploads from the local filesystem to Drive |
| **Create a new Doc/Sheet/Slide/Folder** | `create.py --name "X" --type Y` | Creates empty Google Workspace items |
| **Rename, move, star, describe** | `update.py --file-id ID` | Metadata changes only (not file content) |
| **Share or manage permissions** | `share.py share/list/remove` | Add/remove/list user permissions on a file |
| **Get detailed file info** | `info.py --file-id ID` | Full metadata: size, owners, permissions, dates, etc. |
| **Read or add comments** | `comments.py list/add/reply` | Google Drive comment threads on a file |

### Finding files — decision logic

1. **User gives a keyword** → start with `search.py --query "keyword"`.
2. **Results insufficient or empty** → try `tree.py --name-filter "keyword"` to check folder/file names.
3. **User mentions a folder name or path** → use `tree.py --name-filter "folder name"` to find the folder ID, then `list_files.py --folder-id ID` to see its contents.
4. **User needs date/type/boolean filtering** → use `search.py --q "modifiedTime > '2025-01-01' and ..."` with raw Drive API query.
5. **User gives a Drive URL** → extract the file/folder ID from the URL and use `list_files.py`, `info.py`, or `download.py` directly.

Do NOT make multiple search calls with different rephrased keywords hoping for better results. Instead, switch strategies: search → tree → list.

## Operations

### Search Files

Search for files across My Drive and Shared Drives. Two modes:

**Simple search** — convenience wrapper, searches both names and content:

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/search.py --query "quarterly report" [--name-only] [--mime-type TYPE] [--folder-id ID] [--shared-drives-only]
```

**Raw query** — pass any Drive API query string directly (no wrapping, no escaping):

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/search.py --q "modifiedTime > '2025-01-01' and name contains 'rent' and mimeType = 'application/pdf'"
```

Use `--q` when you need date ranges, boolean logic, `sharedWithMe`, `starred`, or any combination the Drive API supports. Query syntax reference: https://developers.google.com/drive/api/guides/search-files

### Browse Folder Tree

Recursively list the folder hierarchy. Essential for discovering files organized by folder structure.

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/tree.py [--folder-id ID] [--depth N] [--name-filter TEXT]
```

- `--depth` — how many levels deep to traverse (default: 3)
- `--name-filter` — case-insensitive substring filter on names (still traverses all folders to find deep matches)

### List Folder Contents

List files in a specific folder (defaults to root).

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/list_files.py [--folder-id ID] [--page-size N] [--order-by FIELD]
```

Order options: `name`, `modifiedTime`, `createdTime`, `folder`.

### Download / Export Files

Download regular files or export Google Workspace files (Docs, Sheets, Slides).

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/download.py --file-id ID [--format FMT] [--output-dir DIR]
```

When exporting Google Docs as Markdown (`--format md`), comments and discussions are appended inline at the end of the document. For binary formats (pdf, docx, etc.), comments are printed to stdout.

See the export formats reference at `${CLAUDE_SKILL_DIR}/references/export-formats.md` for all supported format mappings.

### Upload Files

Upload a local file to Google Drive.

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/upload.py --file-path PATH [--folder-id ID]
```

### Create Items

Create a new Google Doc, Sheet, Slide, or Folder.

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/create.py --name "Document Name" --type doc|sheet|slide|folder [--folder-id ID]
```

### Update File Metadata

Rename, move, star, or set description on a file.

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/update.py --file-id ID [--name "New Name"] [--move-to FOLDER_ID] [--star] [--description "text"]
```

### Share Files

Manage file sharing permissions.

```bash
# Share with a user
uv run ${CLAUDE_SKILL_DIR}/scripts/share.py share --file-id ID --email user@example.com --role reader|commenter|writer|organizer

# List permissions
uv run ${CLAUDE_SKILL_DIR}/scripts/share.py list --file-id ID

# Remove a user's access
uv run ${CLAUDE_SKILL_DIR}/scripts/share.py remove --file-id ID --email user@example.com
```

### Get File Info

Retrieve detailed metadata about a file.

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/info.py --file-id ID
```

### Comments & Discussions

List, add comments, and reply to existing comments on files.

```bash
# List all comments
uv run ${CLAUDE_SKILL_DIR}/scripts/comments.py list --file-id ID

# Add a comment
uv run ${CLAUDE_SKILL_DIR}/scripts/comments.py add --file-id ID --content "Your comment text"

# Reply to a comment
uv run ${CLAUDE_SKILL_DIR}/scripts/comments.py reply --file-id ID --comment-id CID --content "Reply text"
```

## Important Notes

- All operations support Shared Drives (`supportsAllDrives=True`)
- This skill does NOT perform permanent deletion — use the `drive-trash` skill to move files to trash
- Credentials are stored in macOS Keychain, not on disk
- All scripts run in isolated environments via `uv` (no global installs needed)
