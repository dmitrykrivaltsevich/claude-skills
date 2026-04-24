# claude-skills

A collection of skills (plugins) for [Claude Code](https://code.claude.com/docs/en/plugins). Each skill extends Claude with domain-specific capabilities — API integrations, workflows, tooling.

## Installation

### From GitHub (marketplace)

```
/plugin marketplace add dmitrykrivaltsevich/claude-skills
```

Then install the plugin (includes all skills):

```
/plugin install claude-skills@dmitrykrivaltsevich-claude-skills
```

### From a local clone

```bash
git clone https://github.com/dmitrykrivaltsevich/claude-skills.git
claude --plugin-dir ./claude-skills
```

### From a Git URL

```
/plugin marketplace add https://github.com/dmitrykrivaltsevich/claude-skills.git
```

See the [Claude Code plugin docs](https://code.claude.com/docs/en/discover-plugins) for all installation methods and scopes (user / project / local).

## Skills

| Skill | Description |
|-------|-------------|
| [deep-research](skills/deep-research/) | Multi-phase autonomous research across all available skills. Uses persistent research state, round-level artifacts, native artifact mode, JSON slice queries, and page-slice queries to drive scope → sweep → deep-read → cross-reference → synthesise phases without relying on transcript memory. |
| [duckduckgo](skills/duckduckgo/) | Internet search via DuckDuckGo — text, image, and news search using external state/environment artifacts for broad discovery, narrowing, targeted deep reads, and page-slice reopening for downloaded markdown. No auth required. |
| [google-drive](skills/drive/) | Search, list, download/export, upload, create, update, share, and comment on Google Drive files. Supports My Drive and Shared Drives. |
| [pdf](skills/pdf/) | Reads and writes PDF documents. Extracts text as markdown, searches content, extracts embedded images, and renders pages to high-DPI PNG for LLM vision OCR. Writes beautiful PDFs from Typst markup with proper typography, math, and New Computer Modern fonts. |
| [review-consistency](skills/review-consistency/) | Reviews internal consistency of code, documents, diffs, or any structured content. Catches contradictions, forgotten propagation, semantic drift, stale references, and convention breaks. |
| [visualization-datascape](skills/visualization-datascape/) | Generates immersive 3D cyberspace point-cloud visualizations from structured data. Interactive cyberpunk cityscape with explorable data vaults, WASD+QE movement, and orbit controls. |
| [kb](skills/kb/) | LLM-curated local knowledge bases. Extracts knowledge from sources (articles, papers, books), including know-how and hidden gems, creates richly interlinked Obsidian-compatible entries, tracks citations, detects contradictions, and supports cyclic deep analysis and graph topology analysis for discovering hidden connections and structural gaps. |

See each skill's README for setup, architecture, and test instructions.

## License

MIT
