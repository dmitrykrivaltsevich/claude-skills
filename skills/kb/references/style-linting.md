# kb:lint — Style-Phrase Scanning

`lint.py` flags style-phrase findings (`type: "style-phrase"`) alongside the mechanical issues. The script only detects; **you** decide for each finding: rewrite the wording, or record an exception explaining why the phrase is legitimate here.

**This is unattended.** `kb:lint` assumes no user is available to answer. Never present findings for someone to triage, never ask which option to take, and never stop with findings outstanding — rule 5 below always terminates the decision.

## Finding Shape

Each finding is an issue dict: `file` (KB-relative), `line`, `column`, `pattern` (id), `match` (exact text), `context` (`prose`, `heading`, or `quote`), `excerpt` (trimmed line), `note` (rewrite guidance for that pattern), `excepted` (bool).

Lint output also carries a `style` summary: `findings` (outstanding, one per entry in `issues`), `exceptions` (accepted, excluded from `issues`), `by_context`, `by_pattern`, `by_source` (`default` | `per-kb` | `cli`) — all three counted over outstanding findings — `disabled` (ids of disabled patterns), and `exception_findings` (the accepted findings, for inventory).

`issues` and `total_issues` carry outstanding work only, style and mechanical alike. Recording an exception takes a finding out of both. **`total_issues: 0` is the single completion gate for `kb:lint`** — there is no separate style score, and a lint count never sits permanently above zero because of accepted phrasing.

Scan scope: every `.md` in the KB **except** `sources/files/` (raw layer), `.kb/tasks/`, `.kb/rules-proposals.md`, and the exception store `.kb/style-exceptions/` (with its pre-rename name `.kb/style-reviewed/`) — everything after the raw layer is written by kb:lint itself, and scanning it would make the operation flag its own bookkeeping. `.kb/rules.md` stays in scope: it is durable prose. Frontmatter, fenced code, indented (4-space) code blocks, and inline code spans are skipped; a 4-space indent under a list item or directly after a line of text is continuation prose, not code, and is still scanned. Matches inside double quotes (straight or typographic) are reported with `context: quote` wherever they occur, in prose and in headings alike, as are `>` blockquote lines. Single quotes are not treated as delimiters — apostrophes in ordinary prose are indistinguishable from them — so a phrase in single quotes keeps its line's context (`prose` or `heading`); judge it from the excerpt. Frontmatter counts as frontmatter only when it closes with a line containing just `---`; a block that does not is reported as `missing-frontmatter` and its lines are scanned as prose.

## Pattern Configuration

Schema `kb-style-patterns/v1`: `{ "schema", "flags"?, "patterns": [{ "id", "enabled"?, "regex", "note"? }] }`. Flags: `ignorecase` only, which is also the default. Scanning is line by line, so `multiline`/`dotall` would change nothing and are rejected rather than silently ignored — a pattern cannot span lines.

Layers merge by `id`, highest precedence first:

1. CLI `--patterns FILE`
2. Per-KB `.kb/style-patterns.json`
3. Skill default `scripts/style_patterns.json` (32 patterns)

Re-declaring an `id` overrides that layer's copy. Set `enabled: false` in the per-KB file to switch off a default pattern (it then appears in `style.disabled`). Use the per-KB file to exempt genuine subject-matter terms (e.g. `load-bearing` in a civil-engineering KB) and to add KB-specific clichés. An invalid pattern file or exception fails the lint with an actionable error — fix the file rather than working around it.

## Decision Procedure (per finding)

Apply the **first** rule that matches. Do not deliberate past the first match, and do not consult anyone.

| # | Condition | Action |
|---|---|---|
| 1 | The sentence still says what it meant without the phrase | Rewrite it. This is the default and should resolve most findings |
| 2 | `context: quote` and the line reproduces a source's own wording | `--reason verbatim-quote` |
| 3 | The match is this KB's domain vocabulary (`load-bearing` in a bridge KB) | `--reason subject-matter` |
| 4 | The same pattern has fired 5+ times on legitimate usage | Disable it in `.kb/style-patterns.json`, then re-run |
| 5 | Three rewrite attempts have not removed it | `--reason other` plus `--note` recording what you tried |

```bash
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/style_exceptions.py add --kb DIR --file F --line N --pattern ID --match "TEXT" --reason verbatim-quote [--note "why"]
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/style_exceptions.py list --kb DIR
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/style_exceptions.py remove --kb DIR --file F --line N --pattern ID --match "TEXT"
```

- Exceptions live in `.kb/style-exceptions/<sha1>.json`, keyed by `(file, line, pattern, match)`. They are durable KB data, not lint scratch: a finding you *fixed* leaves no file, so everything in that directory is a standing decision about a phrase still present on purpose. Deleting it makes the next run re-triage every one. A KB still holding the pre-rename `.kb/style-reviewed/` keeps working: lint and `list` read both locations, and the first `add` or `remove` moves the records across. The scan itself never moves anything — `lint.py` only reads — so a KB on read-only media still lints.
- `--file` is normalized to the KB-relative posix form lint reports, so an absolute path or a `./` prefix works; a path outside the KB is rejected rather than stored as a key that could never match.
- Write exceptions with `style_exceptions.py`, not by hand. A hand-written `key.file` that is not in canonical form is rejected on read, but `key.match` is compared exactly — including case — so a hand-edited record that differs in case simply will not suppress its finding, and you will re-triage it on the next run.
- An excepted finding leaves `issues` entirely and reappears under `style.exception_findings` with `excepted: true`, so it is inventory, not work.
- An exception only matches its exact key — if you edit the line so the number or text shifts, the exception goes stale and the finding becomes outstanding again. Re-triage instead of re-adding blindly.
- Rewrite first, except second. Exceptions are for legitimate usages, not for silencing the scan.

## Style Checklist in kb:lint

The first run on an established KB surfaces its whole style backlog at once, so `total_issues` jumps; that is the backlog, not a regression. Work it down as below, or pass `--no-style` to keep a given run mechanical-only.

1. Run `lint.py` (use `--output FILE` when findings are numerous)
2. Resolve every `style-phrase` finding with the decision procedure above
3. Re-run `lint.py` until `total_issues` is 0 — at most 3 passes, then rule 5 closes out whatever is left
4. Log: `YYYY-MM-DD lint | N issues fixed, ~M files, P phrases rewritten, Q excepted`

## CLI Flags

- `--no-style` — skip style-phrase scanning; mechanical checks still run
- `--patterns FILE` — merge an extra pattern file on top of per-KB and defaults