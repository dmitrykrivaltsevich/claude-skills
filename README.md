# claude-skills

A collection of skills (plugins) for [Claude Code](https://code.claude.com/docs/en/plugins). Each skill extends Claude with domain-specific capabilities — API integrations, workflows, tooling.

## Installation

### From GitHub (marketplace)

```
/plugin marketplace add dmitrykrivaltsevich/claude-skills
```

Then install individual plugins:

```
/plugin install google-drive@dmitrykrivaltsevich-claude-skills
```

### From a local clone

```bash
git clone https://github.com/dmitrykrivaltsevich/claude-skills.git
claude --plugin-dir ./claude-skills
```

### From a Git URL

```
/plugin marketplace add https://github.com/dmitrykrivaltsevich/claude-skills.git
```

See the [Claude Code plugin docs](https://code.claude.com/docs/en/discover-plugins) for all installation methods and scopes (user / project / local).

## Skills

| Skill | Description |
|-------|-------------|
| [google-drive](skills/drive/) | Search, list, download/export, upload, create, update, share, and comment on Google Drive files. Supports My Drive and Shared Drives. |
| [google-drive-trash](skills/drive-trash/) | Move files to trash or restore them. Requires explicit user confirmation (`disable-model-invocation: true`). |

See each skill's README for setup, architecture, and test instructions.

## License

MIT
