# Knowledge Base Skill

LLM-curated local knowledge bases — persistent collections of interlinked Obsidian-compatible markdown files. Extracts knowledge from sources (articles, papers, books, videos), including know-how and hidden gems, creates richly interlinked entries, tracks citations, and detects contradictions.

Broad KB JSON surfaces support native artifact mode via `--output`, and saved JSON or markdown/text artifacts can be reopened narrowly with `json_query.py` and `page_query.py`.

## What It Does

This skill manages the scaffolding and mechanical operations. **The LLM does all the intellectual work**: knowledge extraction, know-how capture, summarization, cross-linking, citation graph building, controversy detection, and meta-analysis.

Operations:
- **kb:init** — scaffold a new KB with folder structure and config
- **kb:open** — load KB context to prime the LLM
- **kb:add** — register source + heavy analytical extraction (multi-session capable)
- **kb:lint** — mechanical health checks (broken links, orphans, timeline gaps)
- **kb:query** — search and answer from KB content
- **kb:explore** — free-form exploration: find surprising connections, synthesize, generate questions
- **kb:revisit** — re-read older entries through the lens of newer knowledge
- **kb:iterate** — deep cyclic analysis: re-read entries iteratively until insights converge
- **kb:topology** — graph structure analysis: find clusters, bridges, gaps, anomalies
- **kb:status** — dashboard with file counts and pending tasks

## Scripts

| Script | Purpose |
|---|---|
| `init.py` | Scaffold KB folder structure, config, rules, index |
| `open.py` | Load KB context as JSON; supports `--output` artifact mode for large KBs |
| `add_source.py` | Copy/reference a source file, assign ID, update config |
| `lint.py` | Check broken wikilinks, orphans, missing backlinks, timeline gaps (year/month/day); supports `--output` |
| `search.py` | Full-text search with scoring, multi-match, category filter, and frontmatter filters for `idea-kind` / tags, plus `--output` |
| `related.py` | Find entries by keyword overlap (for cross-referencing); supports `--output` |
| `graph.py` | Extract wikilink graph: nodes, edges, degrees, components; supports `--output` |
| `topology.py` | Graph topology analysis: clusters, bridges, structural holes, anomalies; supports `--output` |
| `state.py` | Multi-session task queue (init, add-items, update, status) with `--output` support on all subcommands |
| `json_query.py` | Reopen narrow slices from saved JSON artifacts using selectors, filters, fields, and limits |
| `page_query.py` | Reopen sections, chunks, or exact line ranges from markdown/text files |
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
    ideas/             # Specific attributable contributions and know-how
    locations/         # Geographic places
    timeline/          # Navigable year→month→day chain
    sources/           # Per-source analysis summaries
    citations/         # Citation graph entries
    controversies/     # Contradictions and debates
    meta/              # Cross-source syntheses
    questions/         # Open questions, gaps, tensions
  index.md             # Table of contents
  log.md               # Operation log
```

## Tests

```bash
uv run --no-config --with pytest --with pyyaml pytest skills/kb/tests/ -x --tb=short
```

The KB tests cover scaffolding, search, state handling, and documentation guardrails.
