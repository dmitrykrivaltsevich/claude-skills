# Gap analysis — method and routing

What the document does not say, and why that matters. Read this file first, then load **exactly one** genre file from `gaps/`.

## Contents

1. [Routing](#routing)
2. [The procedure](#the-procedure)
3. [Gap kinds](#gap-kinds)
4. [The materiality test](#the-materiality-test)
5. [Evidence rules](#evidence-rules)
6. [Generic checklist](#generic-checklist)
7. [Rendering the GAPS section](#rendering-the-gaps-section)
8. [Anti-patterns](#anti-patterns)

## Routing

Identify the genre, load one file, and stop. Loading several wastes context and produces a checklist that fits nothing.

| Genre | File |
|---|---|
| Research paper, survey, benchmark study | `gaps/research-paper.md` |
| Textbook or technical book, whole or by chapter | `gaps/technical-book.md` |
| Industry system or engineering experience paper | `gaps/system-paper.md` |
| Incident report or post-mortem | `gaps/postmortem.md` |
| Technical design document, RFC, architecture decision record | `gaps/design-doc.md` |
| Standard, specification, body of knowledge | `gaps/standard-spec.md` |
| Magazine or journal issue, newsletter | `gaps/periodical.md` |
| Popular science, history, trade non-fiction | `gaps/popular-science.md` |
| Policy, regulation, ethics code, position statement | `gaps/policy-position.md` |
| Product, API or tool documentation | `gaps/tool-doc.md` |
| News article, blog post, press release | `gaps/news-article.md` |
| Nothing above fits | None — use the [generic checklist](#generic-checklist) below |

Ambiguous cases: a vendor engineering blog announcing a system is `system-paper`, not `news-article`. A chapter of a textbook is `technical-book`, even when read alone. A preprint is `research-paper`. An RFC that defines a wire protocol is `standard-spec`; an RFC proposing an internal change is `design-doc`.

## The procedure

1. **Inventory what the document claims.** For a page built from a source, work from the source, not from how much of the page the reader happened to open. For a topic page you authored, work from the committed outline.
2. **Load one genre file** and take its expected-coverage checklist.
3. **Diff.** Expected minus actual gives candidate gaps.
4. **Verify** each candidate before reporting it. See [evidence rules](#evidence-rules).
5. **Filter** by the [materiality test](#the-materiality-test).
6. **Record** with `state.py gaps-add`, then append a `GAPS` node to the outline and its body to the page.

Five to eight gaps is a full answer. Twenty is a checklist dump and will not be read.

## Gap kinds

| Kind | The document… |
|---|---|
| `omission` | never raises something a competent reader needs |
| `understated` | mentions it, but at a weight that misleads |
| `stale` | was true when written and is not true now |
| `unstated-assumption` | depends on a condition it never declares |
| `conflict-of-interest` | omits something its author had an incentive to omit |
| `contradicted` | states something that better evidence contradicts |

`contradicted` is the only kind that overlaps with fact-checking. Use it when the document is wrong, not merely incomplete.

## The materiality test

For every candidate, ask: **would a competent reader, acting on this document alone, make a materially worse decision?**

If yes, it is a gap. If no, discard it — including when it is true and interesting.

Two rules follow:

- **Out of scope is not a gap.** A page about `grep` need not cover `awk`. A paper on an optimiser need not cover deployment. Judge against what the document set out to do.
- **A gap must name the decision it damages.** If you cannot write the `Effect:` line concretely, you do not have a gap.

For a page you authored yourself from a topic, there is no author to have omitted anything. Reframe: what the page under-weights, which claims are genuinely contested, and where your own knowledge may be stale.

## Evidence rules

Research first. Model knowledge is a marked fallback, never a silent one.

1. Search for confirmation with the `duckduckgo` skill. Use `deep-research` when the question needs several sources reconciled.
2. A confirmed gap carries a source and a retrieval date: `https://example.org/pricing (retrieved 2026-09-05)`.
3. A candidate you cannot confirm is still reportable, stamped exactly:
   `[unverified - model knowledge, confirm before acting]`
4. Never state a number, a date, a price or a limit from memory as though it were sourced. If the number is the point and you cannot source it, say what kind of number to look for instead of inventing one.
5. If the search contradicts your candidate, drop it. A wrong gap is worse than a missing one, because the reader has no way to check it.

`state.py gaps-add` sets `verified` from the presence of evidence. Render an unverified gap with the stamp; never hide it.

## Generic checklist

When no genre file fits, probe these:

- What must be true for this to work, that is never stated?
- What does it cost — in money, time, attention, or maintenance?
- How does it fail, and what does failure look like from outside?
- At what scale or in what conditions does it stop holding?
- What is the boring alternative, and why is it not used here?
- Who benefits from the reader believing this?
- What is the denominator behind every proportion given?
- What changed after this was written?

## Rendering the GAPS section

Append `GAPS` as the last node of the top outline level, so it is reachable with `$` and `!` and navigable like any other section. One entry per gap, most material first:

```
GAP 2 - Egress cost is not mentioned

Kind:         omission
Materiality:  high
Missing:      Cross-zone traffic is billed per gigabyte in each direction.
Effect:       A reader plans a multi-zone design and underestimates its cost.
Evidence:     https://example.invalid/pricing (retrieved 2026-09-05)
```

The `Missing:` line states the fact, not the absence. Write `Cross-zone traffic is billed per gigabyte`, not `The document does not discuss billing`. The heading already says it is missing; the body must deliver the thing itself, in the language contract of `language.md`.

## Anti-patterns

- **Do not report the document's own stated limitations as gaps.** If the author wrote "we did not test above 10 nodes", that is disclosure, not omission.
- **Do not pad to a round number.** Five real gaps beat eight with three inventions.
- **Do not use gaps to argue.** You are reporting what a reader needs, not disagreeing with the author.
- **Do not report a genre file's checklist item that the document actually covers.** Check the source before claiming absence.
- **Do not treat brevity as omission.** A short document that says what it set out to say has no gaps.
