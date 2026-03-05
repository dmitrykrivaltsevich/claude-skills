# claude-skills

A collection of skills (plugins) for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Each skill extends Claude with domain-specific capabilities — API integrations, workflows, tooling.

## Usage

```bash
claude --plugin-dir /path/to/this/repo
```

## Skills

| Skill | Description |
|-------|-------------|
| [google-drive](skills/drive/SKILL.md) | Search, list, download/export, upload, create, update, share, and comment on Google Drive files. Supports My Drive and Shared Drives. |
| [google-drive-trash](skills/drive-trash/SKILL.md) | Move files to trash or restore them. Requires explicit user confirmation (`disable-model-invocation: true`). |

## Conventions

Every skill in this repo follows the same structure and principles:

- **SKILL.md** at the skill root — frontmatter defines name, allowed tools, and invocation rules
- **scripts/** — standalone Python scripts with [PEP 723](https://peps.python.org/pep-0723/) inline metadata, executed via `uv run` (no global installs)
- **tests/** — unit tests following strict TDD (red → green → refactor → green)
- **Design by Contract** — `@precondition`, `@postcondition`, `@invariant` decorators enforce runtime contracts
- **macOS Keychain** — secrets stored via `keyring`, never on disk
- **`.claude-plugin/marketplace.json`** — plugin catalog at repo root (`strict: false`)

## Running Tests

```bash
uv run --with pytest --with pytest-mock --with google-auth --with google-auth-oauthlib \
  --with google-auth-httplib2 --with google-api-python-client --with keyring \
  pytest skills/ -v
```

## License

MIT
