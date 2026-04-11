# kb:revisit Workflow Reference

Periodic re-visitation of older entries through the lens of newer knowledge. The LLM re-reads entries created when fewer sources were in the KB, and updates them with insights that are only visible after accumulating more context.

## Contents

1. [Rationale](#rationale)
2. [When to Trigger](#when-to-trigger)
3. [Selection Strategy](#selection-strategy)
4. [Revisit Process](#revisit-process)
5. [Hallucination Guardrails](#hallucination-guardrails)
6. [Logging](#logging)

## Rationale

When source #1 is added, entities and ideas are extracted with zero cross-reference context. By the time source #20 is added, the KB has a rich network — but entries from source #1 are still at their original depth. A human expert re-reads foundational papers after gaining experience and notices things they missed the first time. This workflow gives the LLM the same capability.

**What revisit catches that add/explore don't:**
- Entity entries that are shallow stubs because they were created when only one source mentioned the person — but now 5 sources reference them
- Topic entries that describe a concept from one perspective — but the KB now has 3+ contrasting perspectives
- Idea entries without practical implications — because the practical source was added later
- Missing connections that weren't possible when the entry was created (the target entry didn't exist yet)
- Questions that can now be answered from newer sources

## When to Trigger

- **After every 5 sources added** — suggest: "The KB has grown significantly since some entries were created. Want me to revisit older entries?"
- **On user request** — user says "revisit", "refresh old entries", "update stale entries", "what did we miss in early entries"
- **When lint finds many orphans** — orphan entries are often from early sources that weren't linked because later entries didn't exist yet
- **When a key entity accumulates 3+ source-ids** — the entry is now important enough to warrant a deep profile rebuild

## Selection Strategy

Don't revisit randomly. Target entries where revisiting will produce the most value:

### Priority 1 — Multi-source entities with thin profiles
Run `search.py` or scan `knowledge/entities/` for entries whose `source-ids` frontmatter lists 3+ sources but whose content is short (< 30 lines). These are the prime candidates — the KB has plenty of information about this person, but the entry doesn't reflect it.

### Priority 2 — Early entries with few outgoing links
Entries from the first 3-5 sources often have sparse wikilinks because the target entries didn't exist yet. Re-read them and add links to entries that now exist.

### Priority 3 — Questions that might now be answerable
Scan `knowledge/questions/` for `status: open` entries. For each, check if recent sources have added relevant information. If so, update the question (add `## Partial answer` or change status to `answered`).

### Priority 4 — Topics with only one source perspective
Topics whose `source-ids` lists only one source but which now appear in citations from multiple sources. These topics have become cross-cutting themes but their entries still reflect a single-source viewpoint.

### Priority 5 — Random sample
After exhausting the above, pick 5 entries at random. Read them fresh. See if they trigger any insights now that wouldn't have been possible when they were written.

## Revisit Process

### Per Entry (5-10 entries per revisit session)

1. **Read the entry** — understand what it currently says
2. **Read the source analyses** listed in its `source-ids` frontmatter
3. **Search for mentions** — `search.py --query "<entry-name>"` to find ALL places in the KB that reference this concept (including entries created after this one)
4. **Compare and update**:
   - Are there facts from newer sources that should be added? → Add with source attribution
   - Are there connections to entries that didn't exist when this was written? → Add wikilinks (reciprocal!)
   - Does the entry contradict anything in a newer source? → Create/update controversy entry
   - Is the entry now answerable (if it's a question)? → Update status, add resolution
   - Does the entry feel shallow compared to the KB's current depth? → Enrich it
5. **Entity triangulation** — for person entries, do the full triangulation process (see entry-types.md): compare what different sources say, note agreements, note new facets, add source concordance section
6. **Mark what you changed** — update `updated:` date in frontmatter, add new source-ids if applicable

### After All Entries

1. Run `lint.py` — the edits may have introduced orphans or broken links
2. Fix any issues found
3. Log the revisit

## Hallucination Guardrails

The same guardrails from [explore-workflow.md](explore-workflow.md) apply, plus:

1. **Do NOT "improve" entries from world knowledge.** If you re-read an entity entry about a person and you "know" something about them from training data that's not in any KB source, do NOT add it. Every fact must trace to a `[[source-analysis]]`. The temptation is strong — resist it.

2. **Preserve original attributions.** When enriching an entry, keep the original `source-ids` and add new ones. Never remove a source attribution.

3. **Track what changed.** For significant updates (not just adding a wikilink), add a note at the bottom of the entry:
   ```
   > **Revisited YYYY-MM-DD**: Enriched from [[new-source-analysis]], added connections to [[entry-x]], [[entry-y]]. Previous version had only [[original-source-analysis]] perspective.
   ```

4. **When in doubt, ask.** If revisiting reveals that an early entry made a claim that newer sources contradict, don't silently "correct" it. Create a controversy entry and let the user decide.

## Logging

Append one line to `log.md`: `YYYY-MM-DD revisit | N entries updated, +N links, +N questions answered, ~N entries enriched`

If a revisit session is substantial (>= 5 entries significantly updated), also note it in the index.
