# Know-How Extraction

How to extract practical knowledge without hallucinating it. This workflow is referenced from add, cleanup, and analysis documents because practical know-how must be captured during the first pass and re-checked during maintenance.

## What counts as know-how

Capture these as `knowledge/ideas/` entries with `idea-kind: practical` when the source genuinely supports them:

- Decision rules: "When X, do Y"
- Heuristics and rules of thumb
- Implementation patterns and deployment checklists
- Debugging tactics and diagnostic signals
- Trade-off rules and constraint tables
- Common pitfalls, anti-patterns, and failure modes
- Negative lessons: what did NOT work, and why

If the source only offers descriptive theory, historical narrative, or abstract claims with no honest operational takeaway, do NOT invent one.

## Primary-pass workflow

Run this during the first extraction pass, not as a cleanup-only afterthought:

1. While reading, mark passages that answer one of these questions:
   - What would an experienced practitioner actually do here?
   - What should they avoid?
   - What warning signs indicate the approach is failing?
   - What trade-off is being paid for the recommendation?
2. Promote reusable guidance into an idea entry with `idea-kind: practical`.
3. Fill these sections in the entry:
   - `## Rule of thumb`
   - `## Use when`
   - `## Avoid when`
   - `## Trade-offs`
   - `## Failure modes`
   - `## Implementation notes`
4. Link the practical entry from the current analysis doc under `## Know-How`.

## Honest none-case

Not every source has practical output. Historical, purely formal, or narrowly descriptive material may have none.

When that happens, write the explicit note below in the relevant analysis document and move on:

`No practical insight justified from this chunk/source.`

The guardrail phrase to preserve is: `no practical insight justified`.

This is the hallucination guardrail. The system should force honesty, not volume.

## Recall surfaces

Analysis documents are the retrieval bridge between raw reading and the long-term KB. When the source yields non-obvious operator-grade value, include:

- `## Hidden Gems` — the 1-3 buried takeaways worth remembering
- `## Know-How` — wikilinks to `idea-kind: practical` entries, or the explicit none-case note
- `## Pitfalls / Failure Modes` — what breaks, how it breaks, and what signals show the breakage early

Use these sections in chapter briefs, article analysis briefs, part analyses, source analyses, and other analysis-style documents.

## Cleanup, lint, and revisit

Run this workflow again during maintenance when you see one of these smells:

- A source analysis has only summary prose and no reusable takeaways
- An idea entry reads like a summary but actually encodes a decision rule
- A chapter or article describes mistakes, outages, or constraints with no practical entry created
- A revisit adds a later source that turns an old conceptual note into actionable guidance

The maintenance pass should not invent new know-how. It should promote already-supported guidance that the first pass missed.