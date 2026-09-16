You are doing the post-merge TRIANGULATION pass of a kb:batch-add. Isolated workers could not link each other's entries — you close that gap with the full merged graph visible. Additive edits only (see constraint 5).

SETUP:
- KB_PATH=%%KB_PATH%%, BATCH_ID=%%BATCH_ID%%
- Batch sources in merge order: %%SOURCE_LIST%%
- SKILL scripts: %%SKILL_DIR%%/scripts/ (run as: uv run --no-config <script> ...)
- Schema/hygiene: %%SKILL_DIR%%/references/entry-types.md (triangulation rules, reciprocal-link discipline)

PROCEDURE (one overlap cluster at a time):
1. Read .kb/batches/%%BATCH_ID%%/merge-queue.json (paths + parties + conflicts) — these files overlapped and need the closest look. Also run: uv run --no-config %%SKILL_DIR%%/scripts/related.py --kb-path %%KB_PATH%% --keywords "<3-6 key terms per batch source>" --output /tmp/tri-rel.json, then reopen top hits with json_query.py. This finds same-concept entries under different slugs and shared mechanisms across batch sources.
2. For each genuine overlap cluster: (a) if two entries cover the same concept, FOLD the weaker into the richer one (move unique facts with attribution, redirect its incoming wikilinks, delete the weaker file); (b) otherwise insert RECIPROCAL cross-source wikilinks between the entries (both directions, appropriate sections); (c) if claims disagree, write knowledge/controversies/<slug>.md with cross-refs from all sides (never silently pick a winner).
3. For each merge-queue file with needs_llm: restructure into ONE narrative (single `# ` heading, merged Sources section, all facts kept with attribution) — this clears the union artifact. Never drop a fact to make prose prettier.
4. Write one knowledge/meta/<batch>-<cluster>.md comparison per cluster with 2+ batch sources (thesis per source, agreements, disagreements, open threads), cross-linked from all involved analyses.
5. Update .kb/batches/%%BATCH_ID%%/merge-queue.json: set needs_llm false on every entry you refined, with a one-line note each. Do NOT delete entries (audit trail).
6. Update %%KB_PATH%%/index.md for any entry you folded/renamed (keep bullets resolving). Do NOT touch log.md, sources/, .kb/* (except the queue file above).

CONSTRAINTS:
1. Every new wikilink reciprocal — verify both directions exist before moving on.
2. No dangling links: link target must exist or be created in the same pass.
3. Additive-or-restructure only on merged files: move/keep facts, never delete claims (fold only exact-duplicate entries, redirecting links first).
4. NEVER re-run batch_merge.py after this pass starts (semantic edits break union containment; the phase machine agrees — merge is behind you).
5. Do NOT run kb:lint (separate scripted pass follows). Do NOT edit .kb/rules.md.

FINAL MESSAGE BACK (compact): {clusters_found, folds (from→into), cross_links_added, controversies, meta_entries, queue_entries_cleared, files_restructured}.
