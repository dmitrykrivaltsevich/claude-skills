# Agent Rules

- Every Python script executed via `uv run` MUST declare the full set of runtime dependencies in its own PEP 723 inline metadata block — including all packages required by locally-imported modules, traced recursively.
- Every change to skill code (scripts, SKILL.md, tests, or references) MUST be accompanied by a version bump in `.claude-plugin/marketplace.json` (`metadata.version`). Patch for fixes, minor for new features, major for breaking changes.
- When adding or modifying a script, MUST trace every local `import`/`from X import Y` to the imported `.py` file and collect all third-party packages it imports at module top level.
- MUST repeat the import trace recursively — if `a.py` imports `b.py` which imports `c.py`, then `a.py`'s PEP 723 block MUST include deps from both `b.py` and `c.py`.
- `uv run` does NOT resolve dependencies from imported `.py` files — only from the entry script. MUST NOT rely on transitive resolution.
- All scripts MUST use PEP 723 inline metadata (`# /// script` blocks), NOT requirements.txt or pyproject.toml.
- All scripts MUST be independently runnable via `uv run script.py` in a clean environment with no pre-installed packages.
- Destructive or irreversible operations MUST set `disable-model-invocation: true` in SKILL.md frontmatter.
- Secrets (tokens, client IDs, client secrets) MUST be stored in macOS Keychain via `keyring`, NEVER on disk.
- Tests MUST follow TDD cycle: write failing tests first (red), then implement to pass (green), then refactor, then verify green again.
- Functions with input constraints MUST enforce them with `@precondition` decorators from `contracts.py`, NOT with ad-hoc `if` checks.
- MUST NOT create global virtual environments or require `pip install` — `uv run` handles isolation.
- SKILL.md `description` MUST use third-person verb form and include when-to-use triggers (e.g. "Use when the user asks about…"). MUST NOT explain implementation details the model already knows (e.g. "scripts run via uv", "credentials stored in Keychain"). SKILL.md `name` SHOULD use gerund form (e.g. "Managing Google Drive").
- After fixing a bug or mistake that reflects a reusable lesson (not task-specific), MUST add a corresponding rule to this file following the same MUST/SHOULD/CAN/NOT style.
