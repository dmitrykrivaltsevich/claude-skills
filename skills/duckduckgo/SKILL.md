---
name: duckduckgo
description: Searches the internet via DuckDuckGo for text, image, and news results. Use for general web searches, fact-finding, visual search, and finding current information.
allowed-tools:
  - Bash(uv run *)
  - open_browser_page
user-invocable: true
---

# DuckDuckGo Search Skill

## Quick Start

```bash
# Text search (web):
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py text --query "your query" [--max-results N]

# Image search:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py image --query "your query" [--size size] [--type type] [--color color] [--max-results N]

# News search:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py news --query "your query" [--max-results N]

# Visual search (analyze an image):
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/vision.py analyze --image-path PATH
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/vision.py find_similar --image-path PATH
```

## Operations

| User intent | Command |
|---|---|
| General web search | `search.py text --query "query" [--max-results N]` |
| Image search | `search.py image --query "query" [--size size] [--type type] [--color color] [--max-results N]` |
| News search | `search.py news --query "query" [--max-results N]` |
| Visual search (find similar images) | `vision.py find_similar --image-path PATH` |
| Analyze image content | `vision.py analyze --image-path PATH` |

## Image Display

VS Code Copilot does NOT render inline images (`![](url)` or `<img>` tags). When the user asks to **show/display images**:
1. Present results as a numbered markdown list with titles and clickable `[title](url)` links.
2. Open the first 3 images in the browser using `open_browser_page` so the user can actually see them.

Do NOT use `![alt](url)` syntax — it does not display in Copilot chat.

## Limitations

- **Rate limit**: ~35 queries/minute — pause between batch requests
- **Results**: defaults to 9 text/news, 30 images — override with `--max-results N`
- **No login required** — public API only
- **Visual search**: Returns image URLs for similar matches

## Technical Details

- **Library** — `ddgs` Python package (handles DDG API endpoints internally)
- **Python** ≥3.11 with PEP 723 inline metadata
- **Runtime** — `uv run` for isolated execution
- **No authentication required**
