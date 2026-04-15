# Book Processing Workflow

Multi-session book extraction: chapter-by-chapter processing with hierarchical analysis documents. Books — especially textbooks — are the densest source type. A 26-chapter textbook can yield 50–100+ entities, 100+ citations, 20+ timeline entries, and multiple controversies. Skimming is the #1 failure mode.

## Contents

1. [PDF Reading Strategy](#pdf-reading-strategy--text-first-images-one-at-a-time)
2. [Session 1 — Plan](#session-1--plan)
3. [Sessions 2-N — Per Chapter](#sessions-2-n--per-chapter)
   - [Explore](#explore--read-and-think-stochastic-your-judgment)
   - [File](#file--create-entries-informed-by-your-exploration)
   - [Verify — Quality Gate](#verify--quality-gate-deterministic-catches-what-you-missed)
   - [Chapter Analysis Brief](#chapter-analysis-brief-mandatory--after-quality-gate)
   - [Checkpoint](#checkpoint-mandatory--after-chapter-analysis-brief)
4. [Part-Level Aggregation](#part-level-aggregation-mandatory-for-books-with-partssections)
5. [Final Session — Synthesis](#final-session--synthesis)
6. [Quick Reference: Session Template](#quick-reference-session-template)
7. [Extraction Density Expectations](#extraction-density-expectations-textbooks)
8. [Anti-Patterns — Guaranteed Failures](#anti-patterns--guaranteed-failures)
9. [Completion Sanity Check](#completion-sanity-check)

---

## PDF Reading Strategy — Text First, Images One at a Time

**Step 0: Run `info.py` to classify the PDF.** Check per-page `has_text` flags. This determines your reading method for the entire book.

**Text-layer PDFs (most pages have text):** Use `read.py` with `--output`:
```bash
uv run --no-config ${CLAUDE_SKILL_DIR}/../pdf/scripts/read.py book.pdf --page-start 43 --page-end 72 --output /tmp/ch3.json
```
Then read `/tmp/ch3.json`. This captures all text including math formulas. Math in text form (Unicode, LaTeX fragments) looks ugly but is readable — do NOT switch to page rendering just because formulas are dense.

**Scanned/image-only PDFs (most pages lack text):** Use `render.py` + vision, but **one page at a time**:
```bash
uv run --no-config ${CLAUDE_SKILL_DIR}/../pdf/scripts/render.py book.pdf --page-start 51 --page-end 51 --output-dir /tmp/ocr --dpi 400
```
View the single page image → extract text/data into a working markdown file on disk → move to the next page. The working file on disk IS your memory. NEVER load multiple page images into context simultaneously — each page image costs 1-5MB of context, and accumulating them causes 413 overflow.

**For visual assets: `render.py` on INDIVIDUAL pages.** When a chapter has a key architecture diagram, a complex figure, a chart, or a table rendered as an image, render that ONE page:
```bash
uv run --no-config ${CLAUDE_SKILL_DIR}/../pdf/scripts/render.py book.pdf --page-start 51 --page-end 51 --output-dir /tmp/assets
```
View the image, name it descriptively, copy to `knowledge/assets/<source-id>/`, embed in the relevant entry, then continue.

**The ONE rule: never accumulate multiple page images in context.** Process each image fully (OCR it, extract the asset, whatever) before loading the next one. This applies whether you rendered the images yourself or found pre-existing renders on disk from a prior session.

## Session 1 — Plan

1. Read table of contents, preface, and any "guided reading" sections
2. Create task items: one per chapter + one per part/section boundary + one "synthesis" item. Titles MUST include chapter number and name (e.g. `Ch 7: Design and implementation (pp. 176-204)`) and part boundaries (e.g. `Part 2 aggregation: Dependability and Security (Ch 10-15)`). Part-level aggregation items are NOT optional — without them, book-level synthesis must jump from 26 chapters to one summary, which is too large a gap.
3. If the book has a bibliography or references section, scan it to estimate citation density

## Sessions 2-N — Per Chapter

Each chapter has three phases: explore, file, verify. The explore phase is stochastic — let your attention drive it. The filing creates entries from your understanding. The verification catches what you missed.

### Explore — read and think (stochastic, YOUR judgment)

**Reading method: text extraction, or one-at-a-time OCR for scans.** For text-layer PDFs: use `/pdf` `read.py --output /tmp/chN.json`, then read the JSON file. If the chapter is long (>15 pages), split into 10-15 page sub-ranges and process each: read text → extract entries → write to disk → read next sub-range. For scanned PDFs: render and view one page at a time, extract text to a working file, then move on. **Never accumulate multiple page images in context** — this is what causes 413 overflow on large chapters.

Read the full chapter text. Do not skim. As you read, notice what grabs your attention — the surprising claim, the counterintuitive result, the aside that contradicts conventional wisdom, the footnote with a key reference, the diagram that crystallizes a concept, the passage that would change how an engineer approaches a problem.

**Do NOT plan your extraction before reading.** Do not think "I need to find entities, then topics, then ideas." That fragments your attention into category-scanning instead of understanding. Just read and think.

### File — create entries (informed by your exploration)

Create entries from what you found. Work in whatever order your understanding suggests — if a key insight grabbed you, write that idea entry first. If a person's contribution struck you, start with that entity. If a figure crystallized the chapter's argument, extract and embed it.

You will naturally produce entries across multiple categories — entities, topics, ideas, citations, timeline, practical insights, locations, visual assets. The quality gate (below) catches if you missed a category. But the ORDER and EMPHASIS come from your reading, not from a checklist.

**References**: Every reference you encounter — `(Author, Year)`, `[N]`, inline URL, footnote, "see the X documentation" — gets a citation entry. These accumulate over time and become the KB's citation graph.

**Visual assets**: When you encounter a figure, table, or diagram worth preserving, extract it using `/pdf` tools (`render.py` for page renders, `extract_images.py` for embedded images). Embed in the entry where it belongs: `![[knowledge/assets/<source-id>/<name>.png]]`.

**Cross-link** with entries from previous chapters — wikilinks both directions. Note contradictions with existing KB → controversy entries.

### Verify — quality gate (deterministic, catches what you missed)

**Hard minimums — a chapter that fails ANY of these is incomplete:**

| Category | Minimum | Why |
|----------|---------|-----|
| Entities (E) | ≥ 3 | Nearly every textbook chapter names researchers, historical figures, or practitioners |
| Citations (C) | ≥ 3 | Most chapters reference prior work — via bibliography, inline URLs, footnotes, or informal mentions |
| Distinct categories | ≥ 3 of {E, T, I, C, TL} | A `+1T` checkpoint is ALWAYS drift. Real chapters produce entries across multiple types |
| Visual assets | ≥ 1 (if chapter has any figures/tables) | Most non-trivial chapters have at least one figure, table, or diagram |

If your extraction doesn't meet these minimums, **go back and look specifically for the missing category** — the gate tells you where you under-extracted. Re-read relevant sections if needed.

**Completeness scan — check before marking done:**

- [ ] Named people in the chapter text have entity entries (scan for proper nouns you skipped)
- [ ] References have citation entries (scan for URLs, footnotes, `(Author, Year)` patterns)
- [ ] Years/dates mentioned have timeline entries
- [ ] Figures/tables extracted as visual assets and embedded in entries
- [ ] Practical insights captured: decision tables, pitfalls, implementation patterns, heuristics
- [ ] Entries interlinked with `[[wikilinks]]`
- [ ] Idea entries have `attributed-to:` and `year:` in frontmatter (required — see entry-types.md)
- [ ] Math has plain-language intuition alongside formulas
- [ ] At least one entry contains something non-obvious — if every entry reads like a Wikipedia summary, you filed without thinking
- [ ] Entity entries for people already in KB have been TRIANGULATED (see entry-types.md) — not blindly appended
- [ ] At least 1 question entry created (see [Question Generation](add-workflow.md#question-generation))
- [ ] **ALL new entries have reciprocal `[[wikilinks]]`** — if A links to B, then B MUST link back to A. No exceptions, no "too many". Every single one.

### Chapter Analysis Brief (mandatory — after quality gate)

After the quality gate passes, write a chapter analysis brief to `knowledge/sources/<source-id>-ch<NN>-analysis.md` (zero-padded chapter number, e.g. `lowe-2025-ch03-analysis.md`). This is a working document — richer than a checkpoint tally, lighter than a source analysis. It feeds the part-level and book-level synthesis.

```yaml
---
type: chapter-analysis
created: YYYY-MM-DD
source-ids: [lowe-2025]
chapter: 3
title: "Design and implementation"
pages: 176-204
---
```

**Required sections** (keep each to 2-5 sentences):

| Section | What to write |
|---------|--------------|
| `## Core argument` | What this chapter argues or teaches. One paragraph. |
| `## Key insight` | The single most valuable thing — the insight the reader would miss by reading only the heading. |
| `## Connections to prior chapters` | Which threads this chapter picks up, extends, or contradicts from earlier chapters. Wikilink to those chapter analyses. |
| `## Open threads` | What this chapter raises but doesn't resolve — tensions, unanswered questions, foreshadowing. These feed part-level and book-level synthesis. |
| `## Entry summary` | Extraction tally and key entry names: `+5E +2T +1I +8C +3TL: [[dijkstra]], [[parnas]]; [[software-processes]]; [[lehman-laws]]`. Wikilink to entries. |

**Why this exists**: Checkpoint tallies (`+5E +3T`) are too terse for synthesis. Without chapter analysis briefs, the book-level synthesis must jump from `+5E +3T +2I` × 26 chapters to one coherent analysis — producing shallow output. These briefs are the intermediate representation that makes hierarchical synthesis work.

**Wikilink the chain**: each chapter analysis brief links to prior (`[[<id>-ch02-analysis]]`) and next (`[[<id>-ch04-analysis]]`). This creates a navigable analytical spine for the book.

### Checkpoint (mandatory — after chapter analysis brief)

```bash
state.py update-item --task-id <task-id> --item-id iN --status done \
  --notes "+5E +2T +1I +8C +3TL: dijkstra, parnas, brooks; software-processes, waterfall; lehman-laws" \
  --state-dir <kb>/.kb/tasks
```

The notes format: `+NE +NT +NI +NC +NTL: key-entity-names; key-topics; key-ideas`. Be specific enough that a future you — with zero context — knows what this chapter contributed. **If any mandatory category shows +0 (especially E or C), go back and re-read before marking done.**

## Part-Level Aggregation (MANDATORY for books with parts/sections)

When a book has explicit parts (e.g. "Part 2: Dependability and Security, Chapters 10-15"), you MUST have a task item for each part boundary (created in Session 1). Even if the book doesn't have explicit parts, group every 4-6 chapters into logical clusters and create aggregation items for them.

After finishing all chapters in a part:

1. **Read chapter analysis briefs** for all chapters in this part — these are your primary input, NOT the raw source text or entry files. The briefs contain: core argument, key insight, connections, open threads.
2. **Write a part analysis document** to `knowledge/sources/<source-id>-part<N>-analysis.md`:

```yaml
---
type: part-analysis
created: YYYY-MM-DD
source-ids: [lowe-2025]
part: 2
title: "Dependability and Security"
chapters: [10, 11, 12, 13, 14, 15]
---
```

**Required sections** (each 3-8 sentences):

| Section | What to write |
|---------|--------------|
| `## Chapter briefs` | Wikilink every chapter analysis brief this part is built from: `[[<id>-ch10-analysis]]`, `[[<id>-ch11-analysis]]`, etc. This is the traceability chain — readers must be able to drill down from part to chapter. |
| `## Argument arc` | How the part's chapters build on each other — the narrative progression, not a chapter-by-chapter summary. |
| `## Cross-chapter themes` | Themes that emerge only when you see multiple chapters together. Not themes visible in any single chapter. |
| `## Tensions and contradictions` | Where chapters disagree, present competing approaches, or leave unresolved debates. These are often the most analytically valuable findings. |
| `## Relationship to other parts` | How this part extends, deepens, or redirects other parts. Wikilink to their part analyses (`[[<id>-part1-analysis]]`, etc.). For prior parts: how this part builds on or diverges from them. For later parts (if already processed): update this section when you reach them. Cross-part links MUST be reciprocal — if Part 3 references Part 1, Part 1's analysis MUST link back. |
| `## Open threads` | What this part raises for the remainder of the book. Threads that should be tracked through later parts. |
| `## Entry summary` | Aggregate tallies and notable entries from all chapters in the part. |

3. **Create or update topic entries** for cross-chapter themes within the part — these are themes that span multiple chapters, not chapter-level topics
4. **Create cross-chapter idea entries** for patterns visible only at the part level
5. **Identify inter-chapter connections within the part** → add wikilinks
6. **Update prior part analyses**: if this part connects to earlier parts (and it almost always does), go back and add reciprocal wikilinks in their `## Relationship to other parts` sections. Part analyses are living documents until synthesis.
7. **Checkpoint**: `state.py update-item --notes "Part 2: dependability vs security trade-off, Reason's Swiss cheese model as unifying pattern across Ch 10-15"`

**Why part analysis documents exist**: They are the intermediate representation between chapter briefs and book-level synthesis. Without them, the book analysis must read 26 chapter briefs at once — too many for the context window. Part analyses compress 4-6 chapter briefs into one coherent document, making the book-level synthesis manageable.

This is the middle level of hierarchical aggregation. Skipping it means the book-level synthesis must jump from 26 individual chapters to one summary — producing shallow, useless output.

## Final Session — Synthesis

Book-level analysis — the top of the hierarchy for this single source. This session synthesizes from part analyses, not from raw chapters.

1. **Read part analysis documents** — these are your primary input. They contain: argument arc, cross-chapter themes, tensions, open threads. If the book has 5 parts, read all 5 part analyses. This IS manageable in one context window (each part analysis is ~1 page).
2. **Read checkpoint notes** from all completed items — these supplement the part analyses with extraction tallies and specific entry names
3. **Read the topic/idea/entity entries** created during extraction (NOT the raw source) — browse key entries to refresh your understanding
4. **Write the source analysis** (`knowledge/sources/<source-id>-analysis.md`) — this is a **finished analytical document**: book summary, overarching thesis, cross-part themes, how the argument develops across parts, key extractions list, bibliography analysis, figures & tables. No checklists, no progress tracking, no session logs. The source analysis wikilinks to each part analysis (`[[<id>-part1-analysis]]`, etc.) and they link back.
5. Create cross-part topic connections (themes that span the entire book)
6. Review the complete timeline extracted — fill any gaps
7. Identify controversies/debates the book discusses across parts → controversy entries
8. **Cross-book analysis** (if related sources exist in KB): create `knowledge/meta/` entries comparing this book with other books on the same topic — convergences, divergences, evolution of the field's thinking. Other books' source analyses are your comparison points.
9. Update index, log, mark task done

**The full document hierarchy for a book**:
```
Chapter analysis briefs (one per chapter)
    ↓ feeds
Part analysis documents (one per part or 4-6 chapter cluster)
    ↓ feeds
Source analysis (one per book)
    ↓ feeds
Meta entries (cross-book comparisons in knowledge/meta/)
```

Each level reads only the level directly below — never raw chapters. This is how a 26-chapter book compresses into a coherent analysis without losing depth.

## Quick Reference: Session Template

For a book with P parts and N chapters:

```
Session 1:  Read TOC → state.py add-items (ch1, ..., chN, part1-agg, ..., partP-agg, synthesis)
Session 2:  state.py pending → process ch1 → quality gate → chapter analysis brief → checkpoint → done
Session 3:  state.py pending → process ch2 → quality gate → chapter analysis brief → checkpoint → done
...
After last chapter in Part 1:  read ch analysis briefs → write part1 analysis doc → entries → done
...
Session N+P+1: read part analyses → write source analysis → cross-book meta → done
```

**Document hierarchy** (each level reads only the level below):

| Level | Document | Location | Reads from |
|-------|----------|----------|------------|
| Chapter | Chapter analysis brief | `knowledge/sources/<id>-ch01-analysis.md` | Raw chapter text + entries |
| Part | Part analysis document | `knowledge/sources/<id>-part1-analysis.md` | Chapter analysis briefs |
| Book | Source analysis | `knowledge/sources/<id>-analysis.md` | Part analysis documents |
| Cross-book | Meta entries | `knowledge/meta/` | Source analyses from multiple books |

**Each chapter session:**
1. Run `open.py` to reload KB context
2. Run `state.py pending` to see next chapter + recent checkpoint notes
3. **Check density floor**: read checkpoint notes from the FIRST 3 completed items. If recent items show lower counts, you are drifting — match early density.
4. **Re-read the quality gate above** — after compaction you will NOT remember the hard minimums
5. Read full chapter from source
6. **Explore freely** — follow what grabs your attention. Create entries as your understanding develops, in whatever order makes sense.
7. **Quality gate** — verify hard minimums (≥3 E, ≥3 C, ≥3 categories). Go back for any missing category.
8. **Chapter analysis brief** — write `knowledge/sources/<id>-chNN-analysis.md` (see format above). Read prior chapter's brief first to write the Connections section.
9. **Checkpoint** via `update-item --notes "..."` — extraction tally + what surprised you about this chapter
10. Mark chapter done

**Part-level aggregation session:**
1. Read chapter analysis briefs for all chapters in this part — these are your primary input
2. Write part analysis document (`knowledge/sources/<id>-partN-analysis.md`, see format above). MUST wikilink every chapter brief in `## Chapter briefs`.
3. Create/update topic entries for cross-chapter themes within the part
4. Add inter-chapter wikilinks within the part
5. Update prior part analyses with reciprocal cross-part links in `## Relationship to other parts`
6. Checkpoint and mark done

**Synthesis session:**
1. Read part analysis documents — these are your primary input (NOT raw chapters, NOT individual entries)
2. Read checkpoint notes from all completed items for supplementary detail
3. Read key topic/idea/entity entries for depth on specific themes
4. Write book-level source analysis — this is the ONLY time you write the source analysis for a book. It synthesizes from part analyses into a finished analytical document: summary, key themes, cross-references, bibliography analysis. No checklists, no progress tracking.
5. Cross-book meta: if related books exist in KB, write `knowledge/meta/` comparison entries
6. Create cross-chapter connections
7. Identify overarching themes → topic entries
8. Meta-analysis if other books on same topic exist

## Extraction Density Expectations (textbooks)

These are baselines, not caps. Real chapters often exceed these:

| Entry type | Typical per chapter | Notes |
|-----------|-------------------|-------|
| Entities  | 5–15              | Every named person in running text. Authors of cited works. Historical figures. |
| Topics    | 1–3               | Major subject areas the chapter introduces or deepens |
| Ideas     | 1–5               | Specific named models, methods, proposals (attributable) |
| Practical | 1–3               | Decision tables, pitfalls, implementation guides, heuristics (tag: `practical`) |
| Citations | 5–20              | Every "(Author, Year)", "[N]", inline URL, or footnote reference in text |
| Timeline  | 1–5               | Years explicitly mentioned with events |
| Locations | 0–2               | Conferences, institutions, labs |
| Assets    | 1–5               | Figures, tables, diagrams rendered or extracted from the chapter |

A 26-chapter textbook should typically produce:
- 50–150 entity entries (not 5)
- 50–200 citation entries (not 0)
- 15–40 timeline entries (not 4)
- 3–8 controversy entries (not 0)

## Anti-Patterns — Guaranteed Failures

These are the named failure modes for book processing. If you recognize yourself doing any of these, STOP and correct immediately.

### Anti-pattern 1: "TOC-as-analysis"

**What happens**: You read the table of contents, write a source analysis that reformats the TOC into prose ("Chapter 1 covers X, Chapter 2 covers Y..."), create a handful of topic entries from chapter titles, and declare the book done.

**Why it happens**: The TOC gives a false sense of "understanding" the whole book. Writing it as prose feels like analysis. It isn't — it's reformatting.

**The fix**: The source analysis is the LAST thing you write, during the synthesis session, AFTER all chapters are extracted. During Phase 2, you create task items from the TOC — that's the only use for it. If you catch yourself writing `knowledge/sources/<id>-analysis.md` before all chapter task items are done, you are in this anti-pattern. Delete the premature analysis and go back to per-chapter extraction.

### Anti-pattern 2: "One-chunk book"

**What happens**: You treat a 300-page book as a single chunk. You read "some of it" (or worse, skim the whole thing), create 5–15 entries covering the highest-level concepts, and mark the task done.

**Why it happens**: Without `state.py add-items`, there are no chapter-level task items — so there's nothing forcing per-chapter processing. The book feels like one big source, and you process it like an article.

**The fix**: Phase 2 MUST end with `state.py add-items` creating one task item per chapter. Phase 3 processes them ONE AT A TIME. If state.py has no task items for a book, you are in this anti-pattern. Stop everything and go back to Phase 2 step 5.

**Diagnosis**: If your total extraction for a book is under 30 entries, you almost certainly did this. A single chapter of a non-trivial textbook should produce 5–20 entries. A full book should produce 50–200+.

### Anti-pattern 3: "Surface skim"

**What happens**: You nominally process chapters one at a time, but each chapter produces only 1–2 topic entries — essentially the chapter heading restated as a topic page. No entities, no citations, no ideas, no timeline, no practical insights. Total: 10–20 entries for a whole book.

**Why it happens**: Context compaction eroded your extraction density. Or you never read the quality gate. Or you're reading the chapter heading and first paragraph instead of the full text.

**The fix**: The per-chapter quality gate has HARD MINIMUMS: ≥3 entities, ≥3 citations, ≥3 distinct categories. If a chapter checkpoint shows `+1T` and nothing else, you did NOT read the chapter—you skimmed it. Re-read the chapter. Extract what you missed. Compare against the density expectations table. A chapter that produces fewer than 5 entries is almost always under-extracted.

### Anti-pattern 4: "Early source analysis"

**What happens**: You write the source analysis during Phase 2 (after reading the TOC) or during Phase 3 (after the first few chapters). The analysis is shallow because it's based on incomplete extraction.

**Why it happens**: Writing the source analysis feels like progress. It feels like the capstone. But for books, it IS the capstone — it belongs at the END, after all chapters are done.

**The fix**: For books, the source analysis is written during the dedicated synthesis session — the last task item. It synthesizes your per-chapter checkpoint notes and extracted entries into a finished analytical document. If you're writing it before all chapters are marked done in state.py, delete it and continue chapter extraction.

### Anti-pattern 5: "Citation-blind book"

**What happens**: You extract entities and topics but zero citations, because "this isn't an academic paper." The book actually has dozens of inline references — to other books, to websites, to historical events — that you ignored.

**Why it happens**: Citation tracking feels like a paper-only task. But practitioner books reference URLs, textbooks reference other textbooks, and even narrative non-fiction cites sources.

**The fix**: Any time the text says "see X", "as described by Y", "(Author, Year)", or includes a URL/footnote — that's a citation. Scan for these explicitly during the quality gate. If your per-chapter checkpoint shows `+0C` for a chapter that discusses other work, you missed them.

## Completion Sanity Check

After ALL chapter task items are done (before the synthesis session), run this self-diagnosis:

```
1. Count your total entries by type:
   - How many entity entries?    Expected: 30-150 for a full book
   - How many citation entries?  Expected: 20-200 for a full book
   - How many timeline entries?  Expected: 10-40 for a full book
   - How many topic entries?     Expected: 10-30 for a full book
   - How many idea entries?      Expected: 5-30 for a full book

2. Compare against chapter count:
   - Total entries / number of chapters = entries per chapter
   - If this ratio is below 5, you under-extracted. Go back.

3. Check for zero-count categories:
   - 0 citations for a book that references other work? → Anti-pattern 5
   - 0 entities for a book that names people? → Re-scan for proper nouns
   - 0 timeline entries for a book that mentions dates? → Re-scan for years

4. Check checkpoint notes across chapters:
   - Are early chapters dense (+8E +3T +5C) but later ones sparse (+1T)?
   - If yes, later chapters drifted. Reprocess them.

5. Only if all checks pass: proceed to synthesis session.
```

This check takes 2 minutes and catches catastrophic under-extraction before the synthesis session commits a shallow source analysis to disk.
