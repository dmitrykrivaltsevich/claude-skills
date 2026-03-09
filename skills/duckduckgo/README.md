# DuckDuckGo Search Skill

Search the internet via DuckDuckGo's public APIs for text results, images, and news. No authentication required.

## Operations

| Script | Purpose |
|--------|---------|
| `search.py` | Text, image, and news search with query parameters |
| `vision.py` | Visual search - analyze images and find similar ones |

### Text Search

```bash
# Simple keyword search:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py text --query "machine learning applications"

```

### Image Search

```bash
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py image --query "circuit board diagram" \
  --size large \
  --type png \
  --color white
```

Size options: `Small`, `Medium`, `Large`, `Wallpaper`
Type options: `photo`, `clipart`, `gif`, `transparent`, `line`
Color options: `color`, `Monochrome`, `Red`, `Orange`, `Yellow`, `Green`, `Blue`, `Purple`, `Pink`, `Brown`, `Black`, `Gray`, `Teal`, `White`

### News Search

```bash
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py news --query "AI breakthrough 2026"
```

### Visual Search

```bash
# Find images similar to this file:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/vision.py find_similar --image-path path/to/image.jpg

# Analyze image and get description:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/vision.py analyze --image-path path/to/image.jpg
```

## Architecture

```
duckduckgo/
  SKILL.md                    # Claude runtime instructions (frontmatter + ops)
  README.md                   # This file - user documentation
  scripts/
    search.py                 # Text, image, news search
    vision.py                 # Visual search and analysis
  tests/                      # Unit tests for search queries
```

## Technical Details

- **Python** ≥3.11 — all scripts use PEP 723 inline metadata
- **Runtime** — `uv run` for isolated, sandboxed execution (no global installs)
- **Library** — `duckduckgo-search` Python package (handles DDG API endpoints internally)
- **No authentication required**

## Testing

```bash
# Run all tests:
uv run --with pytest --with duckduckgo-search --with Pillow pytest tests/ -v

# Test search only:
uv run --with pytest --with duckduckgo-search pytest tests/test_search.py -v

# Test vision only:
uv run --with pytest --with duckduckgo-search --with Pillow pytest tests/test_vision.py -v
```
