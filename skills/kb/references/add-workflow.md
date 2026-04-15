# kb:add Workflow Reference

Generic extraction framework for all source types. Source-type-specific workflows are in separate reference files — load only what you need.

## Contents

1. [Universal Checklist](#universal-checklist)
2. [Source Type Routing](#source-type-routing)
3. [Any Large Source (Generic Pattern)](#any-large-source-generic-pattern)
4. [Compaction](#compaction)
5. [Multi-Perspective Extraction](#multi-perspective-extraction)
6. [Question Generation](#question-generation)
7. [Creative Cross-Linking](#creative-cross-linking)
8. [Backlink Enforcement](#backlink-enforcement)

## Universal Checklist

Every `kb:add` regardless of source type:

- [ ] Register source (`add_source.py`) — pass `--identifier TYPE:VALUE` for every bibliographic identifier found (ISBN, DOI, ISSN, arXiv, PMID, URL). Check copyright page (books), header/footer (papers), masthead (journals), metadata block (web articles).
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
- [ ] **Multi-perspective pass** — re-read source through a different lens (see [Multi-Perspective Extraction](#multi-perspective-extraction))
- [ ] **Question generation** — 1-3 grounded questions → `knowledge/questions/` (see [Question Generation](#question-generation))
- [ ] **Creative cross-linking** — random walk through 10 diverse existing entries (see [Creative Cross-Linking](#creative-cross-linking))
- [ ] Consider meta-analysis opportunities → `knowledge/meta/`
- [ ] **Backlinks** — every new wikilink has a reciprocal link. ALL of them. (see [Backlink Enforcement](#backlink-enforcement))
- [ ] Update `index.md`
- [ ] Append one line to `log.md`: `YYYY-MM-DD add <source-id> | +NE +NT +NI +NC +NTL`
- [ ] Mark task done (`state.py update-phase --phase done`)

## Source Type Routing

Determine the source type, then read the matching workflow file:

| Source type | Workflow | When to use |
|---|---|---|
| Article / blog post | [article-workflow.md](article-workflow.md) | Single-session web articles, blog posts, essays |
| Academic paper | [paper-workflow.md](paper-workflow.md) | Papers with abstracts, methodology, citation graphs |
| Book / textbook | [book-workflow.md](book-workflow.md) | Multi-session, chapter-by-chapter with hierarchical analysis documents |
| Video / podcast | [video-url-workflow.md](video-url-workflow.md) | Transcripts with speaker attribution |
| URL reference | [video-url-workflow.md](video-url-workflow.md#url-reference) | External link, no full text available |
| Collection (magazine / journal / proceedings / anthology) | [collection-workflow.md](collection-workflow.md) | Multiple independent articles by different authors, grouped into an issue or volume |

For citation examples, see [citation-tracking.md](citation-tracking.md#examples).

For any source too large for a single pass (regardless of type), also read [Any Large Source](#any-large-source-generic-pattern) below.

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

## Multi-Perspective Extraction

After your initial stochastic exploration of a chunk, do ONE additional perspective pass. Pick the perspective that's most different from your natural reading:

| If your first pass was… | Use this lens |
|---|---|
| Theoretical / conceptual | **Practitioner**: "What would I actually build with this? What are the pitfalls?" |
| Implementation-focused | **Skeptic**: "What claims are weak? What's the strongest counterargument?" |
| Historical / biographical | **Engineer**: "What's the technical mechanism? What are the constraints?" |
| Broad survey | **Deep diver**: "What's the hidden insight in paragraph 3 that the heading doesn't mention?" |

**How to execute**: After filing your initial entries, explicitly say to yourself: "Now I re-read this chunk as a [perspective]." Re-scan the source material (NOT your entries — the source) looking through that lens. Create or enrich entries based on what the new perspective surfaces. This is typically 1-3 additional entries or significant additions to existing entries.

**Why this works**: An LLM's first pass is dominated by whichever features the training distribution highlights. A second pass with an explicit perspective shift activates different attention patterns, suppressing already-activated features and surfacing overlooked content. Two passes at 80% coverage with different biases exceed one pass at 90%.

**Quality gate addition**: The checkpoint notes MUST include which perspective was used: `+5E +2T +1I +8C [practitioner pass: +1I practical]`.

## Question Generation

After extracting knowledge from a chunk, generate 1-3 questions. These go in `knowledge/questions/`.

**What makes a good question:**
- The source explicitly says "this remains an open problem" or "future work includes…"
- The source's methodology has an obvious limitation it doesn't address
- Two claims in the source (or between this source and existing KB entries) create tension without resolution
- The source mentions a topic in passing without explaining it, and the explanation would be valuable

**What is NOT a good question:**
- Generic "what if" speculation with no grounding in the source text
- Questions the source actually answers (even if you missed the answer)
- "Wouldn't it be interesting if…" — that's a hypothesis, not a gap

**Hallucination guardrail**: Every question MUST include in its `## Origin` section:
1. A `**Source**: [[source-analysis]]` wikilink
2. The exact passage (quoted or closely paraphrased) that prompted the question
3. If the question comes from cross-source tension, cite BOTH sources

If you cannot point to a specific passage or observation, the question is probably hallucinated. Do not create it.

**Checkpoint notes**: Include question count: `+5E +2T +1I +8C +1Q: "Does X scale beyond Y?"`.

## Creative Cross-Linking

This happens in Phase 5 (Cross-Reference & Analyze) and is MANDATORY, not optional.

**The random walk**: After writing entries for a new source, read **10 existing entries chosen to maximize diversity** — not the most obviously related entries (you already linked those during Phase 3). Pick entries from:
- Different time periods than the new source
- Different domains/topics
- Different source types (if the new source is a paper, look at entries from books)
- Entries with few existing links (they need connections the most)

**What to look for**: Structural parallels, shared mechanisms, analogous problems in different domains, historical echoes, methodological similarities, shared influences, unexpected terminology overlaps.

**How to record**: If you find a connection worth noting:
- Add reciprocal wikilinks between the entries
- If the connection is surprising or non-obvious, create a `knowledge/meta/` entry explaining it
- If the connection reveals a gap, create a `knowledge/questions/` entry

**Guardrail**: Every cross-link MUST be justified by content in the actual entries. You must be able to point to specific text in both entries that supports the connection. "These seem related" is not sufficient — "Both entries describe hierarchical decomposition as a complexity management strategy" is.

**This is the serendipity engine.** It exploits the LLM's ability to recognize structural patterns across domains — something humans are slow at because they read entries sequentially. Don't skip it. Don't do it mechanically by linking the 10 most keyword-similar entries — that just creates the same links search.py would find. The value is in the *unexpected* connections.

## Backlink Enforcement

**EVERY wikilink MUST be reciprocal.** If entry A links to entry B, then entry B MUST link back to entry A. This is not optional and is not subject to "too many" exceptions.

When `lint.py` reports N missing backlinks, fix ALL N of them. Not "the most important ones." Not "I'll fix them later." All of them. If there are 2200, batch them: fix 50, save, fix 50, save. This is mechanical work — you don't need to read the full entries, just add the wikilink in the appropriate section (usually `## See also` or `## Related`).

**Why non-negotiable**: Obsidian backlinks are the KB's navigation system. A missing backlink means an entry is invisible from the other side. At 2200 missing backlinks, the knowledge graph has 2200 invisible connections — the KB is effectively a bag of files, not a graph.
