# Citation Tracking

For every source that references external works, you MUST build a citation graph. This applies to academic papers (always), textbooks (always), practitioner books (usually — even without formal bibliographies), and articles/blog posts (when they link to sources). Inline URLs, hyperlinks, and footnotes count as references.

## Forward Citations (what this source cites)

For each reference — whether `[1]`, `(Author, Year)`, an inline URL, or a footnote:

1. Identify the exact sentence containing the citation
2. Identify which bibliography entries [1], [2] refer to
3. Create/update citation entry: `knowledge/citations/<source-id>-cites-<ref-slug>.md`
4. Content MUST include:
   - `**Citing source**: [[<source-id>-analysis]]` — mandatory navigable wikilink back to the source
   - `**Context**:` — the exact sentence containing the citation
   - `**Claims supported**:` — what the citation is used for
   - `**Significance**:` — one sentence: why this citation matters (foundational? competing? methodological?)
   - `**See also**:` — wikilinks to related KB entries (entities, topics, ideas)

## Backward Citations (what cites this source)

When a referenced work Y already has an entry in the KB (from a previous source):
- Update Y's entry with the new incoming citation context
- Add wikilink to Y in the citation's **See also** — this enables "show me everything that cites Y" via backlink navigation
- Over time, Y accumulates all sentences from all sources that reference it

## Entries for Works NOT in Sources

Create entries for referenced works even if they're not in your `sources/` directory. These entries:
- Start with just the bibliographic info and incoming citation contexts
- Accumulate more context as more sources are added that reference them
- Serve as "wanted" items — user can decide to add them as full sources later

## Unreferenced Bibliography

If a source lists items in its bibliography but NEVER cites them in the text:
- Record them in the source analysis entry as "listed but unreferenced"
- These may indicate background reading or padding — useful signal for the user

## Examples

### Numbered in-text citation

Source text: "Recent work has shown that transformer architectures outperform RNNs on most NLP benchmarks [3][7]."

Create `knowledge/citations/chen-2023-cites-ref-3.md`:

```markdown
---
type: citation
created: 2025-01-15
source-ids: [chen-2023]
cited-work: "Author et al., 2020, Title of Paper"
cite-key: "[3]"
---

# chen-2023 cites Author et al. 2020

**Citing source**: [[chen-2023-analysis]]

**Context**: "Recent work has shown that transformer architectures outperform RNNs on most NLP benchmarks [3][7]."

**Claims supported**: Transformer superiority over RNNs on NLP benchmarks.

**Significance**: Establishes the empirical basis for the paper's choice of transformer architecture.

**See also**: [[transformers]], [[recurrent-neural-networks]], [[nlp-benchmarks]]
```

### Inline URL citation

Source text (practitioner book or blog): "Bootstrap Thompson Sampling (see https://arxiv.org/abs/1410.4009) approximates the posterior without conjugate priors."

Create `knowledge/citations/sweet-2023-cites-eckles-kaptein-2014.md`:

```markdown
---
type: citation
created: 2025-01-15
source-ids: [sweet-2023]
cited-work: "Eckles & Kaptein, 2014, Thompson Sampling with the Online Bootstrap"
cite-url: "https://arxiv.org/abs/1410.4009"
---

# sweet-2023 cites Eckles & Kaptein 2014

**Citing source**: [[sweet-2023-analysis]]

**Context**: "Bootstrap Thompson Sampling approximates the posterior without conjugate priors."

**Claims supported**: Bootstrap as a practical alternative to exact Bayesian posterior computation.

**Significance**: Key enabler for Thompson Sampling in production — removes the conjugate prior requirement that limits real-world applicability.

**See also**: [[bootstrap-thompson-sampling]], [[olivier-chapelle]]
```

**Note**: Inline URLs, hyperlinks, footnote URLs, and informal references ("see the scikit-learn docs") are ALL valid citations. A book with no formal bibliography but 30 inline URLs has 30 citations — not zero.

### Unreferenced bibliography item

In source analysis (`knowledge/sources/chen-2023-analysis.md`):

```markdown
## Bibliography Analysis

### Unreferenced entries
- [12] Smith et al., 2018 — listed in bibliography but never cited in the paper text
- [15] Jones, 2019 — listed in bibliography but never cited in the paper text
```
