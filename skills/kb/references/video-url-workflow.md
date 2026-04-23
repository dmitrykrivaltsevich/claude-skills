# Video, Podcast & URL Reference Workflows

## Video / Podcast Transcript

Treat like an article but with speaker attribution.

1. If no transcript exists, tell the user (you can't transcribe)
2. If transcript provided: identify all speakers → entity entries
3. Extract claims/ideas → attribute to specific speaker
4. If the speaker gives concrete tactics, lessons learned, or failure patterns, run [practical-extraction.md](practical-extraction.md) and create `idea-kind: practical` entries
5. Note: timestamps are useful for the user, include them in entries when available
6. Extract all entities, topics, ideas mentioned
7. Source analysis notes it's a transcript (less formal than written sources) and includes `## Hidden Gems`, `## Know-How`, and when relevant `## Pitfalls / Failure Modes`
8. If the transcript has no honest operational takeaway, write `No practical insight justified from this source.`

Then complete the universal checklist from [add-workflow.md](add-workflow.md): multi-perspective pass, question generation, creative cross-linking, backlink enforcement.

## URL Reference

No full text available — just metadata and user-provided context.

1. Source registered as reference stub (no file copy)
2. Create minimal entries from what you know (title, author, topic)
3. Mark entries as `stub: true` in frontmatter — they need enrichment later
4. If user provides notes about the URL, extract from those. Run [practical-extraction.md](practical-extraction.md) only when the notes contain actual tactics or lessons; never infer know-how from metadata alone.
5. Flag in source analysis: "Reference only — full text not ingested"
6. If the notes do not support any honest practical lesson, write `No practical insight justified from this source.`
