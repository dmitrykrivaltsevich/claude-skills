# kb:add Workflow Reference

Detailed checklists for the knowledge extraction pipeline. Linked from SKILL.md.

## Contents

1. [Universal Checklist](#universal-checklist)
2. [Source Type: Article / Blog Post](#article--blog-post)
3. [Source Type: Academic Paper](#academic-paper)
4. [Source Type: Book](#book)
5. [Source Type: Video / Podcast Transcript](#video--podcast-transcript)
6. [Source Type: URL Reference (no full text)](#url-reference)
7. [Any Large Source (Generic Pattern)](#any-large-source-generic-pattern)
8. [Citation Tracking Examples](#citation-tracking-examples)
9. [Book Processing Pattern](#book-processing-pattern)
10. [Compaction — Why You Don't Need the Raw Text Again](#compaction)

## Universal Checklist

Every `kb:add` regardless of source type:

- [ ] Register source (`add_source.py`)
- [ ] Create task (`state.py init`)
- [ ] Read the source (use `/pdf` skill for PDFs)
- [ ] Extract visual assets (figures, tables, diagrams, charts) → `knowledge/assets/<source-id>/`
- [ ] Extract ALL named entities → `knowledge/entities/`
- [ ] Extract ALL topics → `knowledge/topics/`
- [ ] Extract ALL concrete ideas → `knowledge/ideas/`
- [ ] Extract ALL locations mentioned → `knowledge/locations/`
- [ ] Extract ALL dates/events → `knowledge/timeline/`
- [ ] Build citation graph (if applicable) → `knowledge/citations/`
- [ ] Write source analysis → `knowledge/sources/`
- [ ] Cross-reference with existing KB entries → add reciprocal `[[wikilinks]]`
- [ ] Check for contradictions with existing KB → `knowledge/controversies/`
- [ ] Consider meta-analysis opportunities → `knowledge/meta/`
- [ ] Update `index.md`
- [ ] Append one line to `log.md`: `YYYY-MM-DD add <source-id> | +NE +NT +NI +NC +NTL`
- [ ] Mark task done (`state.py update-phase --phase done`)

## Article / Blog Post

Typically fits in one session. No chunking needed.

1. Read the full text
2. Identify: author, publication date, publication venue
3. Extract visual assets: if source has diagrams, charts, or key figures, extract them to `knowledge/assets/<source-id>/` using `/pdf` skill's `extract_images.py` or `render.py`
4. Create entity entry for author (or update existing)
5. Extract the core argument/thesis → idea entry
6. Extract supporting evidence → fold into idea entry or create sub-ideas
7. Extract all mentioned entities, topics, locations, dates
8. Embed extracted figures in relevant entries using `![[knowledge/assets/<source-id>/<name>.png]]`
9. Note any claims that conflict with existing KB → controversy entry
10. Write source analysis with summary + key takeaways
11. Cross-link everything

## Academic Paper

Always has citation tracking. Often fits in one session.

1. Read abstract → plan what to extract
2. Read full paper
3. **Extract visual assets** (mandatory for papers with figures/tables):
   - Use `/pdf` `extract_images.py` → save to `knowledge/assets/<source-id>/`
   - Use `/pdf` `render.py` on pages with key figures, architecture diagrams, result tables, or algorithm pseudocode that aren't captured as embedded images
   - Name descriptively: `transformer-architecture.png`, `bleu-score-comparison.png`, `algorithm-1-training-loop.png`
   - Skip: decorative headers, journal logos, page numbers
4. Create entity entries for ALL authors
5. Extract methodology → topic or meta entry if novel
6. Extract findings → idea entries (attribute to authors + paper). Embed relevant figures: `![[knowledge/assets/<source-id>/<name>.png]]`
7. Extract limitations acknowledged by authors → note in source analysis
7. **Citation graph** (mandatory for papers):
   - For each in-text citation: record exact sentence + reference
   - Create citation entries in `knowledge/citations/`
   - Create stub entries for referenced works not yet in KB
   - Flag bibliography items never cited in text
8. Cross-reference with existing KB
9. If this paper contradicts another in KB → controversy entry

## Book

Multi-session. Use task state for continuity. Books — especially textbooks — are the densest source type. A 26-chapter textbook can yield 50–100+ entities, 100+ citations, 20+ timeline entries, and multiple controversies. Skimming is the #1 failure mode.

### Session 1 — Plan

1. Read table of contents, preface, and any "guided reading" sections
2. Create task items: one per chapter + one per part/section boundary + one "synthesis" item. Titles MUST include chapter number and name (e.g. `Ch 7: Design and implementation (pp. 176-204)`) and part boundaries (e.g. `Part 2 aggregation: Dependability and Security (Ch 10-15)`). Part-level aggregation items are NOT optional — without them, book-level synthesis must jump from 26 chapters to one summary, which is too large a gap.
3. If the book has a bibliography or references section, scan it to estimate citation density

### Sessions 2-N — Per Chapter

For each chapter, complete ALL of these before marking done:

1. **Read the full chapter** — do not skim
2. **Understand deeply (MANDATORY — BEFORE any extraction):**
   Answer these questions in your head before creating a single entry:
   - What is the chapter's core argument in your own words? (not a summary — the argument)
   - What here would surprise a senior engineer? What goes against conventional wisdom?
   - What is the single most important sentence or paragraph? Why?
   - What does this chapter teach that you can't learn from the topic's Wikipedia page?
   - What non-obvious connection exists to earlier chapters or other KB entries?
   
   **Include your answers in checkpoint notes.** They force deep processing. If you can't answer them, you read the words but didn't understand the chapter — read it again.
3. **Extract visual assets (MANDATORY)** — scan every page of the chapter. Use `/pdf` `render.py` on pages with figures, tables, diagrams, charts, architecture drawings, algorithm pseudocode, data tables, or workflow illustrations. Use `/pdf` `extract_images.py` for embedded images. A chapter with zero extracted assets is almost certainly a failed extraction — most non-trivial chapters contain at least one figure or table. Save to `knowledge/assets/<source-id>/ch<N>-<descriptive-name>.png`.
4. **Extract EVERY named person** → entity entries. Each named person MUST get an entity entry (or update an existing one). A typical textbook chapter mentions 5–15 individuals.
5. **Extract practical insights** (MANDATORY for every chapter) — this is what makes the KB USEFUL to an engineer:
   - Decision tables: "when X, use Y; when Z, use W" → idea entries with tag `practical`
   - Implementation patterns and architecture blueprints → idea entries
   - Common pitfalls, gotchas, failure modes with causes and fixes → idea entries
   - Design heuristics and rules of thumb → idea entries
   - Deployment/scaling/operational considerations → idea entries
   - Worked examples showing how theory applies in practice → fold into idea entries
   - Think: "if I were building this system tomorrow, what from this chapter would I need?"
6. **Extract topics** → topic entries for each distinct subject area the chapter covers
7. **Extract ideas** → idea entries for specific proposals, frameworks, methods, theorems attributed to someone (e.g. "Lehman's Laws of Software Evolution", "Boehm's spiral model"). Ideas are attributable to a person; topics are not.
8. **Extract locations** → if the chapter mentions specific places (conferences, labs, companies)
9. **Extract dates** → timeline entries for every year/event mentioned (e.g. "NATO Software Engineering Conference (1968)", "Agile Manifesto (2001)")
10. **Citation tracking** (mandatory for ALL sources — not just those with formal bibliographies):
   - **Academic references**: "(Royce, 1970)", "[Parnas, 1972]", "as shown by Brooks (1975)" → citation entry
   - **Inline URLs**: hyperlinks or bare URLs to papers, articles, docs, Wikipedia, GitHub repos → citation entry. The URL IS the reference — treat it exactly like a numbered citation
   - **Footnote references**: footnotes pointing to external works → citation entry
   - **Informal mentions**: "see the scikit-learn documentation", "described on the project wiki" → citation entry if the target is identifiable
   - Create stub entries for referenced works not yet in KB
   - If the chapter has a "Further Reading" or "References" section, note bibliography items not cited in-text
11. **Embed extracted figures** in relevant entries using `![[knowledge/assets/<source-id>/<name>.png]]`
12. **Cross-link with entries from previous chapters** — wikilinks both directions
13. **Detect contradictions** with existing KB or earlier chapters → controversy entries

#### Per-chapter quality gate (check BEFORE marking done)

**Hard minimums — a chapter that fails ANY of these is incomplete:**

| Category | Minimum | Why |
|----------|---------|-----|
| Entities (E) | ≥ 3 | Nearly every textbook chapter names researchers, historical figures, or practitioners |
| Citations (C) | ≥ 3 | Textbooks cite prior work throughout — zero citations means you skimmed |
| Distinct categories | ≥ 3 of {E, T, I, C, TL} | A `+1T` checkpoint is ALWAYS drift. Real chapters produce entities + citations + at least one more type |
| Visual assets | ≥ 1 (if chapter has any figures/tables) | Most non-trivial chapters have at least one figure, table, or diagram |

If your extraction doesn't meet these minimums, **re-read the chapter from the beginning** — do not try to "patch" from memory.

**Completeness checks — verify each before marking done:**

- [ ] Every named person in the chapter text has an entity entry
- [ ] Every in-text reference has a citation entry
- [ ] Every year/date mentioned has a timeline entry (or updates an existing one)
- [ ] Figures/diagrams/tables extracted as visual assets and embedded in entries (zero assets = re-check the chapter)
- [ ] Practical insights extracted: decision tables, pitfalls, implementation patterns, heuristics (if the chapter has ANY "how to" or "lessons learned" content, it MUST be extracted)
- [ ] All new entries interlinked with `[[wikilinks]]`
- [ ] Math explanations include plain-language intuition alongside formulas
- [ ] **Insight quality check**: at least one entry contains something a senior engineer would find surprising, counterintuitive, or non-obvious — if every entry reads like a Wikipedia summary, you filed but didn't think

If any box is unchecked, go back and fix it before marking the chapter done.

#### Checkpoint (mandatory — do this AFTER quality gate, BEFORE moving to next chapter)

```bash
state.py update-item --task-id <task-id> --item-id iN --status done \
  --notes "+5E +2T +1I +8C +3TL: dijkstra, parnas, brooks; software-processes, waterfall; lehman-laws" \
  --state-dir <kb>/.kb/tasks
```

The notes format: `+NE +NT +NI +NC +NTL: key-entity-names; key-topics; key-ideas`. This is what the LLM reads to reconstruct context after compaction. Be specific enough that a future you — with zero context — knows what this chapter contributed. **If any mandatory category shows +0 (especially E or C), you skipped extraction — go back and re-read the chapter before marking done.**

### Part-Level Aggregation (MANDATORY for books with parts/sections)

When a book has explicit parts (e.g. \"Part 2: Dependability and Security, Chapters 10-15\"), you MUST have a task item for each part boundary (created in Session 1). Even if the book doesn't have explicit parts, group every 4-6 chapters into logical clusters and create aggregation items for them.

1. After finishing all chapters in a part, process the part-level aggregation item
2. Write checkpoint notes summarizing cross-chapter themes: `state.py update-item --notes \"Part 2 themes: dependability vs security trade-off, Reason's Swiss cheese...\"`
3. Create or update topic entries for part-level themes that span multiple chapters
4. Create cross-chapter idea entries for patterns visible only at the part level
5. Identify inter-chapter connections within the part → add wikilinks

This is the middle level of hierarchical aggregation. Skipping it means the book-level synthesis must jump from 26 individual chapters to one summary — producing shallow, useless output.

### Final Session — Synthesis

Book-level aggregation — the top of the hierarchy for this source:

1. Read checkpoint notes from all completed items — these are your chapter and part summaries
2. Read the topic/idea/entity entries created during extraction (NOT the raw source)
3. Write the source analysis — this is a **finished analytical document**: book summary, overarching thesis, cross-part themes, key extractions list, bibliography analysis, figures & tables. No checklists, no progress tracking, no session logs.
4. Create cross-part topic connections (themes that span the entire book)
5. Review the complete timeline extracted — fill any gaps
6. Identify controversies/debates the book discusses across parts → controversy entries
7. Meta-analysis if related sources exist in KB (e.g. same topic, contrasting viewpoints) → `knowledge/meta/`
8. Update index, log, mark task done

See [Book Processing Pattern](#book-processing-pattern) below.

## Video / Podcast Transcript

Treat like an article but with speaker attribution.

1. If no transcript exists, tell the user (you can't transcribe)
2. If transcript provided: identify all speakers → entity entries
3. Extract claims/ideas → attribute to specific speaker
4. Note: timestamps are useful for the user, include them in entries when available
5. Extract all entities, topics, ideas mentioned
6. Source analysis notes it's a transcript (less formal than written sources)

## URL Reference

No full text available — just metadata and user-provided context.

1. Source registered as reference stub (no file copy)
2. Create minimal entries from what you know (title, author, topic)
3. Mark entries as `stub: true` in frontmatter — they need enrichment later
4. If user provides notes about the URL, extract from those
5. Flag in source analysis: "Reference only — full text not ingested"

## Any Large Source (Generic Pattern)

When a source is too large for a single pass — regardless of type — apply hierarchical processing:

1. **Identify natural chunks**: chapters, sections, episodes, parts. Create task items for each.
2. **Process chunk by chunk**: exhaustive extraction per chunk, quality gate, checkpoint notes.
3. **Aggregate at group boundaries**: when a logical group of chunks is done (e.g. all chapters in a part, all episodes in a season), write a group-level summary in source analysis.
4. **Synthesize at source level**: after all chunks, write source-level analysis from group summaries.
5. **Cross-reference with KB**: meta-analyses, contradiction detection across sources.

Signs a source needs this pattern:
- More than ~30 pages or ~15K words
- Has internal chapter/section structure
- You can't read and extract it all before context fills up
- The user says to process it "thoroughly" or "exhaustively"

When in doubt, use this pattern. The overhead of task items + checkpoint notes is tiny compared to losing work to context compaction.

## Citation Tracking Examples

### Example: Numbered in-text citation

Source text: "Recent work has shown that transformer architectures outperform RNNs on most NLP benchmarks [3][7]."

Create `knowledge/citations/chen-2023-cites-ref-3.md`:

```markdown
---
type: citation
created: 2025-01-15
source-ids: [chen-2023]
cited-work: "Author et al., 2020, Title of Paper"
cite-key: "[3]"
---

# chen-2023 cites Author et al. 2020

**Citing source**: [[chen-2023-analysis]]

**Context**: "Recent work has shown that transformer architectures outperform RNNs on most NLP benchmarks [3][7]."

**Claims supported**: Transformer superiority over RNNs on NLP benchmarks.

**Significance**: Establishes the empirical basis for the paper's choice of transformer architecture.

**See also**: [[transformers]], [[recurrent-neural-networks]], [[nlp-benchmarks]]
```

### Example: Inline URL citation

Source text (practitioner book or blog): "Bootstrap Thompson Sampling (see https://arxiv.org/abs/1410.4009) approximates the posterior without conjugate priors."

Create `knowledge/citations/sweet-2023-cites-eckles-kaptein-2014.md`:

```markdown
---
type: citation
created: 2025-01-15
source-ids: [sweet-2023]
cited-work: "Eckles & Kaptein, 2014, Thompson Sampling with the Online Bootstrap"
cite-url: "https://arxiv.org/abs/1410.4009"
---

# sweet-2023 cites Eckles & Kaptein 2014

**Citing source**: [[sweet-2023-analysis]]

**Context**: "Bootstrap Thompson Sampling approximates the posterior without conjugate priors."

**Claims supported**: Bootstrap as a practical alternative to exact Bayesian posterior computation.

**Significance**: Key enabler for Thompson Sampling in production — removes the conjugate prior requirement that limits real-world applicability.

**See also**: [[bootstrap-thompson-sampling]], [[olivier-chapelle]]
```

**Note**: Inline URLs, hyperlinks, footnote URLs, and informal references ("see the scikit-learn docs") are ALL valid citations. A book with no formal bibliography but 30 inline URLs has 30 citations — not zero.

### Example: Unreferenced bibliography item

In source analysis (`knowledge/sources/chen-2023-analysis.md`):

```markdown
## Bibliography Analysis

### Unreferenced entries
- [12] Smith et al., 2018 — listed in bibliography but never cited in the paper text
- [15] Jones, 2019 — listed in bibliography but never cited in the paper text
```

## Book Processing Pattern

For a book with P parts and N chapters:

```
Session 1:  Read TOC → state.py add-items (ch1, ..., chN, part1-agg, ..., partP-agg, synthesis)
Session 2:  state.py pending → process ch1 → quality gate → checkpoint → done
Session 3:  state.py pending → process ch2 → quality gate → checkpoint → done
...
After last chapter in Part 1:  process part1-agg → part-level notes in source analysis → done
...
Session N+P+1: state.py pending → synthesis → update-phase done
```

Each chapter session:
1. Run `open.py` to reload KB context
2. Run `state.py pending` to see next chapter + recent checkpoint notes
3. **Read the checkpoint notes from the FIRST 3 completed items** — these set the extraction density floor. If recent items show lower counts than early ones, you are drifting and must match early density.
4. **Re-read the per-chapter quality gate above** (hard minimums table + completeness checks) — after compaction you will NOT remember the specific requirements
5. Read full chapter from source
6. **Understand deeply** — answer the 5 deep-reading questions (step 2 in per-chapter checklist) BEFORE extracting anything
7. **Extract exhaustively** — every named person, every reference (including inline URLs), every date, every concept
8. Cross-link with entries from previous chapters
9. **Run per-chapter quality gate** — verify hard minimums (≥3 E, ≥3 C, ≥3 categories) AND check all boxes including insight quality check
10. **Write checkpoint notes** via `update-item --notes "..."` — include deep-reading answers + extraction tally
11. Mark chapter done

Part-level aggregation session:
1. Read checkpoint notes from completed chapter items in this part
2. Create/update topic entries for cross-chapter themes within the part
3. Add inter-chapter wikilinks within the part
4. Write part-level checkpoint notes via `update-item --notes`

### Extraction density expectations (textbooks)

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

### Why exhaustive extraction matters

The LLM's instinct is to summarize — to compress a chapter into its 3-5 key points. That's the opposite of what the KB needs. The KB is a **long-term memory** that accumulates facts across sources. A person mentioned in passing in Chapter 9 might be a central figure in a later source. A citation to an obscure 1972 paper might become critical when that paper is added to the KB. Extract everything — the KB's value grows combinatorially with coverage.

Synthesis session:
1. Read checkpoint notes from all completed items (NOT the raw source)
2. Read the topic/idea/entity entries created during extraction
3. Write book-level source analysis — this is the ONLY time you write the source analysis for a book. It is a finished analytical document: summary, key themes, cross-references, bibliography analysis. No checklists, no progress tracking.
4. Create cross-chapter connections
5. Identify overarching themes → topic entries
6. Meta-analysis if other books on same topic exist

## Compaction

After extracting knowledge from a source chunk, the entries you created ARE the knowledge. You don't need to re-read the raw source text.

Why this works:
- Each entity/topic/idea/citation entry captures the relevant facts
- Wikilinks preserve the relationships
- Source analysis captures the big picture
- Citation entries preserve exact quote contexts
- Checkpoint notes on task items record what was extracted per chunk

When resuming after context compaction or session break:
1. Run `state.py pending` — read the `recent_completed` notes to reconstruct context
2. Read the source analysis chapter notes for the narrative arc so far
3. Read your extracted entries from recent chunks (they're short, focused markdown)
4. Do NOT re-read the raw source chunks you already processed
5. Continue with the next pending item at the same extraction density
6. **NEVER bulk-read remaining chapters to "catch up."** After compaction, process ONE chapter at a time — read it, extract exhaustively, checkpoint, move on. Bulk-reading multiple chapters at once produces shallow, summary-level extraction that misses practical insights, named entities, and citations. If 15 chapters remain, that's 15 separate read-extract-checkpoint cycles. There are no shortcuts.
