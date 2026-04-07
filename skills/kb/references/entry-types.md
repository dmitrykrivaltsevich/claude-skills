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

---

## Entity

**Path**: `knowledge/entities/<kebab-name>.md`
**What**: A person, organization, institution, or named thing.

```yaml
---
type: entity
created: 2025-01-15
updated: 2025-01-15
source-ids: [src-001, src-003]
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

## Sources
- [[src-001-analysis]] — biography chapter 3
- [[src-003-analysis]] — referenced in physics history
```

**Rules**:
- One file per entity. Accumulates facts from multiple sources.
- `entity-kind` is required.
- Link to ideas they originated, organizations they belong to, timeline entries for key dates.

---

## Topic

**Path**: `knowledge/topics/<kebab-name>.md`
**What**: A subject area, field, discipline, or theme. NOT attributable to a single person.

```yaml
---
type: topic
created: 2025-01-15
updated: 2025-01-15
source-ids: [src-001]
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

---

## Idea

**Path**: `knowledge/ideas/<kebab-name>.md`
**What**: A specific intellectual contribution — attributable to person(s) or paper(s).

```yaml
---
type: idea
created: 2025-01-15
updated: 2025-01-15
source-ids: [src-002]
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

## Evidence
- BLEU score of 28.4 on WMT 2014 EN-DE (src-002, Table 2)
- Training time reduced by order of magnitude vs. recurrent models

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

---

## Location

**Path**: `knowledge/locations/<kebab-name>.md`
**What**: A geographic place relevant to the KB.

```yaml
---
type: location
created: 2025-01-15
updated: 2025-01-15
source-ids: [src-001]
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
source-ids: [src-001]
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

**Path**: `knowledge/sources/<src-id>-analysis.md`
**What**: Per-source summary and metadata. One per ingested source.

```yaml
---
type: source-analysis
created: 2025-01-15
updated: 2025-01-15
source-ids: [src-001]
tags: [biography, physics]
source-type: book | paper | article | transcript | reference
---
```

```markdown
# src-001 — "Einstein: His Life and Universe"

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

## Processing notes
- Chapters 1-5 processed in session 1
- Chapters 6-12 processed in session 2
- Synthesis completed in session 3
```

**Rules**:
- One per source. Named `<src-id>-analysis.md`.
- Must include summary, key extractions (what entries were created/updated), bibliography analysis (for academic sources).

---

## Citation

**Path**: `knowledge/citations/<source-id>-cites-<ref-slug>.md`
**What**: A specific citation relationship between a source and a referenced work.

```yaml
---
type: citation
created: 2025-01-15
source-ids: [src-002]
cited-work: "Bahdanau et al., 2015, Neural Machine Translation by Jointly Learning to Align and Translate"
cite-key: "[14]"
tags: [attention, nmt]
---
```

```markdown
# src-002 cites Bahdanau et al. 2015

**Context**: "The dominant approach to attention mechanisms was introduced by Bahdanau et al. [14], who proposed learning alignment scores between encoder and decoder states."

**Claims supported**: Bahdanau introduced the dominant attention mechanism approach.

**See also**: [[attention-mechanism]], [[neural-machine-translation]], [[dzmitry-bahdanau]]
```

**Rules**:
- `cited-work` is the full bibliographic reference.
- `cite-key` is the in-text citation marker from the source.
- Context must be the exact sentence(s) containing the citation.
- Create even for works NOT in the KB — they accumulate incoming citations.

---

## Controversy

**Path**: `knowledge/controversies/<kebab-name>.md`
**What**: A contradiction, debate, or disagreement found across sources.

```yaml
---
type: controversy
created: 2025-01-15
updated: 2025-01-15
source-ids: [src-001, src-004]
tags: [attribution, physics]
status: open | resolved
---
```

```markdown
# Did Mileva Marić Contribute to Relativity?

## Position A — Yes
Source: [[src-004-analysis]] — "Letters suggest collaborative work on the mathematics"
Entities: [[mileva-maric]]

## Position B — No
Source: [[src-001-analysis]] — "No documentary evidence of intellectual contribution"
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
source-ids: [src-001, src-002, src-005]
tags: [comparison, attention]
meta-kind: comparison | synthesis | timeline-overview | gap-analysis
---
```

```markdown
# Attention Mechanisms — Evolution (2015–2023)

Cross-source synthesis of how attention evolved.

## Timeline
1. [[attention-mechanism]] — Bahdanau 2015 ([[src-005-analysis]])
2. [[self-attention]] — Vaswani 2017 ([[src-002-analysis]])
3. [[multi-head-attention]] — also Vaswani 2017
4. [[flash-attention]] — Dao 2022 ([[src-008-analysis]])

## Key insight
Each step increased parallelism while preserving or improving quality.

## Gaps
- No source in KB covers sparse attention variants (2019-2021 period)
```

**Rules**:
- `meta-kind` required.
- Created when 2+ sources cover overlapping topics.
- Link to all relevant source analyses and entries.
