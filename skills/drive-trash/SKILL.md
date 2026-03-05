---
name: google-drive-trash
description: Move Google Drive files to trash or restore them. Requires explicit user confirmation — Claude cannot invoke this autonomously.
allowed-tools:
  - Bash(uv run *)
  - Read
disable-model-invocation: true
user-invocable: true
---

# Google Drive Trash Skill

**⚠️ This skill requires explicit user invocation. Claude will NEVER autonomously trash files.**

## Authentication Status

!"uv run ${CLAUDE_SKILL_DIR}/scripts/auth_status.py"

If NOT_AUTHENTICATED: the user must first set up authentication through the main `drive` skill. This skill shares the same credentials stored in macOS Keychain.

## Operations

### Move File to Trash

Soft-delete a file by moving it to the trash. The file can be restored later.

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/trash.py trash --file-id ID
```

### Restore File from Trash

Restore a previously trashed file.

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/trash.py restore --file-id ID
```

## Safety Notes

- `disable-model-invocation: true` prevents Claude from running trash operations autonomously
- The user must explicitly request trashing or restoring a file
- This skill does NOT permanently delete files — it only moves to/from trash
- Files in trash can be restored for 30 days (Google's default retention)
- All operations support Shared Drives (`supportsAllDrives=True`)
