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

## State Persistence

- **Default**: `~/.cache/deep-research/<research-id>.json`
- **Custom**: Pass `--state-dir /path/to/dir` to any `state.py` subcommand
- **Resume**: Re-running `state.py init` with existing research-id returns current state

## Usage

```bash
# Discover available skills:
uv run --no-config scripts/discover.py

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
│   └── state.py          # Research state manager
└── tests/
    ├── test_discover.py
    └── test_state.py
```
