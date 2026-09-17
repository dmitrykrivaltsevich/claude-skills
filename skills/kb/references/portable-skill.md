# Portable Skill — every KB carries its own kb skill

`kb:init` vendors the skill into the KB so any harness works with zero
install: clone the repo, open it, the skill is already there. Nothing to
install, nothing to configure.

## Layout (created by init, all paths repo-relative)

- `.agents/skills/kb/` — the ONE real copy (`SKILL.md` + `scripts/` +
  `references/`, stamped with the skill version in `.vendor.json`).
  OpenCode, pi, Codex and Copilot read `.agents/skills/` natively.
- `.claude/skills/kb` → `../../.agents/skills/kb` — relative symlink
  (git preserves it on clone) for Claude Code, which reads `.claude/`.
- `.github/agents/kb.agent.md` — Copilot custom agent: a stub pointing at
  the vendored `SKILL.md`, so Copilot has an agent that knows the skill
  immediately. Never edit the vendored copy; it is replaced on refresh.

## Harness matrix (observed — update this table, not folklore)

| Harness | Reads `.agents/skills` natively | Alias needed | Dupes? |
|---|---|---|---|
| OpenCode | yes | no | no |
| pi | yes | no | no |
| Codex | yes (repo scope) | no | no |
| Copilot (VS Code/CLI/cloud) | yes | no | lists `kb` twice (also reads `.claude/`) — cosmetic, same files |
| Claude Code | no | `.claude` symlink | no |
| github.com (web) | n/a (files browsable) | no | no |

Copilot *code review on GitHub* only reads `.github/skills/` — deliberately
not aliased (a third registration for zero KB-review value). If that changes,
add the row to `ALIASES` in `vendor_skill.py`.

## Staleness (explicit, never silent)

The stamp freezes the skill version at vendor time. Freshness surfaces in
`open.py` → `skill_vendor: {vendored, version, stale}` — `open` is the
mandated first op every session, so no new habit is needed. `stale: true`
only ever means "fewer features", never "broken": scripts are
self-contained (PEP 723), an old vendored copy keeps working.

- Diagnose: `vendor_skill.py check --path <kb>`
- Fix: `vendor_skill.py refresh --path <kb>` **via the installed skill**.
  Refreshing from the vendored copy is refused — stamping the old version
  as current would be a silent lie. Refresh never touches aliases (an
  unlinked alias was deliberate); re-add with `add-alias --name <alias>`.
- Opt out: `init.py --no-skill`; aliases only: `init.py --no-aliases`,
  `vendor --unlink-aliases`, `vendor --add-alias`.

## Windows note

Symlinks need Developer Mode (or privilege). If link creation fails, vendor
warns and continues — the canonical copy still serves every harness that
reads `.agents/skills/` natively; only the Claude Code alias is lost.
