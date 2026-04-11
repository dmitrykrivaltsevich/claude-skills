# kb:explore Workflow Reference

Post-add free exploration of the knowledge base. Triggered after a `kb:add` operation or on user request. The LLM wanders through the KB under the impression of what was recently added, looking for surprising connections, synthesis opportunities, and emergent questions.

## Contents

1. [When to Trigger](#when-to-trigger)
2. [Exploration Process](#exploration-process)
3. [Hallucination Guardrails](#hallucination-guardrails)
4. [Output Types](#output-types)
5. [Duration Control](#duration-control)

## When to Trigger

- **Automatically after kb:add** — when a source has been fully ingested (Phase 6 complete), offer: "I've finished adding [source]. Want me to explore the KB for new connections?" If the user agrees, run explore.
- **On user request** — user says "explore", "find connections", "what's interesting", "synthesize", "what patterns do you see".
- **Periodically** — after every 3-5 sources added, suggest an explore pass even if the user doesn't ask.

## Exploration Process

### Phase 1 — Prime Context (mechanical)

1. Run `open.py` to load KB state
2. Read `log.md` (last 20 entries) to understand recent additions
3. Read the source analysis for the most recently added source(s)
4. Run `related.py --keywords <key-terms-from-recent-source>` to find overlap points

### Phase 2 — Wander (stochastic, YOUR judgment)

**This is deliberately unstructured.** Follow your curiosity through the knowledge graph:

1. Start from the entries most recently created/updated
2. Follow wikilinks to connected entries — read them, think about what they say together
3. When something surprises you, follow that thread:
   - An entity appears in two unrelated topics → what connects them?
   - A timeline gap between two events → what happened in between?
   - Two ideas use the same mechanism in different domains → is this a deeper pattern?
   - A controversy has new evidence from the recent source → has it shifted?
4. Let yourself get at least 3-4 hops away from the recent source — the most valuable connections are NOT the obvious topical ones
5. Read at least 15-20 entries during the wander — enough to cover real breadth

### Phase 3 — Capture (grounded, sourced)

For each insight, create or update entries. Every output MUST follow the hallucination guardrails below.

**Types of output** (in order of value):

1. **New connections** — add reciprocal wikilinks between entries that should be linked but aren't. This is the most common and most valuable output.
2. **Synthesis entries** — `knowledge/meta/` entries that identify patterns across sources. E.g. "Three sources all describe failure cascades in complex systems, but use different terminology."
3. **Questions** — `knowledge/questions/` entries for gaps or tensions you discover. E.g. "Source A says X peaked in 1995, source B says 1998 — who's right?"
4. **Enriched entries** — adding depth to existing entries based on connections you noticed. E.g. adding a `## Connections` entry to a person who turns out to be cited by three different sources but had no connections section.
5. **Controversy entries** — when you notice contradictions between entries from different sources that weren't flagged during individual source processing.

### Phase 4 — Log

Append one line to `log.md`: `YYYY-MM-DD explore | +N connections, +N meta, +N questions, ~N entries enriched`

## Hallucination Guardrails

**The fundamental risk**: During free exploration, the LLM may generate "insights" that aren't grounded in the actual KB content — pattern-matching from training data rather than from the entries it just read.

**Rules — these are non-negotiable:**

1. **Every claim traces to an entry.** When you write "Source A and Source B both describe X", you MUST have actually read two specific entries that describe X. Cite them: `[[entry-a]] and [[entry-b]]`.

2. **No fabricated connections.** If you "feel" two entries are related but can't point to specific text in both entries that supports the connection, do NOT create the link. The feeling may come from your training data, not from the KB. Write a question entry instead: "Are [[entry-a]] and [[entry-b]] related via X?"

3. **Separate observation from inference.** In meta entries, use explicit markers:
   - **Observed**: "[[vaswani-2017-analysis]] and [[bahdanau-2015-analysis]] both describe attention as a weighted average" (directly stated in the entries)
   - **Inferred**: "This suggests a lineage from Bahdanau to Vaswani" (your interpretation — mark it as such)

4. **Questions are safer than claims.** When you notice something interesting but aren't sure it's grounded, create a question entry rather than a meta entry. Questions with `raised-by: exploration` are explicitly tagged as LLM-generated and can be verified later.

5. **No entries from memory.** NEVER create entries about topics, people, or ideas that aren't already in the KB, based on what you "know" from training. If you think a relevant concept is missing, create a question: "The KB discusses X but doesn't have an entry for Y, which seems relevant because [reason grounded in existing entries]."

6. **The user is the final arbiter.** If during exploration you're uncertain about a connection or insight, present it to the user for approval rather than writing it directly. Prefix uncertain findings with "I noticed something that might be interesting — want me to add it?"

## Output Types

| What you create | Where | When to use |
|---|---|---|
| Reciprocal wikilinks | Existing entries | Always — the most common explore output |
| Meta entry | `knowledge/meta/` | Cross-source patterns you can cite from 2+ entries |
| Question entry | `knowledge/questions/` | Gaps, tensions, or "seems related but I can't prove it" |
| Enriched entry | Existing entries | Adding depth from connections you noticed |
| Controversy entry | `knowledge/controversies/` | Contradictions between sources found during exploration |

## Duration Control

**Default explore**: ~15-20 entries read, 5-10 minutes of work. Produces 3-10 new connections, 0-2 meta entries, 0-3 questions.

**Deep explore** (user requests "explore deeply" or "take your time"): 30-50 entries read, potentially multiple wander cycles through different regions of the KB. Useful when the KB has 100+ entries and a new source touches many areas.

**Focused explore** (user says "explore connections to X"): Start from entries related to X, but still follow surprising links away from X. The focus is a starting point, not a cage.
