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
8. [Working with Other Skills](#working-with-other-skills)
9. [Context Management](#context-management)
10. [Reference](#reference)

## Architecture

**This skill is an orchestrator, not a data fetcher.** It provides two data-pipe scripts — one discovers available skill capabilities, the other manages persistent research state. The LLM does all the thinking: decomposing goals into questions, choosing which skills to invoke, evaluating coverage, deciding when to dig deeper, and synthesising findings.

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
│  3. Run scripts → get raw data          │
│  4. LLM: extract facts, update state   │
│  5. LLM: check convergence             │
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

## Quick Start

```bash
# Discover what skills are available:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/discover.py [--skills-dir PATH]

# Initialize a research session:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py init --research-id "my-topic" --goal "Understand X in depth"

# Add questions (write JSON to a file, then pass with --file):
cat > /tmp/questions.json << 'HEREDOC'
["What is X?", "How does Y relate to Z?"]
HEREDOC
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py add-questions --research-id "my-topic" --file /tmp/questions.json

# Update a question's status (write JSON to a file, then pass with --file):
cat > /tmp/update_q.json << 'HEREDOC'
{"question": "What is X?", "status": "covered"}
HEREDOC
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py update-question --research-id "my-topic" --file /tmp/update_q.json --status covered

# Record sources found (write JSON to a file, then pass with --file):
cat > /tmp/sources.json << 'HEREDOC'
[{"url": "https://...", "title": "Article", "skill": "duckduckgo"}]
HEREDOC
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py add-sources --research-id "my-topic" --file /tmp/sources.json

# Record extracted facts (write JSON to a file, then pass with --file):
cat > /tmp/facts.json << 'HEREDOC'
[{"claim": "X causes Y", "source_ids": ["s1", "s2"], "confidence": "high"}]
HEREDOC
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py add-facts --research-id "my-topic" --file /tmp/facts.json

# Advance to next phase:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py update-phase --research-id "my-topic" --phase sweep

# Check progress:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py status --research-id "my-topic"

# Export full state for synthesis:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py export --research-id "my-topic"

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
2. Run the chosen skill's scripts — **read the skill's SKILL.md first** to get correct commands
3. Record discovered sources via `state.py add-sources`
4. Extract preliminary facts from result summaries via `state.py add-facts`
5. Mark questions as `partially` if some data found, leave `unexplored` if nothing useful
6. Run `state.py update-phase --phase sweep`

**Skill routing** — use the capability map from discover.py, then READ the target skill's SKILL.md:
- Web search → read `/duckduckgo` SKILL.md, use its `search.py`, `top_news.py`. NEVER use built-in Web Search.
- Page download → read `/duckduckgo` SKILL.md, use its `download.py`. NEVER use built-in Fetch.
- Fact checking → read `/duckduckgo` SKILL.md, use its `fact_check.py`
- Trending topics → read `/duckduckgo` SKILL.md, use its `trending.py`
- Google Drive documents → read `/google-drive` SKILL.md, use its scripts
- Other skills as discovered

**Decomposition before search**: For specialized topics, decompose into precise queries BEFORE running search scripts. Enumerate vendors, products, publications, and sub-categories from existing knowledge, then search for each specifically.

### Phase 3: Deep Read

1. For each `partially` covered question, fetch full content of promising sources
2. Read `/duckduckgo` SKILL.md, use its `download.py` to get full text (or `/google-drive` `download.py` for Drive files)
3. Extract detailed facts with source attribution
4. Run `state.py add-facts` for each batch of findings
5. Discover new questions from what was read — run `state.py add-questions`
6. Update question statuses based on new evidence
7. Run `state.py update-phase --phase deep-read`

**LLM guidance**: Read critically. Note contradictions between sources. When sources disagree, record both claims with confidence levels: `high` (multiple quality sources agree), `medium` (single source or partial evidence), `low` (unverified, social media, single blog).

### Phase 4: Cross-Reference

1. Run `state.py export` to see all accumulated facts
2. Look for contradictions, gaps, and patterns across sources
3. For contradictions: search for additional sources to resolve them
4. For gaps: generate targeted new questions, go back to sweep/deep-read
5. Update fact confidence levels based on cross-source agreement
6. Run `state.py update-phase --phase cross-reference`

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

1. **Summarise early**: After each sweep/deep-read round, record facts into state.py immediately. Don't hold raw search results in context.
2. **Offload to state**: The state file is the persistent memory. Export it when starting a new phase to refresh working memory.
3. **Split rounds**: Do 3–5 questions per round, record facts, then move to the next batch. This keeps each round manageable.
4. **Progressive depth**: Start with broad sweeps (summaries only), then deep-read only the most promising sources. Don't try to download every article.

## Large Data — MUST Use `--file`

When adding questions, sources, or facts, **always write data to a temp file first**, then pass `--file /path/to/file.json`. NEVER pass multi-line text or large JSON as inline CLI arguments — shell quoting mangles them.

Affected commands:
- `add-questions --file /tmp/questions.json` — JSON array of question strings
- `add-sources --file /tmp/sources.json` — JSON array of source objects
- `add-facts --file /tmp/facts.json` — JSON array of fact objects
- `update-question --file /tmp/uq.json` — JSON object `{"question": "...", "status": "..."}`

```bash
# Questions — write array to file:
cat > /tmp/questions.json << 'HEREDOC'
[
  "What are the key factors influencing X?",
  "How does Y compare to Z in the context of W?"
]
HEREDOC
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py add-questions --research-id "my-topic" --file /tmp/questions.json

# Facts — write array to file:
cat > /tmp/facts.json << 'HEREDOC'
[
  {"claim": "fact 1", "source_ids": ["s1"], "confidence": "high"},
  {"claim": "fact 2", "source_ids": ["s2"], "confidence": "medium"}
]
HEREDOC
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py add-facts --research-id "my-topic" --file /tmp/facts.json

# Also works — pipe via stdin:
cat /tmp/facts.json | uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/state.py add-facts --research-id "my-topic" --file -
```

Inline `--questions`/`--facts`/`--sources` are only safe for 1–2 very short items. For any batch from a research round, use `--file`.

## Reference

See [references/phases.md](references/phases.md) for detailed phase-by-phase prompt patterns and examples.
