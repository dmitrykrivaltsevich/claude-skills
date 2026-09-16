You are finishing a kb:batch-add. The merge is done; perform the SINGLE final kb:lint repair pass on KB_PATH=%%KB_PATH%% (batch %%BATCH_ID%%). Read-only first, then fix everything.

SETUP:
- SKILL scripts: %%SKILL_DIR%%/scripts/ (run as: uv run --no-config <script> ...)
- Saved lint artifact (possibly stale): run lint.py yourself with --output /tmp/<batch>-lint.json and reopen slices with json_query.py (--selector issues --fields type file source target --limit 50)
- Style protocol: %%SKILL_DIR%%/references/style-linting.md (rewrite default; verbatim-quote / subject-matter / disable-pattern only when genuinely justified; max 3 passes)
- Entry schema: %%SKILL_DIR%%/references/entry-types.md (timeline entries need type/created/updated/source-ids/tags + prev/next/parent)

PROCEDURE (mechanical first, judgment second):
1. `uv run --no-config %%SKILL_DIR%%/scripts/lint_fix.py backlinks --kb-path %%KB_PATH%% --apply` — fixes every missing reciprocal link. Verify with a lint re-run.
2. `uv run --no-config %%SKILL_DIR%%/scripts/lint_fix.py timeline --kb-path %%KB_PATH%% --apply` — creates missing date stubs + repairs the chain. Verify with a lint re-run.
3. Triage remaining style-phrase findings yourself per style-linting.md (this is the judgment part scripts cannot do).
4. Re-run lint.py until total_issues == 0. NEVER leave findings unresolved for a human to triage.

CONSTRAINTS: touch only %%KB_PATH%%/knowledge/** (new stubs + reciprocal-link edits + style rewrites). NEVER touch sources/, index.md, log.md, .kb/*. Do NOT restructure union-merged files — add links, don't rewrite sections.

FINAL MESSAGE BACK (compact): {fixed_backlinks, fixed_style (rewritten/excepted), timeline_stubs_created, final total_issues (must be 0), not_fixed}.
