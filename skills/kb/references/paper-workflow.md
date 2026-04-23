# Academic Paper Workflow

Single-session extraction. Always has citation tracking.

1. Read abstract → plan what to extract
2. Read full paper
3. **Extract visual assets** (mandatory for papers with figures/tables):
   - Use `/pdf` `extract_images.py` → save to `knowledge/assets/<source-id>/`
   - Use `/pdf` `render.py` on pages with key figures, architecture diagrams, result tables, or algorithm pseudocode that aren't captured as embedded images
   - Name descriptively: `transformer-architecture.png`, `bleu-score-comparison.png`, `algorithm-1-training-loop.png`
   - Skip: decorative headers, journal logos, page numbers
4. Create entity entries for ALL authors
5. Extract methodology → topic or meta entry if novel
6. Extract findings → conceptual idea entries (attribute to authors + paper). Embed relevant figures: `![[knowledge/assets/<source-id>/<name>.png]]`
7. Run [practical-extraction.md](practical-extraction.md) during the first pass: capture implementation constraints, failure modes, debugging lessons, negative lessons, and decision rules as `idea-kind: practical` entries when the paper genuinely supports them
8. Extract limitations acknowledged by authors → note in source analysis and surface them under `## Pitfalls / Failure Modes`
9. **Citation graph** (mandatory for papers):
   - For each in-text citation: record exact sentence + reference
   - Create citation entries in `knowledge/citations/`
   - Create stub entries for referenced works not yet in KB
   - Flag bibliography items never cited in text
10. Cross-reference with existing KB
11. If this paper contradicts another in KB → controversy entry
12. In the source analysis, include `## Hidden Gems`, `## Know-How`, and when relevant `## Pitfalls / Failure Modes`. If the paper is purely theoretical and yields no honest practical lesson, write `No practical insight justified from this source.`

Then complete the universal checklist from [add-workflow.md](add-workflow.md): multi-perspective pass, question generation, creative cross-linking, backlink enforcement.
