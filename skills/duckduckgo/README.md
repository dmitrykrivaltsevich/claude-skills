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

# Advanced query with filters:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py text --q "q=python&max_q=10&date=Y-m-d"
```

Query parameters:
- `q` - search term (required)
- `no_html` - boolean, exclude HTML snippets
- `safe_strict` - safe search mode
- `date` - date range filter (Y-m-d format)
- `region` - locale (us, uk, ca, etc.)

### Image Search

```bash
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py image --query "circuit board diagram" \
  --size large \
  --type png \
  --color white
```

Size options: `tiny`, `small`, `medium`, `large`, `huge`
Color options: `any`, `red`, `orange`, `yellow`, `green`, `teal`, `blue`, `purple`, `pink`, `gray`, `black`, `white`, `transparent`
Type options: `gif`, `jpg`, `jpeg`, `png`, `svg`, `webp`, `bmp`

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
- **API** - DuckDuckGo Instant Answer API & Vision API (public endpoints)
- **No authentication required**

## Testing

```bash
# Run all tests:
uv run --with pytest pytest tests/ -v

# Test search functionality:
uv run --with requests python tests/test_search.py::test_text_search
uv run --with requests python tests/test_vision.py::test_find_similar
```
