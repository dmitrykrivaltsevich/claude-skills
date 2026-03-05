---
name: google-drive
description: Searches, lists, downloads, uploads, creates, updates, shares, and comments on Google Drive files and folders across My Drive and Shared Drives. Use when the user asks about files in Google Drive, needs documents, spreadsheets, presentations, or any Drive-stored content.
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

If NOT_AUTHENTICATED, guide the user:

1. Open: https://console.cloud.google.com/apis/credentials
2. **"+ CREATE CREDENTIALS"** → **"OAuth client ID"** → **"Desktop app"**
3. Copy the **Client ID** and **Client Secret**

Then run:

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/setup_auth.py --client-id "CLIENT_ID" --client-secret "CLIENT_SECRET"
```

## Choosing the Right Script

| User intent | Script |
|---|---|
| Find files by keyword | `search.py --query "term"` |
| Complex query (date range, MIME, starred, boolean) | `search.py --q "raw Drive API query"` |
| Find folder/file by name in hierarchy | `tree.py --name-filter "text"` |
| Browse a known folder | `list_files.py --folder-id ID` |
| Explore folder structure | `tree.py [--folder-id ID] --depth N` |
| List only PDFs (or other type) in a folder tree | `tree.py --folder-id ID --mime-type application/pdf` |
| Download/export a file | `download.py --file-id ID [--format FMT]` |
| Upload a local file | `upload.py --file-path PATH [--folder-id ID]` |
| Create Doc/Sheet/Slide/Folder | `create.py --name "X" --type doc\|sheet\|slide\|folder` |
| Rename, move, star, describe | `update.py --file-id ID [...]` |
| Share or manage permissions | `share.py share\|list\|remove --file-id ID` |
| List available Shared Drives | `list_drives.py` |
| Get detailed file metadata | `info.py --file-id ID` |
| Read or add comments | `comments.py list\|add\|reply --file-id ID` |

### Finding files — escalation

1. **Keyword** → `search.py --query "keyword"`
2. **Insufficient results** → `tree.py --name-filter "keyword"` (catches folder names, unindexed files)
3. **User mentions a folder/path** → `tree.py --name-filter "name"` to find folder ID, then `list_files.py --folder-id ID`
4. **Date/type/boolean filter needed** → `search.py --q "modifiedTime > '2025-01-01' and ..."`
5. **User gives a Drive URL** → extract ID from URL, use `list_files.py`, `info.py`, or `download.py` directly
6. **Nothing found / no keywords** → broad exploration:
   - `tree.py --depth 2` on My Drive to see top-level structure
   - `list_drives.py` to discover Shared Drives, then `tree.py --folder-id DRIVE_ID --depth 2` on each
   - Present the folder structure to the user so they can point you in the right direction

### Large collections (1000+ files)

When a folder or Shared Drive is large (e.g. a book library, media archive):

- Do NOT `tree.py` without filters — output will be huge and truncated
- Use `search.py --query "keyword" --folder-id ID` to search within the specific folder
- Use `tree.py --folder-id ID --mime-type application/pdf` to narrow by file type
- Try multiple varied keywords: title fragments, author names, subtopics — not just broad topic words
- PDF content search is unreliable on Drive (scanned/large PDFs may not be indexed) — always also try `--name-only` or `tree.py --name-filter`

Do NOT rephrase the same keyword hoping for better results. Switch strategies instead.

## Script Reference

### search.py

```bash
# Simple keyword search (searches name + content):
uv run ${CLAUDE_SKILL_DIR}/scripts/search.py --query "text" [--name-only] [--mime-type TYPE] [--folder-id ID]

# Raw Drive API query (you construct the full query):
uv run ${CLAUDE_SKILL_DIR}/scripts/search.py --q "modifiedTime > '2025-01-01' and name contains 'rent'"
```

`--query` and `--q` are mutually exclusive. Use `--q` for anything beyond simple keyword search. Query syntax: https://developers.google.com/drive/api/guides/search-files

### tree.py

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/tree.py [--folder-id ID] [--depth N] [--name-filter TEXT] [--mime-type TYPE]
```

### list_files.py

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/list_files.py [--folder-id ID] [--page-size N] [--order-by FIELD]
```

### list_drives.py

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/list_drives.py [--page-size N]
```

Returns all Shared Drives accessible to the user (id, name, createdTime).

### download.py

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/download.py --file-id ID [--format FMT] [--output-dir DIR]
```

For Google Docs export as Markdown (`--format md`), comments are appended inline. For binary formats, comments print to stdout. See [export-formats.md](references/export-formats.md) for supported format mappings.

### upload.py

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/upload.py --file-path PATH [--folder-id ID]
```

### create.py

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/create.py --name "Name" --type doc|sheet|slide|folder [--folder-id ID]
```

### update.py

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/update.py --file-id ID [--name "New Name"] [--move-to FOLDER_ID] [--star] [--description "text"]
```

### share.py

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/share.py share --file-id ID --email EMAIL --role reader|commenter|writer|organizer
uv run ${CLAUDE_SKILL_DIR}/scripts/share.py list --file-id ID
uv run ${CLAUDE_SKILL_DIR}/scripts/share.py remove --file-id ID --email EMAIL
```

### info.py

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/info.py --file-id ID
```

### comments.py

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/comments.py list --file-id ID
uv run ${CLAUDE_SKILL_DIR}/scripts/comments.py add --file-id ID --content "text"
uv run ${CLAUDE_SKILL_DIR}/scripts/comments.py reply --file-id ID --comment-id CID --content "text"
```
