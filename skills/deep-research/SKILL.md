---
name: deep-research
description: Orchestrates multi-phase autonomous research across all available skills. Discovers skill capabilities, manages persistent research state (questions, sources, facts, coverage), and guides the LLM through scope → sweep → deep-read → cross-reference → synthesise phases. Use when the user asks for deep research, comprehensive analysis, multi-source investigation, literature review, or any task requiring iterative search-read-analyse cycles across multiple data sources.
allowed-tools:
  - Bash(uv run *)
  - Bash(cat *)
user-invocable: true
---

# Deep Research Skill

> **MANDATORY — read before doing anything else:**
>
> 1. **NEVER delegate research to Agent() or any subagent.** Execute ALL phases directly in the main conversation. Spawning an Agent bypasses these instructions and breaks the workflow.
> 2. **NEVER use built-in Fetch to download URLs.** It does NOT mimic a browser and gets blocked (403). To download ANY URL, use duckduckgo's `download.py` — it sets browser headers and handles anti-bot protection. **Every URL you want to read MUST go through `download.py`.**
> 3. **NEVER use built-in Web Search.** Use duckduckgo's `search.py` instead.
> 4. **`${CLAUDE_SKILL_DIR}` = this skill only.** To run duckduckgo scripts, read the `/duckduckgo` SKILL.md first — it has its own `${CLAUDE_SKILL_DIR}`.

## Contents

1. [Architecture](#architecture)
2. [DuckDuckGo Quick Reference](#duckduckgo-quick-reference)
3. [Scripts](#scripts)
4. [Quick Start](#quick-start)
5. [Research Workflow](#research-workflow--5-phases)
6. [Convergence Rules](#convergence-rules)
7. [State File](#state-file)
8. [State/Environment Discipline](#stateenvironment-discipline)
9. [Working with Other Skills](#working-with-other-skills)
10. [Context Management](#context-management)
11. [Reference](#reference)

## Architecture

**This skill is an orchestrator, not a data fetcher.** It provides two data-pipe scripts — one discovers available skill capabilities, the other manages persistent research state. The LLM does all the thinking: decomposing goals into questions, choosing which skills to invoke, evaluating coverage, deciding when to dig deeper, and synthesising findings.

**The research state/environment is the source of truth.** The transcript is not durable memory. Every broad sweep, shortlist, deep-read batch, and synthesis handoff should be reconstructed from external state/environment artifacts rather than from prior chat turns.

```
User question
    ↓
LLM: decompose into sub-questions
    ↓
discover.py → capability map (what skills/scripts are available)
    ↓
state.py init → create research session
    ↓
┌─────────────────────────────────────────┐
│  PHASE LOOP (LLM orchestrates)         │
│                                         │
│  1. Pick unexplored questions           │
│  2. Choose skill + script for each      │
│  3. Run scripts → capture discovery     │
│     artifacts in external state/env     │
│  4. LLM: narrow to working-set files    │
│     and update research state           │
│  5. LLM: check convergence              │
│  6. If not converged → generate new     │
│     questions, loop back to 1           │
└─────────────────────────────────────────┘
    ↓
state.py export → full research state
    ↓
LLM: synthesise final report
```

## DuckDuckGo Quick Reference

**Before using these commands**: read the `/duckduckgo` SKILL.md to get its `${CLAUDE_SKILL_DIR}`. The variable below (`DDG_DIR`) is a placeholder — replace it with the actual path from the duckduckgo SKILL.md.

```bash
# Web search (text, news, or images):
uv run --no-config ${DDG_DIR}/scripts/search.py text "your query" --max-results 10
uv run --no-config ${DDG_DIR}/scripts/search.py news "your query" --timelimit w
uv run --no-config ${DDG_DIR}/scripts/search.py images "your query"

# Comprehensive news sweep (multiple topics):
uv run --no-config ${DDG_DIR}/scripts/top_news.py --groups tech science

# *** DOWNLOAD ANY URL (replaces Fetch — mimics browser, avoids 403) ***:
uv run --no-config ${DDG_DIR}/scripts/download.py "https://example.com" --format md

# Fact checking (multi-source):
uv run --no-config ${DDG_DIR}/scripts/fact_check.py "claim to verify"

# Trending topics:
uv run --no-config ${DDG_DIR}/scripts/trending.py --discover

# Multi-language search:
uv run --no-config ${DDG_DIR}/scripts/translate_search.py "en:query" "de:query"
```

**When you find a URL you want to read — use `download.py`, NEVER Fetch.** Fetch gets 403 errors; `download.py` mimics a real browser.

For duckduckgo discovery scripts, prefer native `--output` artifact mode over shell redirection.

## State/Environment Discipline

Use two layers of external state/environment:

1. **Research state** — the durable source of truth managed by `state.py`
2. **Round artifacts** — file-backed discovery sets, working sets, and downloaded pages for the current round

**Recommended round layout**:
- `/tmp/<research-id>-<round>-discovery.json` — raw search/fact-check/trend output
- `/tmp/<research-id>-<round>-working-set.json` — shortlisted sources, clusters, gaps, or support matrix
- `/tmp/<research-id>/pages/<slug>.md` — downloaded page text
- `/tmp/<research-id>-<round>-facts.json` — facts to append to `state.py`

Rules:
- Broad tool output MUST land in round artifacts first, not in the transcript.
- `state.py` stores accepted research state: questions, sources, facts, phases.
- Round artifacts store messy intermediate environment state for the current pass.
- When resuming, start from `state.py` plus the latest working-set artifact, not from chat history.
- After a phase boundary, carry forward only `{research_id, phase, artifact paths, small summary, next action}`.
- Use `json_query.py` to reopen only the slice you need from saved JSON artifacts instead of rereading the entire file.

## Scripts

| Task | Script | What it does |
|---|---|---|
| Discover available skills | `discover.py` | Scans skills/ directory, outputs JSON capability map |
| Initialize/resume research | `state.py init` | Creates or resumes a research session |
| Add research questions | `state.py add-questions` | Appends questions (deduped) to state (use `--file`) |
| Update question status | `state.py update-question` | Marks question as unexplored/partially/covered (use `--file`) |
| Add sources | `state.py add-sources` | Records URLs/docs with skill attribution (use `--file`) |
| Add facts | `state.py add-facts` | Records claims with source IDs and confidence (use `--file`) |
| Advance phase | `state.py update-phase` | Moves to next research phase |
| Check progress | `state.py status` | Returns coverage summary JSON |
| Export full state | `state.py export` | Dumps complete research state as JSON |
| Reopen JSON slices | `json_query.py` | Returns only the selected slice from a saved JSON artifact |

## Quick Start

```bash
# Discover what skills are available:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/discover.py [--skills-dir PATH]
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/discover.py --output /tmp/discover.json

# Initialize a research session:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py init --research-id "my-topic" --goal "Understand X in depth"

# Add questions — use Write tool to create the JSON file, then pass --file:
#   Write /tmp/questions.json with: ["What is X?", "How does Y relate to Z?"]
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py add-questions --research-id "my-topic" --file /tmp/questions.json

# Update a question's status:
#   Write /tmp/uq.json with: {"question": "What is X?", "status": "covered"}
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py update-question --research-id "my-topic" --file /tmp/uq.json --status covered

# Record sources found:
#   Write /tmp/sources.json with: [{"url": "https://...", "title": "Article", "skill": "duckduckgo"}]
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py add-sources --research-id "my-topic" --file /tmp/sources.json

# Record extracted facts:
#   Write /tmp/facts.json with: [{"claim": "X causes Y", "source_ids": ["s1", "s2"], "confidence": "high"}]
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py add-facts --research-id "my-topic" --file /tmp/facts.json

# Advance to next phase:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py update-phase --research-id "my-topic" --phase sweep

# Check progress:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py status --research-id "my-topic"

# Export full state for synthesis:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py export --research-id "my-topic"
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py export --research-id "my-topic" --output /tmp/research-state.json

# Reopen only the covered questions from a saved state artifact:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/json_query.py --file /tmp/research-state.json --selector questions --where status=covered --fields text

# Custom state directory (when user says "store results in ..."):
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py init --research-id "my-topic" --goal "..." --state-dir /path/to/custom/dir
```

## Research Workflow — 5 Phases

The LLM drives each phase. Scripts provide I/O and persistence; the LLM provides reasoning.

### Phase 1: Scope & Decompose

1. Run `discover.py` to see what skills/scripts are available
2. Run `state.py init` to create a research session
3. Decompose the user's goal into 5–15 specific, answerable sub-questions
4. Run `state.py add-questions` to record them
5. Run `state.py update-phase --phase scope`

**LLM guidance**: Questions should be concrete and verifiable. Bad: "Is AI good?" Good: "What are the top 3 documented risks of LLM deployment in healthcare as of 2026?" Each question should be answerable by finding specific sources.

### Phase 2: Broad Sweep

> **Reminder**: Do NOT use Agent(), Web Search, or Fetch. Run duckduckgo scripts directly via `uv run`.

1. For each unexplored question, choose the best skill/script to gather data
2. Run the chosen skill's scripts into a **discovery artifact**, not into the transcript — **read the skill's SKILL.md first** to get correct commands
3. Build a **working-set artifact** from that discovery artifact: shortlist, gap list, clusters, or support matrix
4. Record discovered sources via `state.py add-sources`, but only for the working set you actually carry forward
5. Extract preliminary facts from the working-set artifact via `state.py add-facts`
6. Mark questions as `partially` if some data found, leave `unexplored` if nothing useful
7. Run `state.py update-phase --phase sweep`

**Skill routing** — use the capability map from discover.py, then READ the target skill's SKILL.md:
- Web search → read `/duckduckgo` SKILL.md, use its `search.py`, `top_news.py`. NEVER use built-in Web Search.
- Page download → read `/duckduckgo` SKILL.md, use its `download.py`. NEVER use built-in Fetch.
- Fact checking → read `/duckduckgo` SKILL.md, use its `fact_check.py`
- Trending topics → read `/duckduckgo` SKILL.md, use its `trending.py`
- Google Drive documents → read `/google-drive` SKILL.md, use its scripts
- Other skills as discovered

**Decomposition before search**: For specialized topics, decompose into precise queries BEFORE running search scripts. Enumerate vendors, products, publications, and sub-categories from existing knowledge, then search for each specifically.

**Artifact-first pattern**:
- Capture broad sweep output to `/tmp/<research-id>-qN-discovery.json` via the source skill's native `--output` flag when available
- Build `/tmp/<research-id>-qN-working-set.json`
- Append only shortlisted sources and accepted preliminary facts into `state.py`
- Discard raw discovery from working memory once the working-set artifact exists

### Phase 3: Deep Read

1. For each `partially` covered question, fetch full content of promising sources from the latest working-set artifact
2. Read `/duckduckgo` SKILL.md, use its `download.py` to get full text into `/tmp/<research-id>/pages/` (or `/google-drive` `download.py` for Drive files)
3. Extract detailed facts with source attribution into a facts artifact
4. Run `state.py add-facts` for each batch of findings
5. Discover new questions from what was read — run `state.py add-questions`
6. Update question statuses based on new evidence
7. Run `state.py update-phase --phase deep-read`

**LLM guidance**: Read critically. Note contradictions between sources. When sources disagree, record both claims with confidence levels: `high` (multiple quality sources agree), `medium` (single source or partial evidence), `low` (unverified, social media, single blog).

### Phase 4: Cross-Reference

1. Run `state.py export` to see all accumulated facts
2. Reopen only the smallest relevant working-set or facts artifacts needed for the current contradiction/gap
3. Look for contradictions, gaps, and patterns across sources
4. For contradictions: search for additional sources to resolve them
5. For gaps: generate targeted new questions, go back to sweep/deep-read
6. Update fact confidence levels based on cross-source agreement
7. Run `state.py update-phase --phase cross-reference`

**LLM guidance**: This is where analytical quality matters most. Cluster facts by theme. Identify which claims have multi-source backing vs. single-source. Flag facts where the only sources are opinion pieces or social media.

### Phase 5: Synthesise

1. Run `state.py export` for the final state
2. Run `state.py status` to confirm coverage
3. Synthesise findings into a structured report with:
   - Executive summary
   - Key findings with **inline numbered citations** `[1]`, `[2]` etc. in the body text
   - Confidence assessment per finding
   - Open questions / areas needing more research
   - Numbered **Sources** section — each source gets a number matching the inline citations, with full title, author (if known), URL, and access date
4. Every claim, statistic, or factual statement in the report MUST have at least one inline citation `[N]` pointing to the Sources section. Do not leave any claim unsourced.
5. Run `state.py update-phase --phase synthesise`

## Convergence Rules

The LLM decides when to stop. These are guidelines, not hard limits:

| Signal | Meaning |
|---|---|
| All questions `covered` | Research goal fully addressed |
| 3 consecutive rounds with <2 new facts | Diminishing returns — synthesise |
| ≥80% questions `covered` or `partially` | Good enough — ask user if they want deeper |
| Contradictions resolved or explicitly flagged | Cross-reference phase complete |

**Never stop prematurely** if there are still `unexplored` questions with available data sources. The goal is thoroughness within the user's topic, not speed.

## State File

- **Default location**: `~/.cache/deep-research/<research-id>.json`
- **Override**: When the user says "store intermediate results in /path/to/dir", pass `--state-dir /path/to/dir` to all `state.py` commands
- **Resume**: Re-running `state.py init` with the same research-id returns the existing state without overwriting. All subsequent commands append without data loss.
- **Research ID**: Use a slug derived from the research goal (e.g. `quantum-computing-trends-2026`). Keep it short and filesystem-safe.

The state file stores accepted research state. It does NOT replace round-level discovery or working-set artifacts.

## Working with Other Skills

This skill does NOT fetch data itself. It orchestrates other skills. **Execute searches directly — NEVER delegate to Agent().**

> **PATH WARNING**: Each skill has its OWN `${CLAUDE_SKILL_DIR}`. You MUST read the target skill's SKILL.md before running its scripts — that will give you the correct `${CLAUDE_SKILL_DIR}` for that skill. NEVER construct paths to other skills' scripts using this skill's `${CLAUDE_SKILL_DIR}`.

**How to invoke another skill's scripts**:
1. Read the skill's SKILL.md (e.g. read `/duckduckgo` SKILL.md)
2. The SKILL.md will show commands using `${CLAUDE_SKILL_DIR}` — that variable resolves to the correct path for THAT skill
3. Copy the command patterns from that SKILL.md and run them

**Workflow**:
1. **Discovery**: `discover.py` tells you WHAT skills exist and what they can do
2. **Invocation**: Read the target skill's SKILL.md to get the correct script commands
3. **Attribution**: When recording sources via `state.py add-sources`, set the `skill` field

**Example routing decisions** (read the skill's SKILL.md first for exact commands):
- "Find recent news about X" → read `/duckduckgo` SKILL.md → use its `search.py news`
- "Get comprehensive coverage" → read `/duckduckgo` SKILL.md → use its `top_news.py`
- "Download full article" → read `/duckduckgo` SKILL.md → use its `download.py`
- "Find our internal doc about X" → read `/google-drive` SKILL.md → use its `search.py`
- "Verify this claim" → read `/duckduckgo` SKILL.md → use its `fact_check.py`
- "Get trending angles" → read `/duckduckgo` SKILL.md → use its `trending.py`

## Context Management

For large research tasks, the context window can fill up. The LLM should:

1. **Capture early**: Broad sweep output goes to discovery artifacts immediately. Do NOT let raw search results sit in the transcript.
2. **Offload to state/environment**: `state.py` is the durable research memory; round artifacts hold the messy local environment for the current pass.
3. **Rebuild from artifacts**: When starting a new phase, export `state.py` and reopen only the latest working-set artifacts you need.
4. **Split rounds**: Do 3–5 questions per round, persist sources/facts, then move to the next batch. This keeps each round manageable.
5. **Progressive depth**: Start with broad sweeps, then deep-read only the most promising sources. Don't try to download every article.
6. **Carry compact handoffs only**: The next step should usually receive only research id, phase, artifact paths, and a short summary.

`json_query.py` is the default narrow-reopen tool for JSON artifacts. Prefer it over loading a full exported state when you only need one field, one list, or a filtered subset.

## Large Data — MUST Use `--file`

When adding questions, sources, or facts, **always use your Write tool** to create a temp JSON file, then pass `--file /path/to/file.json`. NEVER use heredoc (`<< 'EOF'`) or `cat >` in the terminal — these garble output and cause retries. NEVER pass large JSON as inline CLI arguments — shell quoting mangles them.

**Pattern** (repeat for every state update):
1. Use **Write tool** to create `/tmp/<name>.json` with the JSON content
2. Run `uv run --no-config ... --file /tmp/<name>.json`

Affected commands:
- `add-questions --file /tmp/questions.json` — JSON array of question strings
- `add-sources --file /tmp/sources.json` — JSON array of source objects
- `add-facts --file /tmp/facts.json` — JSON array of fact objects
- `update-question --file /tmp/uq.json` — JSON object `{"question": "...", "status": "..."}`

```bash
# Step 1: Write tool → /tmp/questions.json with content:
#   ["What are the key factors?", "How does Y compare to Z?"]
# Step 2: run the script:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py add-questions --research-id "my-topic" --file /tmp/questions.json

# Step 1: Write tool → /tmp/facts.json with content:
#   [{"claim": "fact 1", "source_ids": ["s1"], "confidence": "high"}]
# Step 2: run the script:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py add-facts --research-id "my-topic" --file /tmp/facts.json
```

Inline `--questions`/`--facts`/`--sources` are only safe for 1–2 very short items. For any batch from a research round, use `--file`.

## Reference

See [references/phases.md](references/phases.md) for detailed phase-by-phase prompt patterns and examples.
