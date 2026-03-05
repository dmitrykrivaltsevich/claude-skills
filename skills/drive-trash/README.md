# Google Drive Trash Skill

Move Google Drive files to trash or restore them. Requires explicit user confirmation — Claude cannot invoke this autonomously (`disable-model-invocation: true`).

## Authentication

This skill shares credentials with the main [google-drive](../drive/) skill. Set up authentication there first.

## Operations

| Script | Purpose |
|--------|---------|
| `trash.py trash` | Move a file to trash (soft delete) |
| `trash.py restore` | Restore a file from trash |

## Architecture

```
SKILL.md                    # Claude runtime instructions (disable-model-invocation: true)
scripts/
  contracts.py              # Design by Contract decorators
  auth.py                   # Keychain credential management (shared service)
  auth_status.py            # Dynamic context: auth check
  trash.py                  # Trash & restore operations
tests/                      # 6 unit tests
```

## Safety

- `disable-model-invocation: true` — Claude will never autonomously trash files
- Only soft-deletes (moves to trash) — no permanent deletion
- Trashed files can be restored for 30 days (Google's default retention)
- All operations support Shared Drives (`supportsAllDrives=True`)

## Running Tests

```bash
uv run --with pytest --with pytest-mock --with google-auth --with google-auth-oauthlib \
  --with google-auth-httplib2 --with google-api-python-client --with keyring \
  pytest tests/ -v
```
