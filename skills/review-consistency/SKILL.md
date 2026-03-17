---
name: review-consistency
description: Reviews internal consistency of code, documents, diffs, or any structured content. Catches contradictions, forgotten propagation, semantic drift, stale references, implausible claims, argument incoherence, convention breaks, and incomplete changes. Use when the user asks to review consistency, check for contradictions, verify a change is complete, audit docs vs. code alignment, or validate logical coherence of any material.
allowed-tools:
  - Bash(uv run *)
  - Bash(cat *)
user-invocable: true
---

# Review Consistency Skill

## Contents

1. [Purpose](#purpose)
2. [Scripts](#scripts)
3. [Quick Start](#quick-start)
4. [Review Workflow — 4 Phases](#review-workflow--4-phases)
5. [Material Types](#material-types)
6. [Review Modes](#review-modes)
7. [Output Format](#output-format)
8. [Severity Levels](#severity-levels)
9. [Re-Review Workflow](#re-review-workflow)
10. [Context Management](#context-management)
11. [Anti-Patterns to Avoid](#anti-patterns-to-avoid)
12. [Reference](#reference)

## Purpose

This skill provides **stateful, systematic consistency review** with persistent tracking of coverage, claims, and findings. Each review persists its state to disk, enabling:

- **Deterministic coverage** — every file is inventoried, extracted, and cross-checked. Nothing is accidentally skipped.
- **Persistent findings** — findings survive across runs, deduplicated by fingerprint. Fixed issues don't resurface; new issues accumulate.
- **Resumable reviews** — interrupt and resume without losing progress.
- **Change-aware re-reviews** — on re-run, only files with changed content are re-extracted. Unchanged claims persist.

The core insight: inconsistency is **relational** — it exists between two or more statements, not within one. The methodology: extract claims from each file, then systematically compare claims across files.

> **READ-ONLY**: This skill MUST ONLY review and report findings. NEVER fix, edit, modify, or apply changes to the reviewed material. Output is a report — the user decides what to fix.

> **MANDATORY**: Read `references/taxonomy.md` to understand the 8 inconsistency classes and claim categories before starting any review.

## Scripts

| Task | Script | What it does |
|---|---|---|
| Enumerate files | `inventory.py` | Walks paths, computes SHA-256 hashes, outputs JSON file list |
| Initialize/resume review | `state.py init` | Creates or resumes a review session |
| Register file chunks | `state.py add-chunks` | Adds inventory output as trackable chunks |
| Mark chunk status | `state.py update-chunk` | Sets chunk to `extracted` or `reviewed` |
| Record extracted claims | `state.py add-claims` | Persists claims with chunk attribution |
| Record findings | `state.py add-findings` | Adds findings, deduped by fingerprint |
| Update finding status | `state.py update-finding` | Marks finding as `open`/`fixed`/`wont-fix`/`false-positive` |
| Show pending work | `state.py pending` | Lists chunks still needing extraction/review |
| Advance phase | `state.py update-phase` | Moves to next review phase |
| Purge stale claims | `state.py purge-stale-claims` | Removes claims from changed files |
| Check progress | `state.py status` | Returns coverage summary |
| Export full state | `state.py export` | Dumps complete review state as JSON |

## Quick Start

```bash
# 1. Inventory target files:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/inventory.py /path/to/repo --exclude tests fixtures --ext .py .ts .md

# 2. Initialize review session:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py init --review-id "my-review" --scope "Review consistency of src/ module"

# 3. Register chunks (pipe inventory output):
#   Write /tmp/chunks.json from inventory output
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py add-chunks --review-id "my-review" --file /tmp/chunks.json

# 4. Check what needs review:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py pending --review-id "my-review"

# 5. After extracting claims from a file, record them:
#   Write /tmp/claims.json with claims array
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py add-claims --review-id "my-review" --file /tmp/claims.json

# 6. Mark chunk as extracted:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py update-chunk --review-id "my-review" --chunk-id c1 --status extracted

# 7. Record findings from cross-checking:
#   Write /tmp/findings.json with findings array
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py add-findings --review-id "my-review" --file /tmp/findings.json

# 8. Check progress:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py status --review-id "my-review"

# 9. Export full state for report generation:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py export --review-id "my-review"

# Custom state directory:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py init --review-id "my-review" --scope "..." --state-dir /path/to/dir
```

> **Note**: The Quick Start omits `update-phase` calls for brevity. In practice, advance the phase after each stage completes — see the detailed Phase 1–4 workflow below.

## Review Workflow — 4 Phases

The LLM drives each phase. Scripts handle persistence; the LLM does all reasoning.

### Phase 1: Inventory

1. Run `inventory.py` on the target paths to get the file list with hashes
2. Run `state.py init` to create (or resume) the review session
3. Write the inventory JSON to a temp file, run `state.py add-chunks`
4. Run `state.py update-phase --phase extract`

**Scope guidance**: When the user provides a directory, inventory ALL relevant files. Use `--ext` to filter to relevant file types and `--exclude` to skip test fixtures, build outputs, and vendored code.

### Phase 2: Extract

For each unextracted chunk (use `state.py pending` to get the list):

1. **Read the file thoroughly** — no skimming
2. **Extract all claims** — each concrete factual, prescriptive, or structural statement. Classify each claim using the categories from `references/taxonomy.md`:
   - **contract**: explicit interface promise (type signature, schema, API shape)
   - **convention**: implicit project pattern (naming, error handling style, file structure)
   - **assertion**: factual claim about behavior, performance, or state
   - **reference**: pointer to another location (import, link, file path)
3. **Write claims to a temp file**, run `state.py add-claims`
4. **Mark chunk as extracted**: `state.py update-chunk --chunk-id cN --status extracted`
5. Move to next chunk. When all chunks extracted, run `state.py update-phase --phase cross-check`

**Claim format** (JSON array for `add-claims --file`):
```json
[
  {"chunk_id": "c1", "text": "function validate() returns boolean", "category": "contract", "location": "line 42"},
  {"chunk_id": "c1", "text": "all errors logged via logger.error()", "category": "convention", "location": "lines 10-50"}
]
```

**Extract in batches**: Process 3–5 chunks per batch to avoid context saturation. After each batch, persist claims before proceeding.

### Phase 3: Cross-Check

This is where inconsistencies are found. After all claims are extracted:

1. **Export the full state**: `state.py export` → read all persisted claims
2. **Group claims by category** — check contracts against contracts, conventions against conventions
3. **Systematically check the 8 inconsistency classes** from `references/taxonomy.md`
4. **For each finding**, compute a fingerprint (stable hash of class + involved files + short description) and write to `state.py add-findings`
5. **Mark chunks as reviewed**: `state.py update-chunk --chunk-id cN --status reviewed`
6. When all chunks reviewed, run `state.py update-phase --phase report`

**Cross-check in groups**: Don't try to compare all claims at once. Group by:
- Same module/directory (likely to share conventions)
- Same interface consumers (contracts must agree)
- Same data flow (output → input chains)

**Finding format** (JSON array for `add-findings --file`):
```json
[
  {
    "fingerprint": "contradiction-auth-return-type-v1",
    "class": "internal-contradiction",
    "severity": "critical",
    "title": "Auth handler return type mismatch",
    "where": "src/auth.py:42, src/routes.py:18",
    "what": "auth.py returns dict, routes.py expects AuthResult object",
    "why": "Runtime AttributeError when accessing .user_id on dict",
    "suggestion": "Return AuthResult from auth.py or update routes.py to handle dict",
    "chunk_ids": ["c1", "c3"],
    "claim_ids": ["cl2", "cl15"]
  }
]
```

**Fingerprint**: Use a stable, descriptive string that won't change across runs. Good: `"contradiction-auth-return-type-v1"`. Bad: `"issue-1"` or a random hash. This enables deduplication across runs.

### Phase 4: Report

1. Run `state.py export` for the final state
2. Run `state.py status` to confirm coverage (all chunks should be `reviewed`)
3. Generate the report using the output format below
4. Run `state.py update-phase --phase report`

## Material Types

The skill works with **any textual material**, not just code files on disk. The inventory phase adapts:

### Files on Disk (code, docs, configs)

Default path — run `inventory.py` directly on the target paths.

### Diffs / Pull Requests

1. Get the list of changed files: `git diff --name-only main...HEAD` (or use the PR's changed files list)
2. Run `inventory.py` on those changed files specifically
3. Also inventory files that **depend on** the changed files (importers, consumers, docs that reference them) — the LLM identifies these during extraction
4. During cross-check, compare changed-file claims against the full codebase's existing claims (from a prior review, or by inventorying key related files)

### Pasted Text / Inline Content

When the user pastes text or provides content inline (not on disk):

1. Save each logical chunk to a temp file: `/tmp/review-chunk-1.md`, `/tmp/review-chunk-2.md`, etc.
2. Run `inventory.py` on the temp files
3. Proceed with add-chunks → extract → cross-check as normal

### URLs / Web Pages

1. Download pages to local files first (use duckduckgo's `download.py` if available)
2. Run `inventory.py` on the downloaded files
3. Proceed as normal — re-review detects content changes via hash

### Mixed Materials

Combine approaches: inventory code files directly, save pasted text to temp files, download URLs. Add all chunks to the same review session. Cross-check across material boundaries (e.g., do docs match the code? does the design doc match the implementation?).

## Review Modes

Context determines which cross-checking strategy to use. The extract phase is the same regardless.

### Change Review (Diff)

Focus extraction on changed files. Cross-check changed claims against all existing claims from unchanged files. **Key for PR reviews**: also read and extract from files that consume/depend on the changed interfaces, even if they weren't modified.

### Document Review

Extract all factual and prescriptive claims. Cross-check every pair — can both be true simultaneously? Works identically for legal docs, specifications, meeting notes, API docs, or any structured text.

### Cross-File Review

Identify contracts (interfaces, types, schemas) first. Cross-check all consumers against each contract.

### Code-Docs Alignment

Extract claims from docs and code separately. Cross-check doc claims against code claims — where do they disagree?

## Output Format

Report each finding as:

```
### [SEVERITY] Inconsistency Class — Short title

**Where**: file(s) and location(s)
**What**: describe the two (or more) things that conflict
**Why it matters**: what could go wrong
**Suggestion**: how to resolve (if obvious)
```

Group findings by severity. Lead with a summary count:

```
## Consistency Review Summary

Reviewed N files, extracted M claims, found K issues.

- X critical findings
- Y major findings
- Z minor findings
- W nits

(or "No inconsistencies found" — but double-check before saying this)
```

## Severity Levels

| Severity | Meaning | Examples |
|----------|---------|---------|
| **Critical** | Will cause runtime failure, data loss, or security vulnerability | Type mismatch, missing propagation that breaks callers, contradictory access control rules |
| **Major** | Will cause confusion, wrong behavior in edge cases, or maintenance burden | Semantic drift across modules, stale references that mislead, implausible claims in docs |
| **Minor** | Cosmetic or low-impact but still technically inconsistent | Convention breaks, slightly outdated comments, minor terminology drift |
| **Nit** | Stylistic inconsistency, not functionally wrong | Formatting differences, comment style variations |

## Re-Review Workflow

When re-reviewing after fixes (critical for catching everything):

1. **Re-inventory**: run `inventory.py` again on the same paths
2. **Re-add chunks**: `state.py add-chunks` — same review-id. Changed files (different hash) get their status reset to `unreviewed` automatically. Unchanged files keep their `extracted`/`reviewed` status.
3. **Purge stale claims**: `state.py purge-stale-claims` — removes claims from changed files
4. **Re-extract only changed chunks**: `state.py pending` shows only files that need re-extraction
5. **Re-cross-check**: compare new claims against all claims (old + new)
6. **New findings accumulate**: existing findings (by fingerprint) are preserved. Only genuinely new issues get added.
7. **Mark fixed findings**: `state.py update-finding --finding-id fN --status fixed`

This ensures:
- Fixed issues don't resurface (fingerprint dedup)
- Previously found issues aren't lost (persisted state)
- Only changed code is re-analyzed (hash-based change detection)
- Coverage is cumulative, not reset

## Context Management

**The #1 cause of inconsistent reviews is context window saturation.** These rules prevent it:

1. **Never try to hold all claims in context at once.** Export state, read the claims JSON, process in groups.
2. **Extract phase: 3–5 files per batch.** Read files, extract claims, persist, then move to next batch. Don't read 20 files and try to extract from memory.
3. **Cross-check phase: group by relationship.** Don't compare all N² pairs. Group by module, interface, or data flow, then cross-check within groups.
4. **Use the state file as external memory.** After extracting claims from files A–E, you don't need to hold those files in context anymore. The claims are persisted. Move on to files F–J.
5. **Verify coverage with `state.py status`** before generating the report. If `unreviewed_chunks > 0`, go back and finish.

## Anti-Patterns to Avoid

- **Do not fix, edit, or modify the reviewed material.** This skill is strictly read-only. Report findings and stop. Never apply fixes, even if the user says "re-check after changes" — re-check means re-review, not repair.
- **Do not invent problems.** Only report actual inconsistencies you can point to concretely.
- **Do not report style preferences as inconsistencies.** Unless the codebase has an established convention that is broken, stylistic variation is not an inconsistency.
- **Do not overwhelm with nits.** If there are many nits of the same kind, report the pattern once with examples, not each instance separately.
- **Do not skip reading.** Never assess consistency of material you haven't fully read. Use `state.py pending` to verify nothing was skipped.
- **Do not confuse "different" with "inconsistent".** Two modules can use different approaches for good reasons. Inconsistency means they *should* agree but don't.
- **Do not report known trade-offs as inconsistencies.** If the code explicitly documents why it deviates from a convention, that's intentional, not inconsistent.
- **Do not try to hold the entire codebase in context.** Extract claims in batches, persist to state, cross-check in groups.
- **Do not skip the re-review workflow.** When re-reviewing, always re-inventory and re-add chunks so changed files are detected.

## Reference

- [Inconsistency Taxonomy and Claim Categories](references/taxonomy.md) — the 8 inconsistency classes and claim category definitions. **Read before every review.**
