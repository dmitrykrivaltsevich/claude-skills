# Video, Podcast & URL Reference Workflows

## Video / Podcast Transcript

Treat like an article but with speaker attribution.

1. If no transcript exists, tell the user (you can't transcribe)
2. If transcript provided: identify all speakers → entity entries
3. Extract claims/ideas → attribute to specific speaker
4. Note: timestamps are useful for the user, include them in entries when available
5. Extract all entities, topics, ideas mentioned
6. Source analysis notes it's a transcript (less formal than written sources)

Then complete the universal checklist from [add-workflow.md](add-workflow.md): multi-perspective pass, question generation, creative cross-linking, backlink enforcement.

## URL Reference

No full text available — just metadata and user-provided context.

1. Source registered as reference stub (no file copy)
2. Create minimal entries from what you know (title, author, topic)
3. Mark entries as `stub: true` in frontmatter — they need enrichment later
4. If user provides notes about the URL, extract from those
5. Flag in source analysis: "Reference only — full text not ingested"
