# kb:add Workflow Reference

Detailed checklists for the knowledge extraction pipeline. Linked from SKILL.md.

## Contents

1. [Universal Checklist](#universal-checklist)
2. [Source Type: Article / Blog Post](#article--blog-post)
3. [Source Type: Academic Paper](#academic-paper)
4. [Source Type: Book](#book)
5. [Source Type: Video / Podcast Transcript](#video--podcast-transcript)
6. [Source Type: URL Reference (no full text)](#url-reference)
7. [Citation Tracking Examples](#citation-tracking-examples)
8. [Book Processing Pattern](#book-processing-pattern)
9. [Compaction — Why You Don't Need the Raw Text Again](#compaction)

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
- [ ] Append to `log.md`
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
2. Create task items: one per chapter + one "synthesis" item. Titles MUST include chapter number and name (e.g. `Ch 7: Design and implementation (pp. 176-204)`)
3. If the book has a bibliography or references section, scan it to estimate citation density

### Sessions 2-N — Per Chapter

For each chapter, complete ALL of these before marking done:

1. **Read the full chapter** — do not skim
2. **Extract visual assets** — diagrams, figures, tables → `knowledge/assets/<source-id>/`
3. **Extract EVERY named person** → entity entries. Textbooks reference researchers by name in running text (e.g. "Dijkstra's early work on…", "as Parnas showed in 1972…"). Each named person MUST get an entity entry (or update an existing one). A typical textbook chapter mentions 5–15 individuals.
4. **Extract topics** → topic entries for each distinct subject area the chapter covers
5. **Extract ideas** → idea entries for specific proposals, frameworks, methods, theorems attributed to someone (e.g. "Lehman's Laws of Software Evolution", "Boehm's spiral model"). Ideas are attributable to a person; topics are not.
6. **Extract locations** → if the chapter mentions specific places (conferences, labs, companies)
7. **Extract dates** → timeline entries for every year/event mentioned (e.g. "NATO Software Engineering Conference (1968)", "Agile Manifesto (2001)")
8. **Citation tracking** (mandatory for textbooks):
   - For each in-text reference (e.g. "(Royce, 1970)", "[Parnas, 1972]", "as shown by Brooks (1975)") create a citation entry
   - Create stub entries for referenced works not yet in KB
   - If the chapter has a "Further Reading" or "References" section, note bibliography items not cited in-text
9. **Embed extracted figures** in relevant entries using `![[knowledge/assets/<source-id>/<name>.png]]`
10. **Cross-link with entries from previous chapters** — wikilinks both directions
11. **Detect contradictions** with existing KB or earlier chapters → controversy entries
12. **Write chapter-level notes** in source analysis — a 2-3 sentence summary of the chapter plus what was extracted

#### Per-chapter quality gate (check BEFORE marking done)

- [ ] Every named person in the chapter text has an entity entry
- [ ] Every in-text reference has a citation entry
- [ ] Every year/date mentioned has a timeline entry (or updates an existing one)
- [ ] Key figures/diagrams extracted as visual assets and embedded in entries
- [ ] Chapter notes written in source analysis
- [ ] All new entries interlinked with `[[wikilinks]]`

If any box is unchecked, go back and fix it before marking the chapter done.

### Final Session — Synthesis

1. Write book-level source analysis (summarizes all chapters, cross-cutting themes)
2. Create cross-chapter topic connections (themes that span multiple chapters)
3. Build complete timeline from all extracted dates
4. Identify controversies/debates the book discusses across chapters → controversy entries
5. Meta-analysis if related sources exist in KB (e.g. same topic, contrasting viewpoints)
6. Update index, log, mark task done

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

## Citation Tracking Examples

### Example: In-text citation

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

### Example: Unreferenced bibliography item

In source analysis (`knowledge/sources/chen-2023-analysis.md`):

```markdown
## Bibliography Analysis

### Unreferenced entries
- [12] Smith et al., 2018 — listed in bibliography but never cited in the paper text
- [15] Jones, 2019 — listed in bibliography but never cited in the paper text
```

## Book Processing Pattern

For a book with N chapters:

```
Session 1:  Read TOC → state.py add-items (ch1, ch2, ..., chN, synthesis)
Session 2:  state.py pending → process ch1 → quality gate → update-item ch1 done
Session 3:  state.py pending → process ch2 → quality gate → update-item ch2 done
...
Session N+1: state.py pending → process chN → quality gate → update-item chN done
Session N+2: state.py pending → synthesis → update-phase done
```

Each chapter session:
1. Run `open.py` to reload KB context
2. Run `state.py pending` to see next chapter
3. Read full chapter from source
4. **Extract exhaustively** — every named person, every in-text reference, every date, every concept
5. Cross-link with entries from previous chapters
6. **Run per-chapter quality gate** — check all boxes before proceeding
7. Mark chapter done

### Extraction density expectations (textbooks)

These are baselines, not caps. Real chapters often exceed these:

| Entry type | Typical per chapter | Notes |
|-----------|-------------------|-------|
| Entities  | 5–15              | Every named person in running text. Authors of cited works. Historical figures. |
| Topics    | 1–3               | Major subject areas the chapter introduces or deepens |
| Ideas     | 1–5               | Specific named models, methods, proposals (attributable) |
| Citations | 5–20              | Every "(Author, Year)" or "[N]" reference in text |
| Timeline  | 1–5               | Years explicitly mentioned with events |
| Locations | 0–2               | Conferences, institutions, labs |

A 26-chapter textbook should typically produce:
- 50–150 entity entries (not 5)
- 50–200 citation entries (not 0)
- 15–40 timeline entries (not 4)
- 3–8 controversy entries (not 0)

### Why exhaustive extraction matters

The LLM's instinct is to summarize — to compress a chapter into its 3-5 key points. That's the opposite of what the KB needs. The KB is a **long-term memory** that accumulates facts across sources. A person mentioned in passing in Chapter 9 might be a central figure in a later source. A citation to an obscure 1972 paper might become critical when that paper is added to the KB. Extract everything — the KB's value grows combinatorially with coverage.

Synthesis session:
1. Read all chapter-level entries (NOT the raw source)
2. Write book-level source analysis
3. Create cross-chapter connections
4. Identify overarching themes → topic entries
5. Meta-analysis if other books on same topic exist

## Compaction

After extracting knowledge from a source chunk, the entries you created ARE the knowledge. You don't need to re-read the raw source text.

Why this works:
- Each entity/topic/idea/citation entry captures the relevant facts
- Wikilinks preserve the relationships
- Source analysis captures the big picture
- Citation entries preserve exact quote contexts

When resuming a multi-session task:
- Read your extracted entries (they're short, focused markdown)
- DON'T re-read the raw source chunks you already processed
- Use the entries as context for processing the next chunk
