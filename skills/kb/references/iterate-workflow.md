# Iterate Workflow — Cyclic Latent Semantic Iterations

## Table of Contents

1. [Rationale](#rationale)
2. [When to Trigger](#when-to-trigger)
3. [Iteration Protocol](#iteration-protocol)
4. [Convergence Criteria](#convergence-criteria)
5. [Crystallization Rules](#crystallization-rules)
6. [Hallucination Guardrails](#hallucination-guardrails)
7. [Output](#output)

## Rationale

The KB is a graph. A single pass through a subgraph (reading A, B, C) produces a linear understanding. But knowledge is non-linear — insights emerge from **cycles**: reading A changes how you understand B, which reveals something new about A. Each pass through the same entries with enriched context activates different attention patterns in the LLM, producing deeper synthesis that a single pass cannot reach.

This is **message passing over a knowledge graph** using the LLM's context window as the propagation medium. Each iteration = one message-passing step. The LLM's stochastic attention is the mechanism — re-reading with different latent state literally produces different outputs.

The key constraint: context is finite. You cannot accumulate raw text indefinitely. Each iteration must **crystallize** findings into a compact working document that replaces the raw readings, then expand outward along wikilinks.

## When to Trigger

- User asks a deep/analytical question that requires synthesis across multiple entries
- User says "iterate", "dig deeper", "think harder about this"
- During `kb:query` when the first-pass answer feels shallow
- During `kb:explore` when a pattern emerges that deserves focused investigation
- User asks "why" or "how" about a connection between entries

## Iteration Protocol

### Phase 0 — Seed

1. Formulate the **driving question** or **hypothesis** explicitly. Write it down. This anchors every iteration.
2. Identify **seed entries** (3-5) that are directly relevant. Use `search.py` and `related.py`.
3. Read the seed entries. Write initial observations into a **working document** (not a KB entry yet — this is volatile scratchpad).

### Phase 1–N — Iterate

Each iteration follows the same 4-step cycle:

```
READ → CRYSTALLIZE → EXPAND → CHECK
```

**READ**: Pick 3-5 entries to read this iteration. In iteration 1, these are the seeds. In later iterations, follow wikilinks discovered in the previous iteration — prioritize links that your crystallization flagged as "needs deeper look."

**CRYSTALLIZE**: After reading, update the working document:
- What new connections did this pass reveal?
- What changed from the previous iteration's understanding?
- What contradictions or tensions surfaced?
- What wikilinks should be followed next? (expansion frontier)

The working document replaces your memory of the raw text. It is the compressed state between iterations. Format:

```markdown
## Iteration N
**Driving question**: [restated — may evolve]
**Entries read this pass**: [[entry-1]], [[entry-2]], ...
**New connections**: ...
**Changed understanding**: ...
**Tensions/contradictions**: ...
**Expansion frontier**: [[next-entry-1]] (because ...), [[next-entry-2]] (because ...)
**Convergence signal**: [new insights count vs previous iteration]
```

**EXPAND**: Follow the expansion frontier. Use `related.py` to discover entries you didn't know about. Prioritize:
1. Entries that multiple previous iterations converged on
2. Cross-category entries (entity → topic, idea → controversy)
3. Entries with high wikilink degree (likely knowledge hubs)

**CHECK**: Compare this iteration's findings against the previous one. How many genuinely new insights emerged? If the count is declining, you're approaching convergence.

### Iteration Limits

- **Minimum**: 2 iterations (a single pass is not iterating)
- **Typical**: 3-5 iterations for most questions
- **Maximum**: 7 iterations (diminishing returns beyond this; the LLM's context becomes saturated)
- **Entries per iteration**: 3-5 (more causes shallow reading)

## Convergence Criteria

Stop iterating when ANY of these hold:

1. **Diminishing returns**: This iteration produced ≤1 new connection that wasn't implicit in the previous iteration
2. **Stable frontier**: The expansion frontier stopped growing — you're circling the same subgraph
3. **Question answered**: The driving question has a well-supported answer with evidence from ≥3 entries
4. **Contradiction found**: You've identified an irreconcilable tension that needs new source material (iteration alone won't resolve it)
5. **Max iterations**: 7 iterations reached

When stopping, explicitly state the convergence reason. If stopping due to (4), create a `knowledge/questions/` entry for the unresolved tension.

## Crystallization Rules

The working document is the critical piece. Without it, context compaction destroys iteration state.

1. **Write after every iteration**, not at the end. If you crash, you lose only the current iteration.
2. **Replace, don't accumulate.** Each iteration's section replaces the previous understanding with a richer one. The working doc should NOT grow linearly with iterations — it should stabilize in size as understanding converges.
3. **The working document is not a KB entry.** It's a volatile artifact. After convergence, the *final synthesis* becomes a KB entry (meta, controversy, or answer to a question).
4. **Concrete over abstract.** "A connects to B through mechanism X (see [[entry-1]] paragraph 3)" beats "there are connections between these concepts."
5. **Track what changed.** The "Changed understanding" field is the most valuable part — it shows where your attention pattern shifted between iterations.

## Hallucination Guardrails

Iterative reading amplifies both insight AND confabulation. The LLM may "discover" patterns that aren't in the entries but feel coherent after multiple passes.

1. **Every claim traces to an entry.** If you can't point to the specific `[[entry]]` and paragraph, the claim is suspect.
2. **Distinguish observation from inference.** "Entry A says X and entry B says Y" (observation) vs "Therefore X causes Y" (inference). Mark inferences explicitly.
3. **The KB is the ground truth.** If an insight contradicts what entries say, recheck the entries — don't trust the insight. Re-read the actual entry text, not your working document summary of it.
4. **New-source test.** If an inference can only be validated by reading a source NOT in the KB, it's a hypothesis, not a finding. Record it as a question, not a fact.
5. **Never fabricate entry content.** When crystallizing, quote or paraphrase what entries actually say. Don't invent intermediate reasoning steps and attribute them to entries.

## Output

After convergence, produce:

1. **Final synthesis** → becomes `knowledge/meta/` or answers a `knowledge/questions/` entry
2. **Discovered connections** → new wikilinks added to existing entries (reciprocal)
3. **Open questions** → new `knowledge/questions/` entries for unresolved tensions
4. **Log entry**: `YYYY-MM-DD iterate "<question>" | N iterations, M entries read, +X connections`

If the iteration was triggered by `kb:query`, the synthesis IS the answer — present it directly to the user with citations.
