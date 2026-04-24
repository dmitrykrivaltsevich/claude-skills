# Deep Research Skill

Autonomous multi-phase research orchestrator that discovers available skill capabilities, manages persistent research state, and guides the LLM through iterative search → read → analyse → synthesise cycles.

## What It Does

This skill does NOT fetch data itself. It orchestrates other skills (duckduckgo, drive, etc.) across 5 research phases:

1. **Scope & Decompose** — break the user's goal into specific questions
2. **Broad Sweep** — search across available skills to find sources
3. **Deep Read** — fetch and read full content of promising sources
4. **Cross-Reference** — validate facts, resolve contradictions, fill gaps
5. **Synthesise** — produce a structured research report

## Scripts

| Script | Purpose |
|---|---|
| `discover.py` | Scans installed skills, outputs JSON capability map |
| `state.py` | Research state CRUD — tracks questions, sources, facts, phases |
| `json_query.py` | Reopens narrow slices from saved JSON artifacts |
| `page_query.py` | Reopens narrow slices from saved markdown/text page artifacts |

## State Persistence

- **Default**: `~/.cache/deep-research/<research-id>.json`
- **Custom**: Pass `--state-dir /path/to/dir` to any `state.py` subcommand
- **Resume**: Re-running `state.py init` with existing research-id returns current state
- **Round artifacts**: Keep discovery sets, working sets, and downloaded pages in temp files or a user-chosen directory; treat them as the research environment, not the transcript. Prefer source-skill native `--output` artifact mode when available.
- **Narrow reopen**: Use `json_query.py` to load only the specific slice you need from a saved JSON artifact.
- **Page reopen**: Use `page_query.py` to load only the specific heading, chunk, or line range you need from a saved markdown/text page.

## Usage

```bash
# Discover available skills:
uv run --no-config scripts/discover.py
uv run --no-config scripts/discover.py --output /tmp/discover.json

# Start research:
uv run --no-config scripts/state.py init --research-id "quantum-2026" --goal "Current state of quantum computing"

# Add questions:
uv run --no-config scripts/state.py add-questions --research-id "quantum-2026" --questions "Q1" "Q2" "Q3"

# Record sources:
uv run --no-config scripts/state.py add-sources --research-id "quantum-2026" \
  --sources '[{"url": "https://...", "title": "...", "skill": "duckduckgo"}]'

# Record facts:
uv run --no-config scripts/state.py add-facts --research-id "quantum-2026" \
  --facts '[{"claim": "...", "source_ids": ["s1"], "confidence": "high"}]'

# Check progress:
uv run --no-config scripts/state.py status --research-id "quantum-2026"

# Export full state:
uv run --no-config scripts/state.py export --research-id "quantum-2026"

# Reopen only the first discovered skill name:
uv run --no-config scripts/json_query.py --file /tmp/discover.json --selector [0] --fields name

# Reopen only one section from a downloaded page artifact:
uv run --no-config scripts/page_query.py --file /tmp/quantum-2026/pages/article.md --heading "Results"
```

## Testing

```bash
cd skills/deep-research
uv run --no-config --with pytest pytest tests/ -v
```

## Architecture

```
skills/deep-research/
├── SKILL.md              # Orchestration workflow for the LLM
├── README.md
├── references/
│   └── phases.md         # Detailed phase-by-phase prompt patterns
├── scripts/
│   ├── contracts.py      # Design by Contract decorators
│   ├── discover.py       # Skill capability scanner
│   ├── json_query.py     # Narrow selector/query helper for JSON artifacts
│   ├── page_query.py     # Narrow selector/query helper for page artifacts
│   └── state.py          # Research state manager
└── tests/
    ├── test_discover.py
    ├── test_json_query.py
    ├── test_deep_research_page_query.py
    └── test_state.py
```
