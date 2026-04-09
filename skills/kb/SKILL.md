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
> 2. **NEVER extract from LLM memory.** If you cannot read the actual source text (file inaccessible, format unsupported, network error), STOP and tell the user. Do not fill in entries from what you “remember” about the work. Every fact in a KB entry must come from the source text you actually read in this session. Hallucinated entries are worse than no entries.
> 3. **One active KB at a time.** Run `open.py` to prime your context for a KB before operating on it.
> 4. **For PDF sources**, read the `/pdf` SKILL.md first — use its scripts for text extraction and image extraction. This skill does not duplicate PDF handling.
> 5. **For Google Drive sources**, use the `/google-drive` skill to download the file first, then process the local copy.
> 6. **`${CLAUDE_SKILL_DIR}` = this skill only.**

## Routing — ALWAYS Do This First

When the user invokes `/kb`, determine what they want. If their intent is clear (e.g. "/kb add this paper"), go straight to the matching operation. If their intent is ambiguous or they just said "/kb", present this menu:

```
Knowledge Base — available operations:

1. **init**   — Create a new knowledge base
2. **open**   — Load an existing KB (do this at the start of every session)
3. **add**    — Add a source and extract knowledge (articles, papers, books, URLs)
4. **query**  — Search and answer questions from KB content
5. **lint**   — Health check: find broken links, orphans, missing backlinks
6. **status** — Dashboard: file counts, link counts, pending tasks

Which operation? (pick a number or describe what you need)
```

**Routing rules:**
- User says "create/new/init KB" → **init**
- User says "open/load KB" or starts a session → **open**
- User says "add/ingest/import" + file/URL/source → **add**
- User says "search/find/query/what is/tell me about" → **query**
- User says "check/lint/health/fix links" → **lint**
- User says "status/dashboard/stats/how many" → **status**
- User provides a file path or URL without other context → **add** (assume they want to ingest it)

## Contents

1. [Architecture](#architecture)
2. [Scripts](#scripts)
3. [Quick Start](#quick-start)
4. [Operations](#operations)
5. [Knowledge Extraction — Your Core Job](#knowledge-extraction--your-core-job)
6. [Citation Tracking](#citation-tracking)
7. [Multi-Session Continuity](#multi-session-continuity)
8. [Context Management](#context-management)
9. [Rules Co-Evolution](#rules-co-evolution)
10. [Reference](#reference)

## Architecture

Three layers per KB:

```
┌─────────────────────────────────────────────────────────┐
│  SCHEMA LAYER    .kb/rules.md + SKILL.md                │
│  (how to operate — co-evolved with the KB)              │
├─────────────────────────────────────────────────────────┤
│  KNOWLEDGE LAYER    knowledge/                          │
│  entities/ topics/ ideas/ locations/ timeline/           │
│  sources/ citations/ controversies/ meta/ assets/       │
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
| "Add this file/source" | `add_source.py --kb-path DIR --source FILE --source-id ID` | Source copied, config updated |
| "Add this URL as reference" | `add_source.py --kb-path DIR --source URL --reference --title "T" --source-id ID` | Reference stub created |
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
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/add_source.py --kb-path /path/to/kb --source /path/to/paper.pdf --source-id real-2020

# Register an external URL as reference:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/add_source.py --kb-path /path/to/kb --source "https://example.com/article" --reference --title "Article Title" --source-id karpathy-2023

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
1. Determine the source ID: first-author-lastname + year in kebab-case (e.g. `real-2020`, `rumelhart-1986`). If collision with existing source, add a letter suffix: `real-2020a`
2. **Acquire the file:**
   - Local file → use directly, register as local source
   - Google Drive file/URL → use `/drive` skill's `download.py` to download a local copy for reading, but register as `--reference` with the original Google Drive URL (the downloaded file is temporary — the canonical location is Drive)
   - URL (web article) → register as reference with `--reference`
3. Run `add_source.py` with `--source-id` to copy/reference the source. For Drive and URL sources, pass `--reference --source <original-URL> --title "Title"`
4. Run `state.py init` to create a task with the source info

**Phase 2 — Read & Plan** (you)
1. Read the source. For PDFs: use `/pdf` skill's `read.py` or `render.py`. For Google Docs: the downloaded markdown from `/drive` is directly readable.
2. **Verify you have actual text.** If the read produced no content or errored, STOP. Tell the user the file could not be read and suggest alternatives (re-download, different format, manual copy-paste). Do NOT proceed from memory.
3. **Extract visual assets (MANDATORY — do not skip).** For PDFs: use `/pdf` skill's `extract_images.py` to save embedded images to `knowledge/assets/<source-id>/`. Then scan page by page: use `render.py` on EVERY page containing figures, tables, diagrams, charts, architecture drawings, algorithm pseudocode, or data tables that are NOT embedded images (e.g. vector graphics, formatted tables). This is not optional — a book with zero extracted assets is a failed extraction. Name each file descriptively: `transformer-architecture.png`, `attention-scores-table.png`, `training-loss-curve.png`. Skip only decorative images (logos, headers, page backgrounds). For books: extract assets per-chapter during Phase 3, not all at once.
4. Assess the source: what kind is it? (article, paper, book chapter, transcript, etc.)
5. For large sources (books): identify chapters/sections → add as task items via `state.py add-items`
6. Run `state.py update-phase --phase analyzing`

**Phase 3 — Extract Knowledge** (you, per chunk)

This is the intellectual core. For each chunk of the source:

1. **Extract entities** → create/update files in `knowledge/entities/` (people, organizations)
2. **Extract relationships & influences** → for each person, record connections (who knows whom, collaborations, debates), influence chains (who influenced whom, how, when), and locations at key moments. Only what the source explicitly states — see entity template in [references/entry-types.md](references/entry-types.md).
3. **Extract topics** → `knowledge/topics/` (subject areas, fields)
4. **Extract ideas** → `knowledge/ideas/` (specific hypotheses, proposals — ideas are attributable, topics are not)
4. **Extract locations** → `knowledge/locations/`
5. **Extract dates** → create/update `knowledge/timeline/` entries (year→month→day chain)
6. **Synthesize key arguments, facts, insights** → into the appropriate entries above
7. **Embed visual assets** in relevant entries using `![[knowledge/assets/<source-id>/<filename>.png]]`. Place each figure/table next to the text discussing it, with a caption. Only embed assets extracted in Phase 2 — never reference non-existent files.
8. **Interlink everything** via `[[wikilinks]]` — bidirectional where possible
9. **Checkpoint & advance**: Write all entries to disk, then mark the item done with checkpoint notes: `state.py update-item --item-id iN --status done --notes "+3E +2T +1I +5C: key-entity-names; key-topics"`. The notes are your breadcrumb trail — they survive context compaction.

See [references/add-workflow.md](references/add-workflow.md) for detailed checklists per source type.

> **Books & textbooks**: Do NOT skim. Extract EVERY named person, EVERY in-text citation, EVERY date. A 26-chapter textbook should yield 50–150 entity entries, 50–200 citations, 15–40 timeline entries. Run the per-chapter quality gate from add-workflow.md before marking any chapter done. The KB's value grows combinatorially with extraction coverage — a name mentioned in passing today becomes a central figure when its source is added later.

**Phase 4 — Citation Graph** (you, for academic/referenced sources)

Mandatory for academic papers AND textbooks/books with bibliographies.

1. Find every in-text citation (e.g., "bla bla bla [1][2]", "(Author, Year)", "as shown by Author (Year)")
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
2. Append ONE line to `log.md`: `YYYY-MM-DD add <source-id> | +NE +NT +NI +NC +NTL` (E=entities, T=topics, I=ideas, C=citations, TL=timeline; omit zero counts; use `~N` for updated entries). Do NOT write multi-line narratives — details live in source analyses and task state.
3. Mark task complete: `state.py update-phase --phase done`

### kb:lint — Health Check, Repair & Consolidation

1. Run `lint.py` — get JSON list of mechanical issues
2. **Fix mechanical issues**: broken links (correct target or create missing entry), orphan pages (link from relevant entries), missing backlinks (add reciprocal links), timeline gaps (create missing entries), missing frontmatter (add it)
3. **Consolidate knowledge**: scan entries for overlapping or redundant content:
   - Find entries covering the same concept (e.g. `neural-network` and `neural-networks`, or two topic entries both explaining attention mechanisms)
   - Merge duplicates: combine content into the richer entry, redirect wikilinks from the removed entry, delete the weaker one
   - Absorb near-duplicates: when one entry is a strict subset of another, fold its unique content into the broader entry
   - Strengthen connections: if two entries reference the same ideas but don't link to each other, add wikilinks
4. **Analyze**: look for undetected contradictions, stale claims, opportunities for new connections, entries that should be interlinked but aren't
5. Update `index.md`. Append one line to `log.md`: `YYYY-MM-DD lint | N issues fixed, ~M files`

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
- **Relationships and influences are first-class.** When a source mentions who knew whom, who influenced whom, mentorship, correspondence, collaboration, or debate — record it in entity entries under `## Connections`, `## Influenced by`, and `## Influenced`. Include the mechanism (read their work, personal meeting, correspondence) and the date/location when stated. Over time this builds an influence graph showing how ideas propagated through people and places. Never fabricate connections — only record what the source explicitly states.
- **Timeline is a navigable chain.** Each date entry links to prev/next at its level. Year entries have prev/next year. Month entries have prev/next month. Day entries have prev/next day. Each links up to parent (day→month→year).
- **Controversies are first-class.** When you find contradicting information, create a dedicated entry in `knowledge/controversies/` — not just a note. Cross-reference from ALL involved entries.
- **Recursive deepening for books.** Process chapter by chapter → part summaries → book synthesis → comparison with existing KB. Each level wikilinks to the one below. The extracted knowledge IS the compaction — you don't need the raw text again.
- **Practical insights are first-class.** Most books contain actionable engineering knowledge: decision tables ("when X, use Y"), implementation patterns, common pitfalls with fixes, architecture trade-offs, design heuristics, deployment checklists, scaling considerations, debugging techniques. These are often MORE valuable than the theoretical concepts. Extract them as idea entries with tag `practical`. If a chapter has a "lessons learned", "common mistakes", "best practices", or "implementation" section — extract it exhaustively.
- **Write for a staff/principal engineer, not a PhD student.** When the source uses dense math, always provide intuition FIRST, then the formula, then engineering implications. Translate "$O(\sqrt{KT \log T})$ regret" into "exploration cost grows as the square root of time — meaning it gets relatively cheaper to explore as you gather more data." Include the formula for precision, but never let it stand alone without a plain-language explanation of what it means in practice.

### Source ID Naming Convention

Source IDs use **first-author-year** format (BibTeX-style). This makes every reference in frontmatter and filenames immediately readable.

| Source type | Pattern | Example |
|---|---|---|
| Academic paper | `<first-author>-<year>` | `real-2020`, `rumelhart-1986` |
| Book | `<author>-<year>` | `isaacson-2007` |
| Blog / article | `<author-or-site>-<year>` | `karpathy-2023`, `openai-2024` |
| Video / talk | `<speaker>-<year>` | `lecun-2019` |
| Disambiguation | append letter suffix | `real-2020a`, `real-2020b` |

This ID propagates everywhere: `sources/files/real-2020/`, `real-2020-analysis`, `real-2020-cites-rumelhart-1986`, `source-ids: [real-2020]`. Always derive it from the first author's last name + publication year.

### Entry Frontmatter Standard

Every knowledge `.md` file MUST have:

```yaml
---
type: entity | topic | idea | location | timeline | source-analysis | citation | controversy | meta
created: YYYY-MM-DD
updated: YYYY-MM-DD
source-ids: [real-2020]
tags: [relevant, tags]
---
```

See [references/entry-types.md](references/entry-types.md) for type-specific fields and examples.

### Link Hygiene — MANDATORY

This KB is Obsidian-compatible. Clicking a wikilink MUST open an existing file in the correct directory. A broken link causes Obsidian to create an empty file in the vault root, which destroys the KB structure.

**Format**: `[[page-name]]` or `[[page-name|Display Text]]`. File names use kebab-case.

**Rule 1 — No dangling wikilinks.** NEVER write `[[something]]` unless the target file already exists OR you create it in the same operation. If you mention a concept that doesn't have an entry yet and you're not creating one now, use plain text — not a wikilink.

**Rule 2 — Sources are wikilinked, not bare IDs.** When referencing a source in an entry, use `[[real-2020-analysis]]` (linking to the source analysis page), NEVER bare `real-2020`. The source analysis page is the navigable hub for that source. In frontmatter `source-ids: [real-2020]` remains a plain string (frontmatter is data, not rendered links).

**Rule 3 — Source analysis ↔ registered source are bidirectionally linked.** The source analysis MUST include `**Source**: [[lamport-1978]]` near the top — a wikilink, not a file path. NEVER write `Source: sources/references/lamport-1978.md` or `Source: sources/files/real-2020/paper.pdf`. The `add_source.py` script creates a navigable `.md` stub for every source (both files and references), so `[[source-id]]` always resolves. The stub already links to `[[source-id-analysis]]`. Without this bidirectional wikilink, the source becomes an orphan in the graph.

**Rule 4 — Every date in text is a wikilink.** When a year, year-month, or full date appears in prose, it MUST be a wikilink to the corresponding timeline entry. Write `[[2017]]` not `2017`, `[[2017-06]]` not `June 2017`, `[[2017-06-12]]` not `June 12, 2017`. Create the timeline entry if it doesn't exist yet.

**Rule 5 — External URLs use standard markdown links.** External links use `[text](https://...)`, NEVER wikilinks. Wikilinks are for internal KB entries only.

**Rule 6 — Verify before linking.** Before writing a wikilink to an entry you didn't just create, check that the file exists (via search or index). When in doubt, create a minimal stub entry rather than risk a dangling link.

**Rule 7 — Asset embeds use `![[path]]`.** Embed extracted images/figures with `![[knowledge/assets/<source-id>/<filename>.png]]`. Only embed files that you extracted in Phase 2 and that exist on disk. Never fabricate asset references.

**Rule 8 — No dead parenthetical references.** NEVER leave bare `(Author Year)` parenthetical references as plain text in knowledge entries. When the source text says "X is true (Boehm 2002)", the entry MUST replace the parenthetical with a wikilink to the citation entry: `X is true ([[sommerville-2011-cites-boehm-2002|Boehm, 2002]])`. If the citation entry doesn't exist yet, create it first (even a minimal stub). This makes every factual claim traceable — the reader clicks the link, lands on the citation entry, sees the exact context and citing source. A bare "(Boehm 2002)" is a dead end that tells the reader nothing about which Boehm 2002 work, which edition, or where to find it.

**Rule 9 — No aliased wikilinks inside markdown tables.** The `|` in `[[page|Display]]` conflicts with the markdown table column delimiter. Inside a table cell, use only bare `[[page-name]]` (no alias). If you need display text, restructure as a list instead of a table.

**Pre-commit check**: After finishing a kb:add or kb:lint operation, mentally scan all new/modified files for wikilinks. Every `[[target]]` must resolve to `knowledge/<category>/target.md` or a top-level file like `index.md`.

## Citation Tracking

For every academic or referenced source, you MUST build a citation graph:

### Forward Citations (what this source cites)

For each in-text citation like "evidence suggests X leads to Y [1][2]":

1. Identify the exact sentence containing the citation
2. Identify which bibliography entries [1], [2] refer to
3. Create/update citation entry: `knowledge/citations/<source-id>-cites-<ref-slug>.md`
4. Content MUST include:
   - `**Citing source**: [[<source-id>-analysis]]` — mandatory navigable wikilink back to the source
   - `**Context**:` — the exact sentence containing the citation
   - `**Claims supported**:` — what the citation is used for
   - `**Significance**:` — one sentence: why this citation matters (foundational? competing? methodological?)
   - `**See also**:` — wikilinks to related KB entries (entities, topics, ideas)

### Backward Citations (what cites this source)

When a referenced work Y already has an entry in the KB (from a previous source):
- Update Y's entry with the new incoming citation context
- Add wikilink to Y in the citation's **See also** — this enables "show me everything that cites Y" via backlink navigation
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

## Long-Horizon Autonomous Work

Large sources require sustained work across many context windows. Context compaction, session breaks, and tool errors WILL happen. This skill is designed for resilience — the LLM must be able to lose its entire context and fully recover from disk state alone.

### Core Principle: Everything on Disk

Your context window is volatile. The KB's files and task state are permanent. Every decision, every extraction, every checkpoint MUST be written to disk before moving on. If you crash after writing, no work is lost. If you crash before writing, you redo only that one chunk.

### Checkpoint Discipline

When you finish processing any work item (chapter, section, batch):

1. **Write all entries to disk first** — entity, topic, idea, citation, timeline files
2. **Write checkpoint notes** via `state.py update-item --notes "..."` — a compact tally of what you extracted (e.g. `+5E +3T +2I +8C: dijkstra, parnas, brooks; waterfall, incremental; lehman-laws; 1968-1975 timeline`)
3. **Then** mark the item done

The notes field is your breadcrumb trail. When context compacts, `state.py pending` returns the last 5 completed items with their notes — enough to reconstruct what was done and what comes next.

### Resumption Protocol

After ANY interruption (context compaction, session break, error recovery):

```
1. Run open.py              → reload KB structure, index, rules, pending tasks
2. Run state.py status      → see current phase, done/pending counts
3. Run state.py pending     → see next items + checkpoint notes from recent items
4. Calibrate extraction density:
   - Read checkpoint notes from the FIRST 3 completed items (not just recent ones)
   - These set the extraction density floor for all remaining items
   - If recent items show declining counts vs early items, you ARE drifting
5. For book chapters: re-read the per-chapter quality gate in add-workflow.md
6. Continue from the next pending item — do NOT re-process done items
```

This protocol works whether you lost context 5 minutes ago or 5 days ago. The disk state is the single source of truth.

### Hierarchical Processing for Large Sources

Any source too large for one pass requires hierarchical processing. This applies to books, collections, large reports — anything with internal structure.

**Processing levels** (bottom-up):

| Level | Unit | What you do | Checkpoint |
|-------|------|------------|------------|
| **Chunk** | Chapter, section, essay | Exhaustive extraction: entities, topics, ideas, citations, dates | `update-item --notes` with extraction tally |
| **Group** | Part, section cluster | Cross-chunk connections, part-level themes | Notes in source analysis under `## Part N` |
| **Source** | Whole book/collection | Source-level synthesis, overarching themes, bibliography analysis | Full source analysis file |
| **Cross-source** | Related KB content | Meta-analyses, contradiction detection | `knowledge/meta/` and `knowledge/controversies/` entries |

Each level builds on the one below. Do NOT skip levels — the synthesis quality depends on having exhaustive chunk-level extraction first.

### Preventing Trajectory Drift

Context compaction can cause the LLM to "forget" the extraction strategy and drift into summarization. Defenses:

1. **Task items are your todo list.** Process them in order. Don't improvise.
2. **Checkpoint notes anchor your approach.** When resuming, read the notes from recent items — they show the extraction pattern you were following (e.g. "+8E +3T +12C" tells you to maintain that density, not drop to "+1T").
3. **The quality gate is mandatory.** Every chunk MUST pass the quality gate checklist before marking done. This prevents drift toward skimming.
4. **Checkpoint notes are your narrative.** After each chunk, write a `--notes` that captures both the extraction tally AND the key themes. This is your running narrative — it survives compaction and anchors your trajectory. Do NOT write incremental progress into knowledge files.
5. **NEVER bulk-read after compaction.** When resuming after context compaction, process ONE chapter/section at a time — exactly as you did before compaction. The temptation to "catch up" by reading multiple remaining chapters at once produces shallow, summary-level extraction. Each chapter deserves the same exhaustive treatment regardless of how many remain. If 15 chapters are left, process them one by one across 15 cycles. There are no shortcuts.
6. **Density drop = drift alarm.** After writing checkpoint notes, compare your extraction tally against TWO baselines: (a) the density expectations table in add-workflow.md (5-15 entities, 5-20 citations per chapter), and (b) the first 3 chapters you processed in this task. Do NOT compare only against the previous 2-3 chapters — if those were already degraded by drift, you'll anchor to a bad baseline. If your counts are below 50% of EITHER baseline (e.g. early chapters averaged `+5E +3I +8C` but you just wrote `+1T`), you ARE drifting. STOP. Re-read the quality gate. Re-read the chapter. Extract what you missed. Do NOT mark the chapter done until density recovers.
7. **Minimum viable extraction per chapter.** Every book chapter checkpoint MUST include at least 3 distinct extraction categories from {E, T, I, C, TL}. A checkpoint with only `+1T` or any single category is ALWAYS incomplete — no exceptions. Most non-trivial textbook chapters contain named people (→ E), in-text references (→ C), and at least one date or topic alongside ideas. If your checkpoint shows `+0E` or `+0C` for a textbook chapter, re-read the chapter — you skimmed it. The per-chapter quality gate in add-workflow.md has specific minimums.

### Context Management

- **Start every session** with `open.py` to load the KB context
- **Read `index.md` first** when searching for information — it's your table of contents
- **Follow wikilinks** rather than reading all files — targeted navigation over full scans
- **Use `search.py`** for keyword lookup when index isn't enough
- **Don't re-read processed chunks** — read your own extracted entries instead
- **Write entries incrementally** — don't try to hold an entire book in context
- **If context feels full**, finish the current item, write checkpoint notes, mark done, then continue — the resumption protocol handles the rest

## Rules Co-Evolution

The file `.kb/rules.md` is the per-KB operating manual. It starts from a template but MUST evolve as the KB grows. Unlike SKILL.md (which is generic), rules.md captures decisions specific to THIS knowledge base.

**When to update rules.md** (propose the change to the user first):

| Trigger | What to add |
|---|---|
| User corrects your entry style or structure | Record the preference as a rule |
| A new entry type pattern emerges (e.g. "recipe", "theorem") | Add it to the entry types table with directory and frontmatter |
| User establishes a tagging convention | Document the tag taxonomy |
| User sets a scope boundary ("this KB is only about X") | Add a scope section |
| A naming conflict arises (two concepts with similar names) | Add a disambiguation rule |
| The KB reaches a size where new conventions help | Add organizational rules (e.g. sub-directories, index sections) |
| User requests a custom workflow | Document it as a named operation |

**How to update**: Read the current rules.md, propose the specific change to the user, and apply it only after approval. Never silently modify rules.md.

## Reference

- [references/add-workflow.md](references/add-workflow.md) — Detailed `kb:add` checklists per source type, book processing pattern, citation tracking examples
- [references/entry-types.md](references/entry-types.md) — Schema for each entry type with frontmatter, examples, and wikilink patterns
