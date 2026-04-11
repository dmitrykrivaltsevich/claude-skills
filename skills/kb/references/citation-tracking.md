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
