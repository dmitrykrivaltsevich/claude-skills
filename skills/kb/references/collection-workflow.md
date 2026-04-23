# Collection Workflow (Magazines, Journals, Proceedings, Anthologies)

Multi-session extraction for collections of independent articles by different (or same) authors, grouped into an issue or volume. Applies to: magazine issues, journal issues, conference proceedings, edited volumes, essay anthologies, special reports with named sections by different authors.

## Key difference from books

In a book, chapters build on each other sequentially — the argument develops. In a collection, **articles are independent units**. Each article has its own author(s), its own argument, and its own citations. The editorial value — what makes it a *collection* rather than a bag of articles — emerges at the issue level: why were these articles grouped together? What themes does the editor see? What conversation is happening across the articles?

## Contents

1. [Session 1 — Plan](#session-1--plan)
2. [Sessions 2-N — Per Article](#sessions-2-n--per-article)
3. [Issue-Level Synthesis](#issue-level-synthesis)
4. [Cross-Issue Analysis](#cross-issue-analysis)
5. [Quick Reference: Session Template](#quick-reference-session-template)
6. [Anti-Patterns](#anti-patterns)

---

## Session 1 — Plan

1. Read the table of contents, editorial/introduction, and any "about this issue" text
2. **Register the collection as a single source** with `add_source.py`. Source ID: `<publication>-<year>-<issue>` (e.g. `acm-queue-2024-vol22-3`, `ieee-sw-2025-jan`, `harpers-2025-04`)
3. **Create task items**: one per article + one "issue-synthesis" item. Titles MUST include article title and author(s): e.g. `Art 3: "Scaling Distributed Systems" by Chen & Park (pp. 28-35)`
4. Note the editorial framing — the introduction often states why these articles were grouped. Record this in your planning notes; it feeds synthesis later.
5. If an article is long (>15 pages), treat it as a mini-book: sub-chunk it, but still produce a single article analysis brief for it.

**Source ID convention for individual articles**: Each article within the collection gets its own source-id for citation purposes: `<collection-id>-<first-author>` (e.g. `acm-queue-2024-vol22-3-chen`). This lets the citation graph distinguish "Chen's article in this issue" from the collection as a whole.

## Sessions 2-N — Per Article

Each article is an independent extraction unit. Process it like a standalone article or paper — but with collection-aware cross-linking.

### Extract

1. Run `state.py pending` to see next article
2. Read the full article text (use PDF reading strategy from [book-workflow.md](book-workflow.md#pdf-reading-strategy--text-first-images-one-at-a-time) if needed)
3. **Create entity entries for ALL authors** of this article — not just the collection editors. Each article may have different authors; this is a primary difference from books.
4. Extract using the standard two-layer pattern: stochastic exploration first, then quality gate. Run [practical-extraction.md](practical-extraction.md) during this first pass so heuristics, deployment constraints, pitfalls, and failure modes become `idea-kind: practical` entries while the article is fresh.
5. **Cross-link with prior articles in this collection** — if article 5 discusses something article 2 covered, add wikilinks. These cross-article links are the collection's intellectual structure.
6. Citation tracking: each article has its own citation graph. Create citation entries attributed to the article-level source-id (e.g. `acm-queue-2024-vol22-3-chen-cites-...`).

### Quality Gate

Same hard minimums as book chapters. For short articles (1-3 pages), relax to ≥1 per category instead of ≥3, but maintain ≥3 distinct categories.

| Category | Minimum (4+ pages) | Minimum (1-3 pages) |
|----------|-------------------|---------------------|
| Entities (E) | ≥ 3 | ≥ 1 |
| Citations (C) | ≥ 3 | ≥ 1 |
| Distinct categories | ≥ 3 of {E, T, I, C, TL} | ≥ 3 of {E, T, I, C, TL} |

If an article contains implementation advice, debugging lessons, checklists, or failure analysis, it MUST produce at least one `idea-kind: practical` entry. If it does not, the article analysis brief MUST state `No practical insight justified from this article.`

### Article Analysis Brief

After the quality gate, write `knowledge/sources/<collection-id>-art<NN>-analysis.md` (e.g. `acm-queue-2024-vol22-3-art03-analysis.md`):

```yaml
---
type: article-analysis
created: YYYY-MM-DD
source-ids: [acm-queue-2024-vol22-3]
article: 3
title: "Scaling Distributed Systems"
authors: [chen, park]
pages: 28-35
---
```

**Required sections** (keep each to 3-8 sentences):

| Section | What to write | What NOT to write |
|---------|--------------|-------------------|
| `## Core argument` | What this article ARGUES — its thesis, not its topic. "The author argues X because Y, which implies Z." | NOT "This article covers X and Y." |
| `## Key insight` | The non-obvious takeaway. What would a reader miss from the title alone? What surprised you? | NOT a summary sentence restating the abstract. |
| `## Author perspective` | What lens does this author bring? Academic vs practitioner, senior vs emerging, insider vs outsider? How does their position shape their argument? | NOT just a label. Explain HOW their perspective shapes what they see and miss. |
| `## Critical questions` | 2-4 analytical questions this article raises. "Why does the author ignore X?", "What evidence would falsify this?", "How does this interact with [concept]?" | NOT comprehension questions. NOT "What did the author say about X?" |
| `## Connections to other articles in this issue` | Where this article agrees, disagrees, or complements other articles in the same collection. What conversation are they having, even if unintentionally? Wikilink to those article analysis briefs. | NOT "Article 1 discusses X and this article discusses Y." State the intellectual relationship. |

Every article analysis brief should also include `## Hidden Gems`, `## Know-How`, and when relevant `## Pitfalls / Failure Modes`. Link practical idea entries from `## Know-How`. If the article yields no honest operational guidance, write `No practical insight justified from this article.`

### Checkpoint

```bash
state.py update-item --task-id <task-id> --item-id iN --status done \
  --notes "+3E +1T +2I +5C: chen, park; distributed-scaling; cap-theorem-revisited" \
  --state-dir <kb>/.kb/tasks
```

## Issue-Level Synthesis

After ALL article task items are done, process the "issue-synthesis" item:

1. **Read all article analysis briefs** — these are your primary input. Pay special attention to the "Connections to other articles" and "Author perspective" sections.
2. **Re-read the editorial/introduction** — compare the editor's framing against what you actually found. Does the editorial's narrative match the articles' content, or is there tension?
3. **Write the collection source analysis** (`knowledge/sources/<collection-id>-analysis.md`):

**Required sections**:

| Section | What to write |
|---------|--------------|
| `## Editorial thesis` | What the editors say this collection is about. Quote or paraphrase the introduction. |
| `## Actual themes` | What themes ACTUALLY emerge from the articles — which may diverge from the editorial framing. Group articles by theme. |
| `## Conversation map` | Where articles agree, where they disagree, where they talk past each other. This is the analytical core — it reveals the intellectual structure the editors may not have articulated. |
| `## Author landscape` | Who contributed, what perspectives they brought. Which authors are already in the KB from other sources? How does this enrich their entity profiles? |
| `## Know-How` | Cross-article practical entries worth resurfacing. Link the strongest `idea-kind: practical` entries and note which article analysis brief contributed each one. |
| `## Gaps and silences` | What topics are conspicuously absent? What questions do the articles collectively raise but none answer? |
| `## Bibliography patterns` | Do the articles cite overlapping references? Are there works that multiple articles rely on but none analyze deeply? These are candidates for future source acquisition. |

If the issue-level synthesis surfaces recurring operational warnings, add a `## Pitfalls / Failure Modes` section as well.

4. **Create topic entries** for issue-level themes — themes that span multiple articles
5. **Create controversy entries** if articles disagree on a topic
6. **Create meta entries** if this collection relates to other sources in the KB
7. Update index, log, mark task done

## Cross-Issue Analysis

When the KB contains multiple issues of the same publication (or related publications):

1. **Compare source analyses** across issues — not individual articles. Each source analysis already summarizes its issue's themes.
2. **Track editorial evolution**: How do themes shift across issues? Is there a sustained conversation over multiple issues?
3. **Track author recurrence**: Do some authors appear across issues? Update their entity profiles with the arc of their contributions.
4. **Write meta entries** in `knowledge/meta/` for cross-issue patterns: `<publication>-theme-evolution.md`, `<publication>-author-network.md`

This is the cross-source level in the standard KB hierarchy and happens naturally during Phase 5 (Cross-Reference & Analyze) of subsequent collection ingestions.

## Quick Reference: Session Template

For a collection with N articles:

```
Session 1:  Read TOC + editorial → state.py add-items (art1, ..., artN, issue-synthesis)
Session 2:  state.py pending → process art1 → quality gate → article analysis brief → checkpoint → done
Session 3:  state.py pending → process art2 → quality gate → article analysis brief → checkpoint → done
...
Session N+1: read article analysis briefs + editorial → write issue source analysis → cross-issue meta → done
```

**Document hierarchy** (each level reads only the level below):

| Level | Document | Location | Reads from |
|-------|----------|----------|------------|
| Article | Article analysis brief | `knowledge/sources/<id>-art01-analysis.md` | Raw article text + entries |
| Issue | Source analysis | `knowledge/sources/<id>-analysis.md` | Article analysis briefs + editorial |
| Cross-issue | Meta entries | `knowledge/meta/` | Source analyses from multiple issues |

**Note**: Collections have a flatter hierarchy than books (no part-level aggregation needed) because articles are independent — you don't need the intermediate compression step. If a collection has explicit sections/tracks (e.g. a conference with tracks), treat them like book parts.

## Anti-Patterns

### Anti-pattern 1: "One article = one topic entry"

**What happens**: You create a single topic entry per article — essentially restating the article title. No entities, no citations, no ideas.

**The fix**: Each article is a full extraction unit. Apply the quality gate. A 10-page article should produce 5-15 entries, not 1.

### Anti-pattern 2: "Ignoring the editorial"

**What happens**: You extract each article in isolation and never write an issue-level synthesis. The collection's editorial structure — why these articles are together — is lost.

**The fix**: The editorial/introduction is critical metadata. The issue-level synthesis MUST include a "Conversation map" showing how articles relate. Without it, you've just ingested N independent articles and missed the collection's value.

### Anti-pattern 3: "Same-author blindness"

**What happens**: Multiple articles by the same author across issues, but you create separate entity entries or never connect them. The author's intellectual trajectory is lost.

**The fix**: Always check if the author already exists in the KB. If so, triangulate — update the existing entity with the new article's contribution, noting evolution or consistency in their thinking.

### Anti-pattern 4: "Flat citation graph"

**What happens**: All citation entries are attributed to the collection, not to specific articles. You can't tell which article cited which work.

**The fix**: Citation entries use the article-level source-id: `<collection-id>-<first-author>-cites-...`. The collection source-id appears in the article analysis brief, but the citation granularity is per-article.
