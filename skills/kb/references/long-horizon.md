# Long-Horizon Autonomous Work

## Contents

1. [Core Principle: Everything on Disk](#core-principle-everything-on-disk)
2. [Checkpoint Discipline](#checkpoint-discipline)
3. [Resumption Protocol](#resumption-protocol)
4. [Hierarchical Processing for Large Sources](#hierarchical-processing-for-large-sources)
5. [Preventing Trajectory Drift](#preventing-trajectory-drift)
6. [Context Management](#context-management)

---

Large sources require sustained work across many context windows. Context compaction, session breaks, and tool errors WILL happen. This skill is designed for resilience — the LLM must be able to lose its entire context and fully recover from disk state alone.

## Core Principle: Everything on Disk

Your context window is volatile. The KB's files and task state are permanent. Every decision, every extraction, every checkpoint MUST be written to disk before moving on. If you crash after writing, no work is lost. If you crash before writing, you redo only that one chunk.

For any broad JSON result (`open.py`, `search.py`, `lint.py`, `related.py`, `graph.py`, `topology.py`, `state.py`), prefer `--output /path/to/artifact.json`. Then reopen only the slice you need with `json_query.py` instead of reloading the entire artifact. For markdown/text artifacts such as KB entries, chapter briefs, source analyses, exported markdown, or working notes, reopen only the needed heading, chunk, or exact line range with `page_query.py`.

## Checkpoint Discipline

When you finish processing any work item (chapter, section, batch):

1. **Write all entries to disk first** — entity, topic, idea, citation, timeline files
2. **Write checkpoint notes** via `state.py update-item --notes "..."` — a compact tally of what you extracted (e.g. `+5E +3T +2I +8C: dijkstra, parnas, brooks; waterfall, incremental; lehman-laws; 1968-1975 timeline`)
3. **Then** mark the item done

The notes field is your breadcrumb trail. When context compacts, `state.py pending` returns the last 5 completed items with their notes — enough to reconstruct what was done and what comes next.

## Resumption Protocol

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
6. **Reading method reminder**: For text-layer PDFs, use `read.py --output /tmp/file.json`
   then read the JSON. For scanned PDFs, render and view one page at a time (never
   accumulate multiple page images in context — process each fully before loading
   the next). Even if rendered page images exist on disk from a prior session,
   do not bulk-load them — the 413 overflow that crashed the prior session will
   recur. One image at a time, always.
7. Continue from the next pending item — do NOT re-process done items
```

If steps 1-3 would produce large payloads, write them to artifacts first (`--output`) and reopen only `pending_tasks`, `file_counts`, `next_items`, or specific task slices with `json_query.py`. Carry forward only the artifact path, selector, a short summary, and the next action.

This protocol works whether you lost context 5 minutes ago or 5 days ago. The disk state is the single source of truth.

## Hierarchical Processing for Large Sources

Any source too large for one pass requires hierarchical processing. This applies to books, collections, large reports — anything with internal structure.

**Processing levels** (bottom-up):

| Level | Unit | What you do | Artifact |
|-------|------|------------|----------|
| **Chunk** | Chapter, section, essay | Exhaustive extraction: entities, topics, ideas, citations, dates | Entries + **chapter analysis brief** (`<id>-ch01-analysis.md`) + checkpoint tally in `update-item --notes` |
| **Group** | Part, section cluster | Cross-chunk themes, argument arc, tensions | **Part analysis document** (`<id>-part1-analysis.md`) — reads chapter briefs |
| **Source** | Whole book/collection | Source-level synthesis, overarching themes, bibliography analysis | **Source analysis** (`<id>-analysis.md`) — reads part analyses |
| **Cross-source** | Related KB content | Meta-analyses, contradiction detection | `knowledge/meta/` and `knowledge/controversies/` entries — reads source analyses |

Each level reads ONLY the level directly below — never raw chapters during synthesis. The chapter briefs, part analyses, and source analysis form a compression pipeline: 26 chapters → 5 part docs → 1 source analysis → cross-book meta.

## Preventing Trajectory Drift

Context compaction can cause the LLM to "forget" the extraction strategy and drift into summarization. Defenses:

1. **Task items are your todo list.** Process them in order. Don't improvise.
2. **Checkpoint notes anchor your approach.** When resuming, read the notes from recent items — they show the extraction pattern you were following (e.g. "+8E +3T +12C" tells you to maintain that density, not drop to "+1T").
3. **The quality gate is mandatory.** Every chunk MUST pass the quality gate checklist before marking done. This prevents drift toward skimming.
4. **Checkpoint notes are your narrative.** After each chunk, write a `--notes` that captures both the extraction tally AND the key themes. This is your running narrative — it survives compaction and anchors your trajectory. Do NOT write incremental progress into knowledge files.
5. **NEVER bulk-read after compaction.** When resuming after context compaction, process ONE chapter/section at a time — exactly as you did before compaction. The temptation to "catch up" by reading multiple remaining chapters at once produces shallow, summary-level extraction. Each chapter deserves the same exhaustive treatment regardless of how many remain. If 15 chapters are left, process them one by one across 15 cycles. There are no shortcuts.
6. **Density drop = drift alarm.** After writing checkpoint notes, compare your extraction tally against TWO baselines: (a) the density expectations table in add-workflow.md (5-15 entities, 5-20 citations per chapter), and (b) the first 3 chapters you processed in this task. Do NOT compare only against the previous 2-3 chapters — if those were already degraded by drift, you'll anchor to a bad baseline. If your counts are below 50% of EITHER baseline (e.g. early chapters averaged `+5E +3I +8C` but you just wrote `+1T`), you ARE drifting. STOP. Re-read the quality gate. Re-read the chapter. Extract what you missed. Do NOT mark the chapter done until density recovers.
7. **Minimum viable extraction per chapter.** Every book chapter checkpoint MUST include at least 3 distinct extraction categories from {E, T, I, C, TL}. A checkpoint with only `+1T` or any single category is ALWAYS incomplete — no exceptions. Most non-trivial textbook chapters contain named people (→ E), in-text references (→ C), and at least one date or topic alongside ideas. If your checkpoint shows `+0E` or `+0C` for a textbook chapter, re-read the chapter — you skimmed it. The per-chapter quality gate in add-workflow.md has specific minimums.

## Context Management

- **Start every session** with `open.py` to load the KB context
- **Prefer artifact mode** for broad JSON outputs, then reopen narrow slices with `json_query.py`
- **Read `index.md` first** when searching for information — it's your table of contents
- **Follow wikilinks** rather than reading all files — targeted navigation over full scans
- **Use `search.py`** for keyword lookup when index isn't enough
- **Use `page_query.py`** for KB entries, chapter briefs, source analyses, and other markdown/text files when you only need one heading, chunk, or line range
- **Don't re-read processed chunks** — read your own extracted entries instead
- **Write entries incrementally** — don't try to hold an entire book in context
- **If context feels full**, finish the current item, write checkpoint notes, mark done, then continue — the resumption protocol handles the rest
