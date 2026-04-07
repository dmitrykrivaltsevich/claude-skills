# Knowledge Base Skill

LLM-curated local knowledge bases — persistent collections of interlinked Obsidian-compatible markdown files. Extracts knowledge from sources (articles, papers, books, videos), creates richly interlinked entries, tracks citations, and detects contradictions.

## What It Does

This skill manages the scaffolding and mechanical operations. **The LLM does all the intellectual work**: knowledge extraction, summarization, cross-linking, citation graph building, controversy detection, and meta-analysis.

Operations:
- **kb:init** — scaffold a new KB with folder structure and config
- **kb:open** — load KB context to prime the LLM
- **kb:add** — register source + heavy analytical extraction (multi-session capable)
- **kb:lint** — mechanical health checks (broken links, orphans, timeline gaps)
- **kb:query** — search and answer from KB content
- **kb:status** — dashboard with file counts and pending tasks

## Scripts

| Script | Purpose |
|---|---|
| `init.py` | Scaffold KB folder structure, config, rules, index |
| `open.py` | Load full KB context as JSON (config, rules, counts, pending tasks) |
| `add_source.py` | Copy/reference a source file, assign ID, update config |
| `lint.py` | Check broken wikilinks, orphans, missing backlinks, timeline gaps |
| `search.py` | Full-text grep across KB markdown files |
| `state.py` | Multi-session task queue (init, add-items, update, status) |
| `contracts.py` | Design-by-contract decorators (shared utility) |

## KB Structure

```
my-kb/
  .kb/
    config.yaml        # KB config + source registry
    rules.md           # LLM operating rules (co-evolved with KB)
    tasks/             # Multi-session task state files
  sources/
    files/<src-id>/    # Copied source files (immutable)
    references/        # External URL reference stubs
  knowledge/
    entities/          # People, organizations
    topics/            # Subject areas, fields
    ideas/             # Specific attributable contributions
    locations/         # Geographic places
    timeline/          # Navigable year→month→day chain
    sources/           # Per-source analysis summaries
    citations/         # Citation graph entries
    controversies/     # Contradictions and debates
    meta/              # Cross-source syntheses
  index.md             # Table of contents
  log.md               # Operation log
```

## Tests

```bash
uv run --no-config --with pytest --with pyyaml pytest skills/kb/tests/ -x --tb=short
```

77 tests across 6 test files.
