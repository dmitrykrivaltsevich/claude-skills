---
name: kb
description: Builds, curates, and queries local knowledge bases — persistent collections of interlinked Obsidian-compatible markdown files. Extracts knowledge from sources (articles, papers, books, videos), creates richly interlinked entries (entities, topics, ideas, locations, timeline, citations, controversies, meta-analyses), detects contradictions, and tracks citation graphs. Use when the user asks to create a knowledge base, add sources to a KB, query a KB, lint/maintain a KB, or manage a personal wiki or external brain.
allowed-tools:
  - Bash(uv run *)
  - Bash(cat *)
  - Read
  - Write
user-invocable: true
---

# Knowledge Base Skill

> **CRITICAL — read before doing anything else:**
>
> 1. **Scripts are data pipes.** They handle file I/O, copying, link scanning, state management. **YOU (the LLM) do ALL the intellectual work**: knowledge extraction, summarization, analysis, cross-linking, controversy detection, citation tracking, and meta-analysis.
> 2. **One active KB at a time.** Run `open.py` to prime your context for a KB before operating on it.
> 3. **For PDF sources**, read the `/pdf` SKILL.md first — use its scripts for text extraction and image extraction. This skill does not duplicate PDF handling.
> 4. **`${CLAUDE_SKILL_DIR}` = this skill only.**

## Contents

1. [Architecture](#architecture)
2. [Scripts](#scripts)
3. [Quick Start](#quick-start)
4. [Operations](#operations)
5. [Knowledge Extraction — Your Core Job](#knowledge-extraction--your-core-job)
6. [Citation Tracking](#citation-tracking)
7. [Multi-Session Continuity](#multi-session-continuity)
8. [Context Management](#context-management)
9. [Reference](#reference)

## Architecture

Three layers per KB:

```
┌─────────────────────────────────────────────────────────┐
│  SCHEMA LAYER    .kb/rules.md + SKILL.md                │
│  (how to operate — co-evolved with the KB)              │
├─────────────────────────────────────────────────────────┤
│  KNOWLEDGE LAYER    knowledge/                          │
│  entities/ topics/ ideas/ locations/ timeline/           │
│  sources/ citations/ controversies/ meta/               │
│  (LLM-curated markdown, interlinked via [[wikilinks]])  │
├─────────────────────────────────────────────────────────┤
│  RAW LAYER    sources/                                  │
│  files/<src-id>/  references/                           │
│  (immutable — LLM reads, never modifies)                │
└─────────────────────────────────────────────────────────┘
```

**Division of labor**: Scripts = file I/O, state tracking, mechanical checks. LLM = reading, understanding, extracting, linking, analyzing, writing knowledge entries.

## Scripts

| User says… | Script | What it returns |
|---|---|---|
| "Create a knowledge base" | `init.py --path DIR --name "NAME"` | Scaffolded KB structure + config |
| "Open/load this KB" | `open.py --path DIR` | JSON context: config, rules, index, counts, pending tasks |
| "KB stats/dashboard" | `open.py --path DIR --stats` | Above + total files, total wikilinks |
| "Add this file/source" | `add_source.py --kb-path DIR --source FILE` | Source copied, ID assigned, config updated |
| "Add this URL as reference" | `add_source.py --kb-path DIR --source URL --reference --title "T"` | Reference stub created |
| "Check KB health" | `lint.py --path DIR` | JSON: broken links, orphans, missing backlinks, timeline gaps |
| "Search the KB for X" | `search.py --path DIR --query "X"` | JSON: matching files with context lines |
| "What's the task status?" | `state.py status --task-id ID` | JSON: phase, items done/pending/in-progress |
| "Resume pending work" | `state.py pending --task-id ID` | JSON: next items to process |

All scripts: `uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/<script>`.

## Quick Start

```bash
# Scaffold a new KB:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/init.py --path /path/to/kb --name "My Research"

# Open an existing KB (do this at start of every session):
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/open.py --path /path/to/kb

# Register a local file as source:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/add_source.py --kb-path /path/to/kb --source /path/to/paper.pdf

# Register an external URL as reference:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/add_source.py --kb-path /path/to/kb --source "https://example.com/article" --reference --title "Article Title"

# Create a task for multi-session work:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py init --task-id "add-paper-x" --task-type add --description "Ingest paper on X" --kb-path /path/to/kb --state-dir /path/to/kb/.kb/tasks

# Search the KB:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py --path /path/to/kb --query "quantum computing"

# Lint the KB:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/lint.py --path /path/to/kb
```

## Operations

### kb:init — Scaffold a New KB

1. Run `init.py` to create the folder structure
2. Script auto-generates: config, rules, index, log, all knowledge directories
3. Read the output — the KB is now "open" (you have the context)

### kb:open — Load KB Context

1. Run `open.py` — read the entire JSON output
2. This gives you: KB name, rules, index (for navigation), file counts, pending tasks
3. If pending tasks exist, inform the user and offer to resume

### kb:add — Add Source + Extract Knowledge

This is the most complex operation. It combines mechanical source registration with deep analytical work by you.

**Phase 1 — Register Source** (script)
1. Run `add_source.py` to copy/reference the source
2. Run `state.py init` to create a task with the source info

**Phase 2 — Read & Plan** (you)
1. Read the source. For PDFs: use `/pdf` skill's `read.py` or `render.py`
2. Assess the source: what kind is it? (article, paper, book chapter, transcript, etc.)
3. For large sources (books): identify chapters/sections → add as task items via `state.py add-items`
4. Run `state.py update-phase --phase analyzing`

**Phase 3 — Extract Knowledge** (you, per chunk)

This is the intellectual core. For each chunk of the source:

1. **Extract entities** → create/update files in `knowledge/entities/` (people, organizations)
2. **Extract topics** → `knowledge/topics/` (subject areas, fields)
3. **Extract ideas** → `knowledge/ideas/` (specific hypotheses, proposals — ideas are attributable, topics are not)
4. **Extract locations** → `knowledge/locations/`
5. **Extract dates** → create/update `knowledge/timeline/` entries (year→month→day chain)
6. **Synthesize key arguments, facts, insights** → into the appropriate entries above
7. **Interlink everything** via `[[wikilinks]]` — bidirectional where possible
8. Mark processed items via `state.py update-item`

See [references/add-workflow.md](references/add-workflow.md) for detailed checklists per source type.

**Phase 4 — Citation Graph** (you, for academic/referenced sources)
1. Find every in-text citation (e.g., "bla bla bla [1][2]")
2. For each citation: record the exact context sentence + what reference it points to
3. Create citation entries in `knowledge/citations/`
4. Create entries for referenced works NOT in KB — they accumulate incoming references over time
5. Track bibliography entries listed but NEVER cited in context → note in source analysis
6. See [Citation Tracking](#citation-tracking) for detailed rules

**Phase 5 — Cross-Reference & Analyze** (you)
1. Write per-source summary in `knowledge/sources/`
2. Read existing KB entries related to this source's topics
3. Add wikilinks from existing entries to new entries and vice versa
4. **Detect contradictions** → create `knowledge/controversies/` entries with cross-refs from all involved
5. If related sources exist → create `knowledge/meta/` entries (meta-analyses, comparisons)

**Phase 6 — Index & Log** (you)
1. Update `index.md` with all new entries (organized by type, one-line summaries)
2. Append operation to `log.md`: `## [YYYY-MM-DD] add | Source Title`
3. Mark task complete: `state.py update-phase --phase done`

### kb:lint — Health Check & Repair

1. Run `lint.py` — get JSON list of issues
2. **You then fix**: broken links (correct target or create missing entry), orphan pages (link from relevant entries), missing backlinks (add reciprocal links), timeline gaps (create missing entries), missing frontmatter (add it)
3. **You then analyze**: look for undetected contradictions, opportunities for new connections, entries that should be interlinked but aren't
4. Update `index.md` and `log.md`

### kb:query — Answer from KB

1. Read `index.md` for navigation
2. Run `search.py` for keyword matching
3. Read relevant knowledge entries, follow `[[wikilinks]]` as needed
4. **Answer strictly from KB content** — cite which entries your answer draws from
5. If gaps found: tell user what's missing, suggest sources to add
6. If user approves: trigger `kb:add` pipeline to fill the gap
7. User can ask to save a useful answer as a new KB entry — preserve the question context in the entry

### kb:status — Dashboard

Run `open.py --stats` and present: file counts by category, total wikilinks, pending tasks, recent log entries.

## Knowledge Extraction — Your Core Job

You are not a filing clerk. You are a knowledge analyst. When processing a source:

- **Understand before filing.** Read the whole chunk first, then decide what entries to create.
- **Ideas ≠ Topics.** An idea is a specific intellectual contribution (attributable to a person/paper). A topic is a subject area. "Machine learning" is a topic. "Attention is all you need" is an idea.
- **Every entity gets a page.** Every person mentioned (author, subject, referenced individual) gets an entry in `knowledge/entities/`. The entry accumulates facts and links as more sources are added.
- **Timeline is a navigable chain.** Each date entry links to prev/next at its level. Year entries have prev/next year. Month entries have prev/next month. Day entries have prev/next day. Each links up to parent (day→month→year).
- **Controversies are first-class.** When you find contradicting information, create a dedicated entry in `knowledge/controversies/` — not just a note. Cross-reference from ALL involved entries.
- **Recursive deepening for books.** Process chapter by chapter → part summaries → book synthesis → comparison with existing KB. Each level wikilinks to the one below. The extracted knowledge IS the compaction — you don't need the raw text again.

### Entry Frontmatter Standard

Every knowledge `.md` file MUST have:

```yaml
---
type: entity | topic | idea | location | timeline | source-analysis | citation | controversy | meta
created: YYYY-MM-DD
updated: YYYY-MM-DD
source-ids: [src-001]
tags: [relevant, tags]
---
```

See [references/entry-types.md](references/entry-types.md) for type-specific fields and examples.

### Link Format

Use Obsidian wikilinks: `[[page-name]]` or `[[page-name|Display Text]]`.
File names use kebab-case: `albert-einstein.md`, `quantum-computing.md`.

## Citation Tracking

For every academic or referenced source, you MUST build a citation graph:

### Forward Citations (what this source cites)

For each in-text citation like "evidence suggests X leads to Y [1][2]":

1. Identify the exact sentence containing the citation
2. Identify which bibliography entries [1], [2] refer to
3. Create/update citation entry: `knowledge/citations/<source-id>-cites-<ref-slug>.md`
4. Content: the exact context sentence, which claims it supports, the referenced work

### Backward Citations (what cites this source)

When a referenced work Y already has an entry in the KB (from a previous source):
- Update Y's entry with the new incoming citation context
- Over time, Y accumulates all sentences from all sources that reference it

### Entries for Works NOT in Sources

Create entries for referenced works even if they're not in your `sources/` directory. These entries:
- Start with just the bibliographic info and incoming citation contexts
- Accumulate more context as more sources are added that reference them
- Serve as "wanted" items — user can decide to add them as full sources later

### Unreferenced Bibliography

If a source lists items in its bibliography but NEVER cites them in the text:
- Record them in the source analysis entry as "listed but unreferenced"
- These may indicate background reading or padding — useful signal for the user

## Multi-Session Continuity

Large sources (books, collections) require multiple sessions. The task state system ensures no work is lost:

1. **Create task**: `state.py init` at the start of `kb:add`
2. **Plan dynamically**: Add work items as you discover them (chapters found while reading)
3. **Track progress**: Mark items done/in-progress as you go
4. **Resume**: Next session, run `open.py` → see pending tasks → run `state.py pending` → pick up where you left off
5. **Knowledge = compaction**: Already-extracted entries are the compact representation. You don't need to re-read raw source chunks — just read the entries you created from them.

The state files live in `.kb/tasks/` inside the KB directory. Use `--state-dir /path/to/kb/.kb/tasks` when calling `state.py`.

## Context Management

- **Start every session** with `open.py` to load the KB context
- **Read `index.md` first** when searching for information — it's your table of contents
- **Follow wikilinks** rather than reading all files — targeted navigation over full scans
- **Use `search.py`** for keyword lookup when index isn't enough
- **Don't re-read processed chunks** — read your own extracted entries instead
- **Write entries incrementally** — don't try to hold an entire book in context

## Reference

- [references/add-workflow.md](references/add-workflow.md) — Detailed `kb:add` checklists per source type, book processing pattern, citation tracking examples
- [references/entry-types.md](references/entry-types.md) — Schema for each entry type with frontmatter, examples, and wikilink patterns
