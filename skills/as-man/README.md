# as-man

Displays anything as a Unix manual page in the terminal, and lets you navigate it.

```
/as-man tell me about Datalog
```

## What It Does

Claude acts as the manual page viewer. You point it at a topic, a URL, a file, a book or a magazine issue; it commits an outline, writes one section at a time as you navigate, and typesets each screen at 80 columns.

Three modes:

| Mode | Reached by | What happens |
|---|---|---|
| Render and navigate | `/as-man <anything>` | A manual page, navigated with pager keys |
| Test my understanding | `?` | One question at a time, graded against the page, with the lines to re-read |
| What is not in this doc | `!` | Researched omissions, appended as a navigable `GAPS` section |

Three design points worth knowing:

- **The outline is committed, the bodies are not.** Claude fixes the table of contents when the page opens, then writes a section only when you reach it — shaped by the path you took and by anything you got wrong in the quiz. A written section is cached, so going back shows the same text.
- **Depth comes from the material.** A concept is one level. A book is part, chapter, section. There is always a last page and an `(END)`.
- **The register is fixed, the detail is not.** Man-page structure, plain international English at CEFR B2. No idioms, no phrasal verbs, ISO dates, glossed acronyms. When a section is too terse, `v` rewrites it with the mechanism and a worked example; `b` goes back. Raising the level adds facts and never loosens the voice.

## Scripts

Two, both stdlib-only. Everything that is judgement belongs to the model.

| Script | Role |
|---|---|
| `state.py` | The memory — outline tree, navigation trail, question bank, gap findings. Subcommands; every response is a bounded slice. |
| `render.py` | The typesetter — markdown to 80-column terminal text, with the one-line prompt. Layout only. |

`contracts.py` is the repo's shared Design-by-Contract helper, vendored as every skill in this marketplace vendors it.

Fetching and parsing are delegated: URLs to the `duckduckgo` skill, PDFs to the `pdf` skill, gap research to `duckduckgo` or `deep-research`, retention to `kb`.

## Session Layout

```
~/.cache/as-man/<session-id>/
├── page.md       # realised sections only
└── session.json  # outline, position, trail, quiz, gaps
```

There is no `init` — the first write creates the session. Override the location with `--session-dir`.

## Tests

From the repository root:

```bash
uv run --no-config --with pytest pytest skills/as-man/tests/ -v
```

`test_guidance.py` is a guardrail suite: it fails if SKILL.md loses one of its mandatory rules, if a reference file stops being reachable one level deep, or if the references start chaining into each other.
