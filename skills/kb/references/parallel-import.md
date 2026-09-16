# Parallel Batch Import (kb:batch-add)

Import a directory of files or a list of URLs with up to 10 isolated workers
extracting in parallel, then merge deterministically so the on-disk result
is indistinguishable from sequential `kb:add` in input order.

## Contents

1. [Protocol At A Glance](#protocol-at-a-glance)
2. [The Four Durability Facts](#the-four-durability-facts)
3. [Coordinator Checklist](#coordinator-checklist)
4. [Delegation Prompts (Don't Retype)](#delegation-prompts-dont-retype)
5. [Worker Contract](#worker-contract)
6. [Merge Policy](#merge-policy)
7. [Lint, Verify, Rules Triage, GC](#lint-verify-rules-triage-gc)
8. [Resume After Interruption](#resume-after-interruption)
9. [Large Batches (Waves)](#large-batches-waves)
10. [Anti-Patterns](#anti-patterns)

## Protocol At A Glance

```
Phase 0 (coordinator, sequential):
  batch_plan.py plan  →  mint ids → pre-register all sources →
  snapshot base → .kb/batches/<id>/manifest.json
Phase 1 (≤10 workers, parallel, staging-only):
  normal kb:add extraction per source → batch_plan.py stage-write
  (never touch knowledge/, sources/, index.md, log.md, .kb/*)
Phase 2 (reconciler, single writer):
  batch_merge.py merge  →  ordered replay, mechanical fast-path,
  per-file escalation on overlap (union keeps every fact)
Phase 2b (triangulation agent, single writer — NEW, closes the 0-cross-link gap):
  batch_prompts.py triangulate  →  cross-source links, folds, meta entries,
  union-artifact cleanup (additive/restructure only, never re-merge after)
Phase 3 (single writer): lint_fix.py backlinks+timeline → lint → fix style → lint clean → mark-done
Phase 4 (coordinator): present rules-combined.md → apply → gc
```

Workers never write the live KB and never do conflict math. All concurrency
lives in the scripts; the final KB equals a replay in manifest order.

## When To Use (And When Not To)

Default: **3+ independent sources → batch-add; 1–2 sources → sequential
`kb:add`.** Below 3, planning + merge overhead exceeds the parallel gain.
Use batch-add also when wall-clock matters more than tokens (parallelism
buys latency, never cost — expect roughly equal token spend either way).
Do NOT use batch-add when later sources must read earlier ones' entries
to be understood (serial argument chains, book volumes) — that is
sequential work by nature. Books inside a batch are fine: each book goes
to ONE worker, which processes it chapter-by-chapter per the worker
prompt — never split one source across workers.

## The Four Durability Facts

- **Unit of work**: one source through stage → merge.
- **Checkpoint artifact**: `.kb/batches/<batch-id>/manifest.json`
  (`{phase, cursor}`) plus `merge-queue.json` after merging.
- **Resume path**: reload the manifest, re-run the current phase command —
  plan, stage-write, and merge are all idempotent (exact-sha1 and
  post-union equality both skip; log/index appends never duplicate).
- **Minimal handoff**: carry only `{batch_id, phase}` in context. Reopen
  details with `batch_plan.py status --output /tmp/batch-status.json`.

## Coordinator Checklist

- [ ] Run `open.py` on the KB first (one active KB at a time).
- [ ] Plan: `uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/batch_plan.py plan --kb-path DIR --input <dir|list.txt> --batch-id <id>` — directory scans use sorted byte order; list files keep caller order (blank lines and `#` comments skipped). Re-running `plan` with the same id resumes; a fresh id requires disjoint inputs.
- [ ] Spawn `min(N sources, 10)` workers, one source per worker (a worker may take several sources sequentially, never concurrently with another worker on the same source). Never run two merges concurrently (single-writer assumption).
- [ ] Wait for all workers (poll `state.py pending --task-id batch-<id>` / `batch_plan.py status --kb-path DIR --batch-id <id>`).
- [ ] Merge: `uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/batch_merge.py merge --kb-path DIR --batch-id <id>` — use `--dry-run` first when the batch is large (writes nothing).
- [ ] Triangulate (closes the parallel gap — isolated workers cannot link each other): render `batch_prompts.py triangulate` and run it as ONE agent pass (cross-source links, same-concept folds, comparison/meta entries, union-artifact cleanup). Additive/restructure only.
- [ ] Mechanical lint repairs via script (never by hand-edit loop): `uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/lint_fix.py backlinks --kb-path DIR --apply`, then `lint_fix.py timeline --kb-path DIR --apply`. Both default to `--dry-run` preview; both are idempotent reruns.
- [ ] Feedback loop for the rest: `uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/lint.py --path DIR` → fix every remaining issue yourself (style phrases need judgment; reference stubs under `sources/references/` are style-scanned, so fix or except those findings too) → re-run lint → repeat until `total_issues == 0`. Render the agent prompt with `batch_prompts.py lint-fix` instead of retyping it.
- [ ] `uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/batch_merge.py mark-done --kb-path DIR --batch-id <id>` (self-verifies the lint gate — it runs `lint_kb` itself and refuses a dirty KB; requires phase `merging`/`linting`).
- [ ] Deterministic audit: `uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/batch_verify.py --kb-path DIR --batch-id <id>` — checks log order, staged-completeness, index coverage, chain integrity, staging-leakage, and tree hash (with `--expect-hash` as a drift gate). Run BEFORE `gc` (completeness needs staging); the report persists as `verify-report.json`.
- [ ] Present `.kb/batches/<id>/rules-combined.md` to the user as one block; apply approved edits to `.kb/rules.md` (or `.kb/rules-proposals.md` unattended).
- [ ] `uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/batch_merge.py gc --kb-path DIR --batch-id <id>` (guarded by phase `done` + the lint report; removes staging scratch, keeps manifest/queue/lint-report/verify-report/rules-combined; `--keep` archives instead).

## Delegation Prompts (Don't Retype)

Render worker and lint-fix prompts from the manifest — never retype IDs,
paths, or contract rules (copy-paste drift caused real staging violations
in early runs):

```bash
# One prompt per source (item id derives from manifest order):
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/batch_prompts.py worker \
  --kb-path DIR --batch-id <id> --source-id <sid>
# Paste the printed prompt into each parallel worker invocation.

# Post-merge triangulation pass (cross-source links, folds, meta):
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/batch_prompts.py triangulate \
  --kb-path DIR --batch-id <id>

# Single final lint-repair prompt after merging:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/batch_prompts.py lint-fix \
  --kb-path DIR --batch-id <id>
```

Both fail loudly on unknown batch/source ids and on template drift
(unsubstituted placeholders are a bug, not a silent omission).

## Worker Contract

You are a normal `kb:add` agent with three restrictions:

1. **Read-only on the live KB.** `open/search/related/graph/page_query` allowed.
2. **Staging-only writes.** Every proposal goes through `batch_plan.py
   stage-write --kb-path DIR --batch-id <id> --source-id <sid>
   --path <knowledge-relative> --content-file <tmp>` (e.g.
   `entities/ada.md`, `timeline/years/2024.md`,
   `knowledge/sources/<id>-analysis.md` via `--path sources/<id>-analysis.md`).
   Assets go under `assets/<source-id>/` (namespaced per source).
   Forbidden: the raw `sources/` layer, `index.md`, `log.md`, `.kb/*`,
   other workers' staging, and `lint` (one final lint runs
   after the merge — running it per worker wastes tokens on a partial graph).
3. **Rules proposals only.** Never edit `.kb/rules.md`; append bullets to
   `staging/<source-id>/rules-proposals.md` (one bullet + evidence quote
   each). The coordinator folds and presents them.

Local link hygiene still applies inside your staged set (no dangling
wikilinks against base + your own stage). Cross-worker backlinks are left
for the final lint.

## Merge Policy

| Situation | Reconciler action |
|---|---|
| Path untouched by others | Fast-forward apply |
| Byte-identical content | Skip (dedup, incl. replays) |
| Same new path, disjoint facts | Union: merge `source-ids`/`tags`, keep every fact with attribution |
| Same path, both changed | Union + `merge-queue.json` entry (`needs_llm: true`, scalar conflicts recorded) for an optional refine pass — never silent last-writer-wins |
| Contradictory claims | Keep both + `merge-queue.json` entry (`needs_llm: true`, conflicts recorded); the LLM refine pass then writes the `controversies/` entry with cross-refs |
| Binary asset collision | Keep both (loser renamed with content-hash suffix) |
| `index.md` / `log.md` / timeline chain / `.kb/*` | Coordinator-owned: rebuilt/appended in manifest order, never merged line-wise |

## Lint, Verify, Rules Triage, GC

- The single post-merge `lint` sees the complete graph — that is where the
  token saving comes from. Run `lint_fix.py` for the mechanical classes
  (reciprocal backlinks, date stubs + chain); do style triage yourself;
  `mark-done` refuses otherwise.
- `batch_verify.py` is the deterministic counterpart to eyeballing:
  run it after `mark-done`, before `gc`. A `warn` status with copyedit
  notes is normal after lint fixes reworded sentences; a `fail` means
  intent was lost — stop and investigate. Record the reported `tree_hash`
  with the release notes; a later `batch_verify.py --expect-hash <hash>`
  fails loudly on any drift of the published tree.
- `rules-combined.md` dedups identical bullets (first source keeps
  attribution). Triage it exactly like `.kb/rules-proposals.md`.
- `gc` is guarded by phase `done` + the lint report, refuses symlinked
  staging, retains manifest/queue/lint-report/verify-report/rules-combined
  as audit, and is idempotent.
- `--keep` archives staging under `.kb/batches-archived/` for debugging.

## Resume After Interruption

1. `batch_plan.py status --batch-id <id>` (read-only; `--output` must live
   outside `.kb/`).
2. Phase `planning` → re-run `plan` (adopts partial registrations).
3. Unstaged sources → re-dispatch those workers only.
4. Phase `merging`/`linting` → re-run `merge` (replay is a no-op for
   applied ops), then continue the lint loop.
5. Phase `done` with staging present → just run `gc`.

Never reconstruct state from chat history — the manifest is the truth.
Never run two merges concurrently (single-writer assumption).

## Large Batches (Waves)

`max-workers` (default 10, hard cap 10) bounds *concurrency*, never total
sources. `plan` partitions manifest order into `waves` (disjoint, complete,
order-preserving — read them from the plan result or the manifest). The
coordinator dispatches one wave at a time: spawn ≤10 workers, wait for all
to finish, then the next wave. No claim protocol is needed — wave membership
is the exclusive assignment.

- **Handoff hygiene.** As source count grows, per-worker handoffs flood context. Per wave, keep
  only `{source_id, started_at, finished_at, counts}` per worker (one line
  each); rely on `batch_plan.py status` and state items for the rest, and
  drop each wave's detail from context before dispatching the next.
- **Stragglers.** A wave finishes when its slowest worker finishes. Put
  predictably heavy sources (books, scanned PDFs) in the same wave so fast
  waves stream through.
- **Dead workers.** An interrupted worker's items stay `in-progress`
  (there is no lease timeout by design — clocks cannot be trusted here).
  Recover explicitly: `state.py update-item --status pending` the stuck
  item, then re-dispatch it in the next wave. Never re-dispatch without
  resetting — two writers on one source breaks the staging contract.
- **Merge scales linearly** (one pass over staged ops, whatever the count).
  Expect more same-file overlaps as sources grow: the queue absorbs
  them, and triangulation runs per cluster below.
- **Triangulate per cluster, not per batch.** One triangulation pass cannot
  hold an arbitrarily large source set. Run it once per topic cluster
  (related-keyword sweeps define the clusters; one `triangulate` invocation
  each, same prompt, different keyword scope), then a single lint-fix +
  lint + mark-done.
- **Lint output is huge at this scale.** Always use `--output` artifacts +
  `json_query.py` slices; never print full results into context.

## Anti-Patterns

- **Workers writing the live tree.** Any direct write under `knowledge/`
  breaks linearization — there is no merge for unrecorded edits.
- **Re-running merge after triangulation/lint-fix.** Semantic edits break
  union containment (reworded sentences no longer match staged bodies),
  so a late re-merge would duplicate content instead of skipping. Merge
  lives behind you: plan → map → merge → triangulate → lint-fix →
  mark-done → verify → gc, never backwards (the phase machine agrees).
- **Per-worker lint.** Misleading on a partial graph; do it once, finally.
- **Reusing a batch-id for new inputs.** `plan` rejects input swaps —
  use a fresh id.
- **Hand-merging conflicts by rewriting both sides.** Let the union keep
  both facts; refine wording in the recorded queue entry only.
