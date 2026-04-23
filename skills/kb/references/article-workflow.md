# Article / Blog Post Workflow

Single-session extraction. No chunking needed.

1. Read the full text
2. Identify: author, publication date, publication venue
3. Extract visual assets: if source has diagrams, charts, or key figures, extract them to `knowledge/assets/<source-id>/` using `/pdf` skill's `extract_images.py` or `render.py`
4. Create entity entry for author (or update existing)
5. Extract the core argument/thesis → conceptual idea entry
6. Run [practical-extraction.md](practical-extraction.md) during the first pass: capture heuristics, decision rules, pitfalls, debugging lessons, and deployment constraints as `idea-kind: practical` entries when the article genuinely supports them
7. Extract supporting evidence → fold into idea entry or create sub-ideas
8. Extract all mentioned entities, topics, locations, dates
9. Embed extracted figures in relevant entries using `![[knowledge/assets/<source-id>/<name>.png]]`
10. Note any claims that conflict with existing KB → controversy entry
11. Write source analysis with summary + key takeaways. Include `## Hidden Gems`, `## Know-How`, and when relevant `## Pitfalls / Failure Modes`. If the article has no honest operational takeaway, write `No practical insight justified from this source.`
12. Cross-link everything

Then complete the universal checklist from [add-workflow.md](add-workflow.md): multi-perspective pass, question generation, creative cross-linking, backlink enforcement.
