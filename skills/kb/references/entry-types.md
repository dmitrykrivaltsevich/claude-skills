# Entry Types Reference

Schema, required frontmatter, and examples for each knowledge entry type. Linked from SKILL.md.

## Contents

1. [Entity](#entity)
2. [Topic](#topic)
3. [Idea](#idea)
4. [Location](#location)
5. [Timeline (Year / Month / Day)](#timeline)
6. [Source Analysis](#source-analysis)
7. [Citation](#citation)
8. [Controversy](#controversy)
9. [Meta](#meta)
10. [Question](#question)
11. [Custom Entry Types](#custom-entry-types)

---

## Entity

**Path**: `knowledge/entities/<kebab-name>.md`
**What**: A person, organization, institution, or named thing.

```yaml
---
type: entity
created: 2025-01-15
updated: 2025-01-15
source-ids: [isaacson-2007, pais-1982]
tags: [physicist, nobel-laureate]
entity-kind: person | organization | institution | other
---
```

```markdown
# Albert Einstein

German-born theoretical physicist. Developed the theory of relativity.

## Key contributions
- [[special-relativity]] (1905)
- [[general-relativity]] (1915)
- [[photoelectric-effect]] — led to [[quantum-mechanics]]

## Affiliations
- [[eth-zurich]] (1912–1914)
- [[prussian-academy-of-sciences]] (1914–1933)

## Connections
- [[marcel-grossmann]] — university friend at [[eth-zurich]], introduced Einstein to Riemannian geometry essential for [[general-relativity]] ([[1912]])
- [[michele-besso]] — lifelong friend and sounding board, acknowledged in the [[special-relativity]] paper ([[1905]])
- [[mileva-maric]] — first wife, studied physics together at [[eth-zurich]] (1896–1901)
- [[niels-bohr]] — decades-long debate on [[quantum-mechanics]] interpretation (1920s–1950s)

## Influenced by
- [[hendrik-lorentz]] — Lorentz transformations, direct correspondence from [[1901]]
- [[ernst-mach]] — critique of Newtonian absolute space, read during [[bern]] patent office years ([[1902]]–[[1905]])
- [[james-clerk-maxwell]] — electromagnetic theory, foundation for relativity

## Influenced
- [[niels-bohr]] — photoelectric effect paper catalyzed quantum atomic model
- [[john-wheeler]] — geometrodynamics program built on general relativity

## Locations
- [[bern]] — patent office ([[1902]]–[[1909]]), where [[special-relativity]] was conceived
- [[berlin]] — Kaiser Wilhelm Institute ([[1914]]–[[1933]])
- [[princeton]] — Institute for Advanced Study ([[1933]]–[[1955]])

## Sources
- [[isaacson-2007-analysis]] — biography chapter 3
- [[pais-1982-analysis]] — referenced in physics history
```

**Rules**:
- One file per entity. Accumulates facts from multiple sources.
- `entity-kind` is required.
- Link to ideas they originated, organizations they belong to, timeline entries for key dates.
- **Connections** — record who this person knew, collaborated with, debated, or corresponded with. Include: the nature of the relationship, when it occurred (wikilinked date), and what it produced. Only record what the source explicitly states — never infer relationships.
- **Influenced by / Influenced** — record intellectual influence chains: who shaped this person's thinking (and how), and who this person influenced (and how). Include the mechanism when stated (read their work, personal mentorship, correspondence, attended lectures). These sections build the influence graph over time.
- **Locations** — record where this person was at key moments, especially when the source ties location to intellectual output (e.g. "conceived idea X while at Y").
- **Triangulation** — when adding information from a NEW source about a person who already has an entity entry, do NOT blindly append. Instead: (1) read the existing entry, (2) compare what the new source says against what's already there, (3) note agreements (shared facts reinforce confidence), (4) note disagreements or new facets (create controversy entries if contradictions are found), (5) add source attribution to every new fact. Over time, each entity builds a multi-source profile — like triangulating a position from multiple observations. The more sources that independently confirm a fact, the more reliable it is. Mark each section with its source: `(per [[source-analysis]])`. When sources disagree on a detail (dates, attribution, relationships), note both versions inline with their sources rather than picking one.
- **Comprehensive profiles** — entity entries should grow into deep profiles, not remain stub-level summaries. After 3+ sources mention a person, the entry should include: biographical arc, intellectual contributions with specific attributions, relationship network, key locations and periods, influence chains (who influenced them, who they influenced), and a `## Source concordance` section showing which sources contributed what. A person mentioned across 10 sources should have a richly detailed entry, not 10 one-line additions.

---

## Topic

**Path**: `knowledge/topics/<kebab-name>.md`
**What**: A subject area, field, discipline, or theme. NOT attributable to a single person.

```yaml
---
type: topic
created: 2025-01-15
updated: 2025-01-15
source-ids: [isaacson-2007]
tags: [physics, fundamental]
---
```

```markdown
# Quantum Mechanics

Branch of physics describing nature at the atomic and subatomic level.

## Key concepts
- [[wave-particle-duality]]
- [[uncertainty-principle]]
- [[quantum-entanglement]]

## Key figures
- [[max-planck]] — originated quantum theory
- [[albert-einstein]] — photoelectric effect
- [[niels-bohr]] — atomic model

## Related topics
- [[classical-mechanics]] — predecessor
- [[quantum-computing]] — application

## Controversies
- [[copenhagen-vs-many-worlds]] — interpretation debate
```

**Rules**:
- Topics are NOT attributable. "Machine learning" is a topic. "Attention mechanism" is an idea (attributable to Bahdanau et al.).
- Link to entities (key figures), ideas (key contributions), and sub/super topics.
- **No bare parenthetical references.** When prose contains a claim from a source that references another work — e.g. "less suitable for dependable processes (Boehm 2002)" — replace the parenthetical with a wikilink to the citation entry: `less suitable for dependable processes ([[sommerville-2011-cites-boehm-2002|Boehm, 2002]])`. Create the citation entry if it doesn't exist yet. This applies to ALL entry types with prose content (topics, ideas, entities, controversies).

---

## Idea

**Path**: `knowledge/ideas/<kebab-name>.md`
**What**: A specific intellectual contribution — attributable to person(s) or paper(s).

```yaml
---
type: idea
created: 2025-01-15
updated: 2025-01-15
source-ids: [vaswani-2017]
tags: [deep-learning, architecture]
attributed-to: [vaswani-et-al]
year: 2017
---
```

```markdown
# Attention Is All You Need

Self-attention mechanism replacing recurrence and convolution for sequence transduction.

## Core claim
Sequence-to-sequence models can achieve state-of-the-art results using only attention mechanisms, without recurrence or convolution.

![[knowledge/assets/vaswani-2017/transformer-architecture.png]]
*Figure 1: The Transformer model architecture (vaswani-2017, Figure 1)*

## Evidence
- BLEU score of 28.4 on WMT 2014 EN-DE (vaswani-2017, Table 2)
- Training time reduced by order of magnitude vs. recurrent models

![[knowledge/assets/vaswani-2017/bleu-score-comparison.png]]
*Table 2: BLEU score comparison on EN-DE and EN-FR translation tasks*

## Impact
- Foundation for [[transformer-architecture]]
- Led to [[bert]], [[gpt-series]], [[t5]]

## Attributed to
- [[ashish-vaswani]] et al., 2017

## Related
- [[self-attention]] — mechanism detail
- [[sequence-to-sequence]] — problem domain
```

**Rules**:
- `attributed-to` is required. Lists entity slugs.
- `year` is required when known.
- Distinguish from topics: ideas have specific authors and claims.
- Embed extracted figures/tables inline using `![[knowledge/assets/<source-id>/<name>.png]]` with an italicized caption on the next line. Place each figure next to the text it supports.

---

## Location

**Path**: `knowledge/locations/<kebab-name>.md`
**What**: A geographic place relevant to the KB.

```yaml
---
type: location
created: 2025-01-15
updated: 2025-01-15
source-ids: [isaacson-2007]
tags: [city, switzerland]
coordinates: [47.3769, 8.5417]
---
```

```markdown
# Zurich

City in Switzerland. Home to [[eth-zurich]].

## KB connections
- [[albert-einstein]] — lived and worked here 1896–1900, 1912–1914
- [[eth-zurich]] — located here
```

**Rules**:
- `coordinates` optional but recommended.
- Link to entities and timeline entries associated with this place.

---

## Timeline

**Paths**:
- `knowledge/timeline/years/<YYYY>.md`
- `knowledge/timeline/months/<YYYY-MM>.md`
- `knowledge/timeline/days/<YYYY-MM-DD>.md`

**What**: Navigable chain of dated events.

```yaml
---
type: timeline
created: 2025-01-15
updated: 2025-01-15
source-ids: [isaacson-2007]
tags: [physics]
date: "1905"
prev: "[[1904]]"
next: "[[1906]]"
parent: null
---
```

```markdown
# 1905

Einstein's _annus mirabilis_.

## Events
- [[photoelectric-effect]] — paper published ([[1905-03|March]])
- [[special-relativity]] — paper published ([[1905-06|June]])
- [[mass-energy-equivalence]] — E=mc² ([[1905-09|September]])

## See also
- [[albert-einstein]]
```

**Rules**:
- `prev` / `next` are required — they form the navigable chain.
- `parent` links up: day→month, month→year. Year has `parent: null`.
- Year entries → link to month entries. Month entries → link to day entries.
- Gap detection: `lint.py` finds missing entries between existing ones.

---

## Source Analysis

**Path**: `knowledge/sources/<source-id>-analysis.md`
**What**: Per-source summary and metadata. One per ingested source.

```yaml
---
type: source-analysis
created: 2025-01-15
updated: 2025-01-15
source-ids: [isaacson-2007]
tags: [biography, physics]
source-type: book | paper | article | transcript | reference
---
```

```markdown
# isaacson-2007 — "Einstein: His Life and Universe"

**Source**: [[isaacson-2007]]
**Author**: Walter Isaacson
**Published**: 2007
**Source type**: Book

## Summary
Comprehensive biography covering Einstein's personal life, scientific contributions, and political involvement.

## Key extractions
- [[albert-einstein]] — primary subject
- [[special-relativity]], [[general-relativity]] — detailed explanations
- [[mileva-maric]] — first wife, collaborator debate

## Bibliography analysis
- 42 items in bibliography
- 38 cited in text
- 4 unreferenced: [list them]

## Figures & Tables

![[knowledge/assets/isaacson-2007/einstein-1905-patent-office.png]]
*Photo of Einstein at the Bern patent office, 1905 (Chapter 3)*

![[knowledge/assets/isaacson-2007/relativity-thought-experiment.png]]
*Diagram of the light-beam thought experiment (Chapter 6, Figure 2)*
```

**Rules**:
- One per source. Named `<source-id>-analysis.md`.
- **MUST wikilink to the registered source**: `**Source**: [[<source-id>]]`. This is a wikilink — NOT a file path. Write `**Source**: [[lamport-1978]]`, NEVER `Source: sources/references/lamport-1978.md`. Do not mention whether the source is a reference or a file — that's an implementation detail irrelevant to the knowledge graph. The `add_source.py` script creates a navigable `.md` stub for every source, so `[[source-id]]` always resolves.
- Must include summary, key extractions (what entries were created/updated), bibliography analysis (for academic sources). MUST NOT contain progress checklists, session logs, or chapter-by-chapter extraction checkboxes — that operational state belongs in task state (`state.py --notes`), not in knowledge files.
- If visual assets were extracted, add a `## Figures & Tables` section. Each asset MUST be an Obsidian image embed — `![[knowledge/assets/<source-id>/<name>.png]]` on its own line, followed by an italicized caption on the next line. NEVER list assets as plain text or code-formatted paths.

---

## Citation

**Path**: `knowledge/citations/<source-id>-cites-<ref-slug>.md`
**What**: A specific citation relationship between a source and a referenced work.

```yaml
---
type: citation
created: 2025-01-15
source-ids: [vaswani-2017]
cited-work: "Bahdanau et al., 2015, Neural Machine Translation by Jointly Learning to Align and Translate"
cite-key: "[14]"
tags: [attention, nmt]
---
```

```markdown
# vaswani-2017 cites Bahdanau et al. 2015

**Citing source**: [[vaswani-2017-analysis]]

**Context**: "The dominant approach to attention mechanisms was introduced by Bahdanau et al. [14], who proposed learning alignment scores between encoder and decoder states."

**Claims supported**: Bahdanau introduced the dominant attention mechanism approach.

**Significance**: Establishes Bahdanau's attention as the baseline this paper builds upon.

**See also**: [[attention-mechanism]], [[neural-machine-translation]], [[dzmitry-bahdanau]]
```

**Rules**:
- `cited-work` is the full bibliographic reference.
- `cite-key` is the in-text citation marker from the source.
- Context must be the exact sentence(s) containing the citation.
- **`Citing source` wikilink is MANDATORY** — must link to `[[<source-id>-analysis]]` so the citation is navigable back to its origin. Without this link, citations are dead ends.
- **`Significance`** — one sentence explaining why this citation matters in the context of the citing paper. Not every citation needs equal weight.
- Create even for works NOT in the KB — they accumulate incoming citations.
- When the cited work already exists as a KB entry (entity, source-analysis, or stub), add a wikilink to it in See also. This enables "find all papers citing X" via backlink navigation.

---

## Controversy

**Path**: `knowledge/controversies/<kebab-name>.md`
**What**: A contradiction, debate, or disagreement found across sources.

```yaml
---
type: controversy
created: 2025-01-15
updated: 2025-01-15
source-ids: [isaacson-2007, trbuhovic-2005]
tags: [attribution, physics]
status: open | resolved
---
```

```markdown
# Did Mileva Marić Contribute to Relativity?

## Position A — Yes
Source: [[trbuhovic-2005-analysis]] — "Letters suggest collaborative work on the mathematics"
Entities: [[mileva-maric]]

## Position B — No
Source: [[isaacson-2007-analysis]] — "No documentary evidence of intellectual contribution"
Entities: [[albert-einstein]]

## Evidence
- Letters from 1901 reference "our work" (Position A)
- No co-authorship on any published paper (Position B)
- Einstein's Nobel prize money went to Marić in divorce (ambiguous)

## Status
Open — insufficient evidence for resolution.
```

**Rules**:
- `status` required: `open` or `resolved`.
- All involved entries MUST wikilink back to the controversy: `See also: [[did-mileva-contribute]]`
- Present positions neutrally with sources for each.

---

## Meta

**Path**: `knowledge/meta/<kebab-name>.md`
**What**: Cross-source analyses, comparisons, syntheses that don't fit other types.

```yaml
---
type: meta
created: 2025-01-15
updated: 2025-01-15
source-ids: [isaacson-2007, vaswani-2017, bahdanau-2015]
tags: [comparison, attention]
meta-kind: comparison | synthesis | timeline-overview | gap-analysis
---
```

```markdown
# Attention Mechanisms — Evolution (2015–2023)

Cross-source synthesis of how attention evolved.

## Timeline
1. [[attention-mechanism]] — Bahdanau 2015 ([[bahdanau-2015-analysis]])
2. [[self-attention]] — Vaswani 2017 ([[vaswani-2017-analysis]])
3. [[multi-head-attention]] — also Vaswani 2017
4. [[flash-attention]] — Dao 2022 ([[dao-2022-analysis]])

## Key insight
Each step increased parallelism while preserving or improving quality.

## Gaps
- No source in KB covers sparse attention variants (2019-2021 period)
```

**Rules**:
- `meta-kind` required.
- Created when 2+ sources cover overlapping topics.
- Link to all relevant source analyses and entries.

---

## Question

**Path**: `knowledge/questions/<kebab-name>.md`
**What**: An open question that a source raises but does not answer — or that emerges from cross-source analysis.

```yaml
---
type: question
created: 2025-01-15
updated: 2025-01-15
source-ids: [vaswani-2017]
tags: [attention, scaling]
status: open | partially-answered | answered
raised-by: source | exploration | revisit
---
```

```markdown
# Does self-attention scale to sequences longer than training length?

## Origin
**Source**: [[vaswani-2017-analysis]]
**Passage**: "We have not explored the limits of sequence length in our experiments; all evaluations used sequences of at most 512 tokens."

## Why it matters
Production use cases (legal documents, codebases, books) routinely exceed 512 tokens. If attention degrades at longer sequences, the architecture needs modification.

## What we know
- Original experiments capped at 512 tokens
- Later work: [[dai-2019-analysis]] introduced relative position encodings, partially addressing this

## What we don't know
- Theoretical bounds on attention quality degradation with length
- Whether linear attention variants preserve the same representation quality

## Related
- [[self-attention]], [[transformer-architecture]], [[positional-encoding]]
```

**Rules**:
- `status` is required: `open` (no answer in KB), `partially-answered` (some evidence found), `answered` (resolved with source).
- `raised-by` is required: `source` (explicitly raised in a source text), `exploration` (emerged during kb:explore), `revisit` (noticed during kb:revisit).
- **Every question MUST cite a specific passage or observation.** The `## Origin` section MUST include a wikilink to the source analysis and the exact sentence/paragraph that prompted the question. Questions without grounding are hallucination risks.
- When a later source answers the question: update `status` to `answered`, add the answer in a `## Resolution` section with source attribution, and wikilink from the answering source's entries back to this question.
- Questions are NOT hypotheses or speculations. They are gaps, open problems, or unexplored directions that the source material itself indicates (explicitly or implicitly).

---

## Custom Entry Types

The 10 built-in types above cover most knowledge domains. However, as a KB grows and covers new source types (codebases, experiments, design patterns, legal cases, recipes, etc.), new entry types may be needed.

**How to add a custom type:**

1. Propose the type in `rules.md` — include: name, directory (`knowledge/<type-name>/`), required frontmatter fields, and when to use it vs. existing types.
2. Create the directory under `knowledge/`.
3. Update `rules.md` with the type definition (the LLM reads rules.md via `open.py`).
4. Custom types MUST follow the same conventions: YAML frontmatter with `type:`, `created:`, `updated:`, `source-ids:`, `tags:`, and any type-specific fields.
5. `lint.py` recognizes any `.md` file under `knowledge/` — custom types get link checking, orphan detection, and frontmatter validation automatically.

**Examples of custom types that might emerge:**
- `experiments/` — for recording experimental results, parameters, and outcomes
- `patterns/` — for design patterns, architectural patterns, anti-patterns
- `code-analysis/` — for analysis of source code, algorithms, API surfaces
- `case-studies/` — for detailed real-world cases with outcomes
- `theorems/` — for formal mathematical results with proofs and implications

**The rules.md file is the authoritative type registry for each KB.** When the LLM encounters a concept that doesn't fit the built-in types, it SHOULD propose a custom type to the user rather than forcing the entry into an ill-fitting category.
