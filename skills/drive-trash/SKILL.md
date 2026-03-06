---
name: google-drive-trash
description: Moves Google Drive files to trash or restores them. Use when the user explicitly asks to delete or restore a Drive file. Does not permanently delete — files stay in trash for 30 days.
allowed-tools:
  - Bash(uv run *)
  - Read
disable-model-invocation: true
user-invocable: true
---

# Google Drive Trash Skill

## Authentication Status

!"uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/auth_status.py"

If NOT_AUTHENTICATED: set up authentication through the main `drive` skill first (shared credentials).

## Operations

```bash
# Move to trash
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/trash.py trash --file-id ID

# Restore from trash
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/trash.py restore --file-id ID
```
