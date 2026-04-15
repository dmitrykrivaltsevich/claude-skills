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
6. Extract findings → idea entries (attribute to authors + paper). Embed relevant figures: `![[knowledge/assets/<source-id>/<name>.png]]`
7. Extract limitations acknowledged by authors → note in source analysis
8. **Citation graph** (mandatory for papers):
   - For each in-text citation: record exact sentence + reference
   - Create citation entries in `knowledge/citations/`
   - Create stub entries for referenced works not yet in KB
   - Flag bibliography items never cited in text
9. Cross-reference with existing KB
10. If this paper contradicts another in KB → controversy entry

Then complete the universal checklist from [add-workflow.md](add-workflow.md): multi-perspective pass, question generation, creative cross-linking, backlink enforcement.
