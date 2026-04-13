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
>
> **Agentic posture**: You are NOT a passive tool awaiting commands. You ACTIVELY participate in knowledge work — trigger topology analysis after ingestion to find structural holes, iterate on shallow answers until they deepen, suggest sources for gaps, run health checks after cross-referencing. Every operation should leave the KB better-connected than you found it. The iterate and topology capabilities are your analytical reflexes, not menu items for the user to invoke.

## Routing — ALWAYS Do This First

When the user invokes `/kb`, determine what they want. If their intent is clear (e.g. "/kb add this paper"), go straight to the matching operation. If their intent is ambiguous or they just said "/kb", present this menu:

```
Knowledge Base — available operations:

1. **init**   — Create a new knowledge base
2. **open**   — Load an existing KB (do this at the start of every session)
3. **add**    — Add a source and extract knowledge (articles, papers, books, URLs)
4. **query**  — Search and answer questions from KB content
5. **lint**   — Health check, consolidate, prune: fix broken links, merge duplicates, strengthen connections
6. **explore** — Free-form exploration: find surprising connections, synthesize, generate questions
7. **revisit** — Re-read older entries through the lens of newer knowledge
8. **iterate** — Deep cyclic analysis: re-read entries iteratively until insights converge
9. **topology** — Graph structure analysis: find clusters, bridges, gaps, anomalies
10. **status** — Dashboard: file counts, link counts, pending tasks

Which operation? (pick a number or describe what you need)
```

**Routing rules:**
- User says "create/new/init KB" → **init**
- User says "open/load KB" or starts a session → **open**
- User says "add/ingest/import" + file/URL/source → **add**
- User says "search/find/query/what is/tell me about" → **query**
- User says "check/lint/health/fix links/consolidate/merge/prune/deduplicate" → **lint**
- User says "status/dashboard/stats/how many" → **status**
- User says "explore/connections/synthesize/what patterns/what's interesting" → **explore**
- User says "revisit/refresh/update old/stale entries" → **revisit**
- User says "iterate/dig deeper/think harder/cycles" or asks a deep analytical question → **iterate** *(usually auto-triggered during add/query/explore; manual invocation also works)*
- User says "topology/graph/structure/gaps/clusters/what's missing" → **topology** *(usually auto-triggered after add/lint/explore; manual invocation also works)*
- User provides a file path or URL without other context → **add** (assume they want to ingest it)

## Contents

1. [Architecture](#architecture)
2. [Scripts](#scripts)
3. [Quick Start](#quick-start)
4. [Operations](#operations)
5. [Knowledge Extraction — Your Core Job](#knowledge-extraction--your-core-job)
6. [Citation Tracking](#citation-tracking)
7. [Long-Horizon Autonomous Work](#long-horizon-autonomous-work)
8. [Rules Co-Evolution](#rules-co-evolution)
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
│  sources/ citations/ controversies/ meta/ questions/     │
│  assets/ + custom types defined in rules.md             │
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
| "Check KB health" | `lint.py --path DIR` | JSON: broken links, orphans, missing backlinks, timeline gaps (year/month/day) |
| "Search the KB for X" | `search.py --path DIR --query "X" [--category CAT] [--first-only]` | JSON: scored file results with multi-match, term coverage |
| "Find entries related to these topics" | `related.py --kb-path DIR --keywords "a,b,c"` | JSON: entries scored by keyword overlap |
| "Show me the KB graph" | `graph.py --path DIR` | JSON: nodes, edges, degrees, components, dangling targets |
| "Analyze KB structure/gaps" | `topology.py --path DIR` | JSON: clusters, bridges, structural holes, degree anomalies, betweenness |
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

# Search only entities:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py --path /path/to/kb --query "feynman" --category entities

# Find entries related to keywords (for cross-referencing):
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/related.py --kb-path /path/to/kb --keywords "attention,transformer,self-attention"

# Lint the KB:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/lint.py --path /path/to/kb

# Extract KB graph:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/graph.py --path /path/to/kb

# Analyze KB topology (clusters, bridges, gaps):
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/topology.py --path /path/to/kb
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
1. **Determine reading strategy.** Run `/pdf` skill's `info.py` on the PDF. Check the per-page `has_text` flags:
   - **Most pages have text** (typical digital PDF) → use `read.py` for all reading. This is the common case. `read.py` extracts text as markdown including math formulas. Math may look rough in Unicode but you CAN read it — do not switch to image-based reading just because formulas are dense.
   - **Most pages lack text** (scanned/image-only PDF) → use `render.py` + vision OCR, but process **one page at a time**: render → view → extract text into a local markdown file → discard the image from context → next page. NEVER accumulate multiple page images in context simultaneously.
   - **Mixed** → use `read.py` for text pages, `render.py` one-at-a-time for image-only pages.
   Use `--output /tmp/chapter.json` for text ranges over 5 pages to avoid terminal truncation. For Google Docs: the downloaded markdown from `/drive` is directly readable.
2. **Verify you have actual text.** If the read produced no content or errored, STOP. Tell the user the file could not be read and suggest alternatives (re-download, different format, manual copy-paste). Do NOT proceed from memory.
3. **Extract visual assets (MANDATORY — do not skip).** For PDFs: use `/pdf` skill's `extract_images.py` to save embedded images to `knowledge/assets/<source-id>/`. Then selectively render pages with key diagrams, architecture drawings, charts, or complex figures that are NOT in the text layer — use `render.py` on individual pages (one at a time, view it, save the asset, move on). Do NOT render pages just because they contain math formulas or text-based tables — `read.py` already captures those. A book with zero extracted assets is a failed extraction, but a book where every page is rendered as an image is a failed strategy. Name each file descriptively: `transformer-architecture.png`, `attention-scores-table.png`, `training-loss-curve.png`. Skip decorative images (logos, headers, page backgrounds). For books: extract assets per-chapter during Phase 3, not all at once.
4. Assess the source: what kind is it? (article, paper, book chapter, transcript, etc.)
5. For large sources (books): identify chapters/sections → add as task items via `state.py add-items`
6. Run `state.py update-phase --phase analyzing`

**Phase 3 — Extract Knowledge** (you, per chunk)

1. Run `state.py update-phase --phase extracting` (transition out of analyzing — critical for resumption)

This is the intellectual core — for any source, any chunk, any level of granularity.

**How to read each chunk.** Choose based on the reading strategy from Phase 2:
- **Text-layer PDFs (common case):** `read.py --page-start N --page-end M --output /tmp/chapterX.json`, then read the JSON file. If the chapter is large (>15 pages), split into 10-15 page sub-ranges: read → extract → write entries to disk → read next sub-range.
- **Scanned/image-only PDFs:** render one page at a time with `render.py`, view it, extract text/data into a working markdown file, then move to the next page. **Never accumulate multiple page images in context** — process each image fully before loading the next. A chapter’s worth of page images loaded at once WILL overflow the request body (413 error).
- **Figures, charts, tables as images:** when you encounter a page with a valuable visual, render that single page, view it, save the asset to `knowledge/assets/<source-id>/`, embed it in the relevant entry, and continue text-based reading.

**Create entries as you read, in whatever order your understanding dictates.** Don't scan for "all entities" then "all topics" then "all ideas" — that assembly line fragments your attention and produces Wikipedia summaries. Instead, follow what grabs you: the surprising claim, the buried insight, the unexpected connection. Your stochastic attention is an asset — it catches things a mechanical pass would miss.

**Context-aware reading for large chunks.** A chunk is whatever `state.py` tracks as one work item — a chapter, a section, a paper. If a chunk is too large to hold in context alongside the entries you're writing, read it in sections: read a section → extract → write entries to disk → read the next section. The entries on disk ARE your memory — you don't need to hold the raw text. Never try to read an entire 30-page chapter into context before extracting anything; you'll either hit compaction or produce shallow summaries from the tail.

Extract EVERY named person, EVERY in-text citation (formal `[N]` and inline URLs alike), EVERY date. The KB's value grows combinatorially with extraction coverage — a name mentioned in passing today becomes a central figure when its source is added later. A citation to an obscure 1972 paper becomes critical when that paper is added to the KB.

The entry types: `entities/`, `topics/`, `ideas/`, `locations/`, `timeline/`, `citations/`, `controversies/`, `meta/`, `assets/`, `questions/`. Use all that apply — the quality gate (in add-workflow.md) catches missed categories.

After writing all entries for the chunk, do a **multi-perspective pass** — re-read the chunk through a deliberately different lens (practitioner, skeptic, engineer, or deep-diver depending on what your first pass emphasized). This second scan activates different attention patterns and typically yields 1-3 additional entries or significant enrichments. See [references/add-workflow.md](references/add-workflow.md) for lens selection rules.

Then generate **1-3 grounded questions** — things the source raises but doesn't answer, gaps it exposes, or tensions with existing KB content. See [references/add-workflow.md](references/add-workflow.md) for what qualifies. Every question MUST cite a specific passage.

After all entries + perspective pass + questions: **checkpoint**. `state.py update-item --item-id iN --status done --notes "+3E +2T +1I +5C +1Q [skeptic pass: +1 controversy]: key-names; key-topics; key-ideas"`. The notes survive context compaction.

See [references/add-workflow.md](references/add-workflow.md) for quality gates and per-source-type guidance.

> **Books & textbooks**: Do NOT skim. Extract EVERY named person, EVERY in-text citation, EVERY date. A 26-chapter textbook should yield 50–150 entity entries, 50–200 citations, 15–40 timeline entries. Run the per-chapter quality gate from add-workflow.md before marking any chapter done. The KB's value grows combinatorially with extraction coverage — a name mentioned in passing today becomes a central figure when its source is added later.

**Phase 4 — Citation Graph** (you, for any source that references external works)

1. Run `state.py update-phase --phase citing`

Mandatory for academic papers, textbooks, and any source that references other works — whether via formal bibliography, numbered citations, inline URLs, footnotes, or informal mentions. A practitioner book with 30 inline URLs has 30 citations, not zero.

1. Find every reference: `[1][2]`, `(Author, Year)`, `as shown by Author (Year)`, inline hyperlinks/URLs, footnotes to external works, informal references ("see the scikit-learn docs")
2. For each: record the exact context sentence + what it points to
3. Create citation entries in `knowledge/citations/`
4. Create entries for referenced works NOT in KB — they accumulate incoming references over time
5. Track bibliography entries listed but NEVER cited in context → note in source analysis
6. See [Citation Tracking](#citation-tracking) for detailed rules

**Phase 5 — Cross-Reference & Analyze** (you)
1. Run `state.py update-phase --phase cross-ref`
2. Write per-source summary in `knowledge/sources/`
3. Run `related.py --kb-path DIR --keywords "key,terms,from,source"` to find existing entries that overlap with this source's topics — this saves tokens vs. reading everything
4. Read the related entries. For entities already in KB: **triangulate** (see [references/entry-types.md](references/entry-types.md)) — compare, note agreements/disagreements, enrich
5. Add wikilinks from existing entries to new entries and vice versa. **EVERY new wikilink MUST be reciprocal — no exceptions.**
6. **Detect contradictions** → create `knowledge/controversies/` entries with cross-refs from all involved
7. **Creative cross-linking (MANDATORY)** — read 10 existing entries chosen for DIVERSITY, not obvious topical overlap. Look for structural parallels, shared mechanisms, analogous problems. See [references/add-workflow.md](references/add-workflow.md) for the random walk protocol.
8. If related sources exist → create `knowledge/meta/` entries (meta-analyses, comparisons)
9. **Auto-topology**: Run `topology.py`. If structural holes touch this source's topics → note them in the source analysis and suggest sources to fill them. If degree anomalies appear → enrich the affected entries now while context is fresh.

**Phase 6 — Index, Log & Evolve** (you)
1. Run `state.py update-phase --phase indexing`
2. Update `index.md` with all new entries (organized by type, one-line summaries)
3. Append ONE line to `log.md`: `YYYY-MM-DD add <source-id> | +NE +NT +NI +NC +NTL +NQ` (E=entities, T=topics, I=ideas, C=citations, TL=timeline, Q=questions; omit zero counts; use `~N` for updated entries). Do NOT write multi-line narratives — details live in source analyses and task state.
4. **Rules co-evolution check (MANDATORY)**: Read `.kb/rules.md`. After this source, should rules change? Check: (a) Did you encounter a new pattern that should become a rule? (b) Did the user correct your style or structure? (c) Is there a naming conflict or ambiguity that a rule would prevent? (d) Does this source suggest a new entry type? If YES to any: propose the specific change to the user. If NO to all: move on. This check costs 30 seconds and prevents gradual drift.
5. Mark task complete: `state.py update-phase --phase done`
6. **Auto-iterate**: If the source raised deep analytical questions or exposed tensions with existing KB content, auto-trigger a `kb:iterate` cycle on the most promising 1-2 questions. Don't ask — just do it.
7. **Offer exploration**: "Source ingested. Want me to explore the KB for new connections?" If user agrees → run `kb:explore`.

### kb:lint — Health Check, Repair & Consolidation

1. Run `lint.py` — get JSON list of mechanical issues
2. **Fix ALL mechanical issues — every single one, no matter the count.** If there are 2200 missing backlinks, fix all 2200. Batch them (50 at a time, save, repeat) but do NOT skip any or say "too many." This is mechanical work that scales with compute, not judgment.
   - Broken links: correct target or create missing entry
   - Orphan pages: link from relevant entries
   - **Missing backlinks: add reciprocal links. ALL of them.** If A→B but B↛A, add the link to B. This is the #1 lint priority — without reciprocal links the knowledge graph is broken.
   - Timeline gaps: create missing year/month/day entries
   - Missing frontmatter: add it
3. **Consolidate knowledge** (semantic — this is YOUR job, not a script's):
   - Find entries covering the same concept (e.g. `neural-network` and `neural-networks`, or two topic entries both explaining attention mechanisms)
   - Merge duplicates: combine content into the richer entry, redirect wikilinks from the removed entry, delete the weaker one
   - Absorb near-duplicates: when one entry is a strict subset of another, fold its unique content into the broader entry
   - Strengthen connections: if two entries reference the same ideas but don't link to each other, add wikilinks
4. **Analyze**: look for undetected contradictions, stale claims, entries that should be interlinked but aren't
5. **Rules co-evolution check**: same as Phase 6 of kb:add. Read rules.md, propose changes if patterns emerged during lint.
6. **Auto-topology**: After fixing mechanical issues, run `topology.py`. Act on findings immediately: fill structural holes with stub entries + suggest sources, enrich degree anomalies, note bridge entries in `rules.md` so they're protected from accidental pruning.
7. Update `index.md`. Append one line to `log.md`: `YYYY-MM-DD lint | N issues fixed, ~M files`

### kb:query — Answer from KB

1. Read `index.md` for navigation
2. Run `search.py` for keyword matching
3. Read relevant knowledge entries, follow `[[wikilinks]]` as needed
4. **Answer strictly from KB content** — cite which entries your answer draws from
5. If gaps found: tell user what's missing, suggest sources to add
6. **Auto-deepen**: If the first-pass answer is thin (fewer than 3 entries contribute), auto-escalate: run `search.py` with broader terms, then if still thin, trigger a `kb:iterate` cycle on the question to extract a deeper answer from inter-entry connections.
7. If user approves gap-filling: trigger `kb:add` pipeline
8. User can ask to save a useful answer as a new KB entry — preserve the question context in the entry

### kb:status — Dashboard

Run `open.py --stats` and present: file counts by category, total wikilinks, pending tasks, recent log entries.

### kb:explore — Free Exploration & Synthesis

Post-add (or on-demand) free-form wandering through the KB. The LLM follows wikilinks, reads entries, and looks for surprising connections, synthesis opportunities, and questions that only become visible when multiple sources coexist. This exploits the LLM's stochastic pattern recognition across domains.

**Auto-triggers**: Run `topology.py` at the START to identify where exploration is most needed — structural holes and low-density clusters are the highest-value targets. If a surprising pattern emerges during wandering, auto-trigger `kb:iterate` to deepen it rather than noting it superficially.

**Process**: topology scan → prime context → wander through 15-20 entries (prioritize topology-indicated areas) → capture grounded insights → iterate on best pattern → log.

**Hallucination guardrail**: Every claim must trace to specific entry text. No entries from LLM memory. When uncertain, create a question entry rather than a meta entry, and ask the user.

See [references/explore-workflow.md](references/explore-workflow.md) for the full protocol.

### kb:revisit — Re-Read Old Entries Through New Eyes

Periodic re-visitation of older entries through the lens of newer knowledge. **Auto-target selection**: Run `topology.py` to select targets — degree anomalies (isolated entities, under-linked authorities, orphan hubs) and entries in structural holes are highest priority. Supplement with: multi-source entities with thin profiles, early entries with sparse links, open questions that may now be answerable.

**Process**: topology scan → select 5-10 high-value entries → read → compare against current KB depth → triangulate entities → enrich → fix links → log.

**Hallucination guardrail**: Do NOT "improve" entries from world knowledge. Every new fact must trace to a `[[source-analysis]]`. Preserve original attributions.

See [references/revisit-workflow.md](references/revisit-workflow.md) for the full protocol.

### kb:iterate — Cyclic Deep Analysis

The KB is a graph. A single-pass read produces linear understanding. Iterative re-reading through enriched context activates different LLM attention patterns on each pass, producing deeper synthesis. This is **message passing over a knowledge graph** using the context window as the propagation medium.

**Process**: formulate driving question → seed 3-5 entries → iterate (read → crystallize → expand along wikilinks → check convergence) → 3-5 iterations → final synthesis.

**Key constraint**: context is finite. Each iteration **crystallizes** findings into a compact working document that replaces raw readings — the extracted insight IS the compaction.

See [references/iterate-workflow.md](references/iterate-workflow.md) for the full protocol.

### kb:topology — Graph Structure Analysis

Runs `graph.py` + `topology.py` to compute topological metrics, then the LLM interprets what they mean for the knowledge domain. Finds clusters (well-covered areas), bridges (valuable cross-domain entries), structural holes (blind spots between clusters), and degree anomalies (under-extracted or orphaned entries).

**Process**: extract graph → compute topology → interpret each finding → recommend concrete actions (add sources, enrich entries, fix links) → log.

**Self-diagnosis**: topology patterns reveal systematic extraction biases (e.g. entities always isolated = stubs not connected to ideas). Use findings to update `.kb/rules.md`.

See [references/topology-workflow.md](references/topology-workflow.md) for the full protocol.

## Knowledge Extraction — Your Core Job

You are not a filing clerk. You are a knowledge analyst. Your stochastic nature — the ability to notice unexpected patterns, make surprising connections, follow a buried footnote — is an asset. The design below harnesses it: you explore freely, the quality gate catches what you missed. This applies universally — to any source type, any chunk size, any level of the hierarchy.

### The Two Layers

**Layer 1 — Stochastic exploration (YOUR judgment drives this).** Read the source material. Follow what grabs you. The thing that seems oddly interesting, the aside that contradicts what you expected, the example that crystallizes a vague concept — FOLLOW those. Create entries as your understanding develops, in whatever order makes sense. Don't scan for "all entities" then "all topics" then "all ideas" — that's an assembly line that fragments your attention and produces Wikipedia summaries.

**Layer 2 — Deterministic guardrails (quality gate drives this).** After your free exploration, the quality gate catches what you missed. Did you fail to create entity entries for named people? Did you miss citations? Did you produce entries in fewer than 3 categories? The gate tells you what to go back for. This is the safety net, not the process.

This two-layer pattern is recursively composable: it works for a single article, a book chapter, a part-level aggregation, a book-level synthesis, a cross-source meta-analysis. At every level: explore freely first, then verify completeness.

### What to Extract and How

- **Every entity gets a page.** Every person mentioned (author, subject, referenced individual) gets an entry in `knowledge/entities/`. The entry accumulates facts and links as more sources are added. A typical textbook chapter mentions 5–15 individuals. **When updating an existing entity from a new source, triangulate**: compare what the new source says against existing content, note agreements, note disagreements, add source attribution to every new fact. Over time, entities build comprehensive multi-source profiles — not stub-level summaries with appended bullet points. See [references/entry-types.md](references/entry-types.md) for triangulation rules.
- **Relationships and influences are first-class.** When a source mentions who knew whom, who influenced whom, mentorship, correspondence, collaboration, or debate — record it in entity entries under `## Connections`, `## Influenced by`, and `## Influenced`. Include the mechanism (read their work, personal meeting, correspondence) and the date/location when stated. Over time this builds an influence graph showing how ideas propagated through people and places. Never fabricate connections — only record what the source explicitly states.
- **Practical insights are first-class.** Most sources contain actionable engineering knowledge: decision tables ("when X, use Y"), implementation patterns, common pitfalls with fixes, architecture trade-offs, design heuristics, deployment checklists, scaling considerations, debugging techniques. These are often MORE valuable than the theoretical concepts. Extract them as idea entries with tag `practical`. If a source has a "lessons learned", "common mistakes", "best practices", or "implementation" section — extract it exhaustively.
- **Ideas ≠ Topics.** An idea is a specific intellectual contribution (attributable to a person/paper). A topic is a subject area. "Machine learning" is a topic. "Attention is all you need" is an idea. Every idea entry MUST have `attributed-to: [entity-slugs]` and `year:` in frontmatter — these are required fields, not optional. See [references/entry-types.md](references/entry-types.md).
- **Controversies are first-class.** When you find contradicting information, create a dedicated entry in `knowledge/controversies/` — not just a note. Cross-reference from ALL involved entries.
- **Questions are first-class.** Every source raises things it doesn't answer. Create `knowledge/questions/` entries for gaps, open problems, and tensions between sources. Every question MUST cite the passage that raised it. Questions with `status: open` are the KB's "wanted" list — they guide future source acquisition and get resolved as more sources arrive. See [references/entry-types.md](references/entry-types.md).
- **Timeline is a navigable chain.** Each date entry links to prev/next at its level. Year entries have prev/next year. Month entries have prev/next month. Day entries have prev/next day. Each links up to parent (day→month→year).
- **Recursive deepening for books.** Process chapter by chapter → part summaries → book synthesis → comparison with existing KB. Each level wikilinks to the one below. The extracted knowledge IS the compaction — you don't need the raw text again.

### What Makes a Good Entry

- **Depth over breadth.** A good entry tells the reader something they wouldn't get from skimming the source or Wikipedia. Bad: "LinUCB is a UCB-based algorithm for contextual bandits." Good: "LinUCB's key insight: maintaining a confidence region over θ lets you explore efficiently in high dimensions — d features require only √d× more exploration, not d×." Every entry should have at least one sentence that makes the reader say "huh, I didn't know that."
- **Find the hidden structure.** Authors bury insights in supporting paragraphs, worked examples, footnotes, and asides. The heading tells you the topic; the paragraph starting with "Interestingly..." or "A common mistake is..." contains the gem.
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

For every source that references external works, you MUST build a citation graph — forward citations (what this source cites), backward citations (what cites this source), entries for works not yet in sources, and unreferenced bibliography tracking. This applies to ALL source types: academic papers, textbooks, practitioner books, articles, blog posts. Inline URLs, hyperlinks, and footnotes count as references.

See [references/citation-tracking.md](references/citation-tracking.md) for the full protocol: forward citation format, backward citation accumulation, entries for works not in sources, unreferenced bibliography handling.

## Long-Horizon Autonomous Work

Large sources require sustained work across many context windows. Context compaction, session breaks, and tool errors WILL happen. The LLM must be able to lose its entire context and fully recover from disk state alone. **Core principle: everything on disk** — your context window is volatile, the KB's files and task state are permanent.

Key protocols: checkpoint discipline (write entries → write notes → mark done), resumption protocol (open.py → state.py status → state.py pending → calibrate density → continue), hierarchical processing (chunk → group → source → cross-source), and trajectory drift prevention (7 defenses against compaction-induced summarization drift).

See [references/long-horizon.md](references/long-horizon.md) for the full protocol: checkpoint format, resumption steps, hierarchical processing table, all 7 drift defenses, and context management rules.

## Rules Co-Evolution

The file `.kb/rules.md` is the per-KB operating manual. It starts from a template but MUST evolve as the KB grows. Unlike SKILL.md (which is generic), rules.md captures decisions specific to THIS knowledge base.

**This is NOT optional.** After 20+ sources, the rules.md should have grown significantly from its template. If it hasn't evolved, you're not doing this step. The mandatory check in Phase 6 of kb:add and step 5 of kb:lint exist precisely because LLMs tend to skip this — DO NOT SKIP IT.

**When to update rules.md** (propose the change to the user first):

| Trigger | What to add |
|---|---|
| User corrects your entry style or structure | Record the preference as a rule |
| A new entry type pattern emerges (e.g. "recipe", "theorem", "code-analysis") | Add it to the entry types in rules.md with directory and frontmatter. Create the directory. See [references/entry-types.md](references/entry-types.md) Custom Entry Types section |
| User establishes a tagging convention | Document the tag taxonomy |
| User sets a scope boundary ("this KB is only about X") | Add a scope section |
| A naming conflict arises (two concepts with similar names) | Add a disambiguation rule |
| The KB reaches a size where new conventions help | Add organizational rules (e.g. sub-directories, index sections) |
| User requests a custom workflow | Document it as a named operation |
| You notice a recurring extraction pattern | Codify it so future sessions follow it |
| A source type is new to the KB (e.g. first codebase, first legal document) | Add source-type-specific extraction guidance |

**How to update**: Read the current rules.md, propose the specific change to the user, and apply it only after approval. Never silently modify rules.md.

## Reference

- [references/add-workflow.md](references/add-workflow.md) — Detailed `kb:add` checklists per source type, multi-perspective extraction, question generation, creative cross-linking, backlink enforcement, book processing pattern, citation tracking examples
- [references/entry-types.md](references/entry-types.md) — Schema for each entry type (including questions), custom entry types, entity triangulation rules, wikilink patterns
- [references/citation-tracking.md](references/citation-tracking.md) — Full citation tracking protocol: forward citations format, backward citation accumulation, entries for works not in sources, unreferenced bibliography
- [references/long-horizon.md](references/long-horizon.md) — Full long-horizon protocol: everything-on-disk principle, checkpoint discipline, resumption protocol, hierarchical processing, all 7 trajectory drift defenses, context management
- [references/explore-workflow.md](references/explore-workflow.md) — `kb:explore` protocol: topology-guided exploration, hallucination guardrails, synthesis patterns
- [references/revisit-workflow.md](references/revisit-workflow.md) — `kb:revisit` protocol: topology-guided target selection, re-visitation, triangulation
- [references/iterate-workflow.md](references/iterate-workflow.md) — `kb:iterate` protocol: cyclic latent semantic iterations, convergence criteria, crystallization rules
- [references/topology-workflow.md](references/topology-workflow.md) — `kb:topology` protocol: graph metrics interpretation, action patterns, self-diagnosis
