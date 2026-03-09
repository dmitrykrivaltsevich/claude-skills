---
name: duckduckgo
description: Searches the internet via DuckDuckGo for text, image, and news results. Use for general web searches, fact-finding, visual search, and finding current information.
allowed-tools:
  - Bash(uv run *)
user-invocable: true
---

# DuckDuckGo Search Skill

## Quick Start

```bash
# Text search (web):
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py text --query "your query"

# Image search:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py image --query "your query" [--size size] [--type type] [--color color]

# News search:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py news --query "your query"

# Visual search (analyze an image):
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/vision.py analyze --image-path PATH
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/vision.py find_similar --image-path PATH
```

## Operations

| User intent | Command |
|---|---|
| General web search | `search.py text --query "query"` |
| Advanced web search (date, region) | `search.py text --q "q=term&date=Y-m-d"` |
| Image search | `search.py image --query "query" [--size size]` |
| News search | `search.py news --query "query"` |
| Visual search (find similar images) | `vision.py find_similar --image-path PATH` |
| Analyze image content | `vision.py analyze --image-path PATH` |

## Limitations

- **Rate limit**: ~35 queries/minute — pause between batch requests
- **Results capped**: 9 text results, 30 images per query
- **No login required** — public API only
- **Visual search**: Returns image URLs for similar matches

## Technical Details

- **API** - DuckDuckGo Instant Answer / Vision API (public endpoints)
- **Python** ≥3.11 with PEP 723 inline metadata
- **Runtime** - `uv run` for isolated execution
- **No authentication required**
