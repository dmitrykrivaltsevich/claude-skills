# Article / Blog Post Workflow

Single-session extraction. No chunking needed.

1. Read the full text
2. Identify: author, publication date, publication venue
3. Extract visual assets: if source has diagrams, charts, or key figures, extract them to `knowledge/assets/<source-id>/` using `/pdf` skill's `extract_images.py` or `render.py`
4. Create entity entry for author (or update existing)
5. Extract the core argument/thesis → idea entry
6. Extract supporting evidence → fold into idea entry or create sub-ideas
7. Extract all mentioned entities, topics, locations, dates
8. Embed extracted figures in relevant entries using `![[knowledge/assets/<source-id>/<name>.png]]`
9. Note any claims that conflict with existing KB → controversy entry
10. Write source analysis with summary + key takeaways
11. Cross-link everything

Then complete the universal checklist from [add-workflow.md](add-workflow.md): multi-perspective pass, question generation, creative cross-linking, backlink enforcement.
