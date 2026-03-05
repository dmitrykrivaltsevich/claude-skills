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

## Operations

### Search Files

Search for files across My Drive and Shared Drives. By default searches both file/folder **names** and full-text content.

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/search.py --query "quarterly report" [--name-only] [--mime-type TYPE] [--folder-id ID] [--shared-drives-only]
```

- `--name-only` — match file/folder name only, skip content search (faster, less noise)

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

## Search Strategy

When looking for files on a user's Drive, do NOT rely on `search.py` alone. Google Drive full-text search only indexes file *content* — it misses folder names and files whose content isn't indexed (some PDFs, images, etc.).

**Recommended approach:**
1. Start with `search.py --query "term"` — this searches both names and content.
2. If results are insufficient, use `tree.py --name-filter "term"` to scan folder names and file titles in the hierarchy.
3. If the user mentions a folder or path, use `tree.py --folder-id ID` or `list_files.py --folder-id ID` to browse directly.
4. Combine strategies: search for content, then browse folder structure to find organizational context.

Never give up after a single search — users organize files in folders, and the folder names often contain the key context.

## Important Notes

- All operations support Shared Drives (`supportsAllDrives=True`)
- This skill does NOT perform permanent deletion — use the `drive-trash` skill to move files to trash
- Credentials are stored in macOS Keychain, not on disk
- All scripts run in isolated environments via `uv` (no global installs needed)
