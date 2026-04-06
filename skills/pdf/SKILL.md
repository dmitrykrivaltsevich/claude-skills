---
name: pdf
description: Reads and writes PDF documents. Extracts text as markdown, searches content, extracts embedded images, and renders pages to high-DPI PNG for LLM vision OCR. Writes beautiful PDFs from Typst markup with proper typography, math, and New Computer Modern fonts. Use when the user asks to read, analyze, search, extract from, or create PDF files.
allowed-tools:
  - Bash(uv run *)
  - Read
  - Write
user-invocable: true
---

# PDF Skill

## Contents

1. [Architecture](#architecture)
2. [Script Decision Guide](#script-decision-guide)
3. [Quick Start — Reading](#quick-start--reading)
4. [Quick Start — Writing](#quick-start--writing)
5. [Workflow Patterns](#workflow-patterns)
6. [Large Document Strategy](#large-document-strategy)
7. [OCR via LLM Vision](#ocr-via-llm-vision)
8. [Writing Beautiful PDFs](#writing-beautiful-pdfs)
9. [Typst Quick Reference](#typst-quick-reference)
10. [Limitations](#limitations)

## Architecture

**Scripts = data pipes.** Handle binary PDF I/O, image extraction, page rendering, and Typst compilation. Output JSON to stdout, progress/errors to stderr.

**LLM = brain.** Decides which pages to read, orchestrates multi-step analysis, generates Typst markup for writing, and performs OCR via its own vision on rendered page images.

All scripts are independently runnable and freely composable — the LLM picks which to call and in what order.

## Script Decision Guide

| User says… | Script | What it returns |
|---|---|---|
| "what's in this PDF", "how many pages" | `info.py` | JSON: metadata, TOC, per-page analysis |
| "read this PDF", "extract text from pages 5-10" | `read.py` | JSON: markdown content per page |
| "find X in this PDF", "search for Y" | `search.py` | JSON: matches with page numbers + context |
| "extract images/figures/charts" | `extract_images.py` | Images saved to dir + JSON manifest |
| "this is a scanned PDF", "OCR this" | `render.py` | High-DPI PNGs for LLM vision reading |
| "check how this page looks" | `render.py` | PNG of specific page for visual QA |
| "convert this to PDF", "make a PDF" | `write.py` | Compiled PDF from Typst source |

## Quick Start — Reading

```bash
# PDF overview — metadata, TOC, per-page text/image detection:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/info.py /path/to/file.pdf

# Extract pages as markdown (all pages):
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/read.py /path/to/file.pdf

# Extract specific page range (1-based, inclusive):
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/read.py /path/to/file.pdf --page-start 5 --page-end 10

# Search for text:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py /path/to/file.pdf "query text"
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/search.py /path/to/file.pdf "query" --page-start 1 --page-end 50

# Extract embedded images:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/extract_images.py /path/to/file.pdf --output-dir /tmp/images
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/extract_images.py /path/to/file.pdf --output-dir /tmp/images --page-start 1 --page-end 10

# Render pages to PNG (for OCR via LLM vision or visual QA):
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/render.py /path/to/file.pdf --output-dir /tmp/pages
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/render.py /path/to/file.pdf --output-dir /tmp/pages --page-start 3 --page-end 3 --dpi 400
```

## Quick Start — Writing

```bash
# Compile Typst source to PDF:
uv run --no-config ${CLAUDE_SKILL_DIR}/scripts/write.py /path/to/source.typ --output /path/to/output.pdf
```

The LLM generates the `.typ` file, then calls `write.py` to compile it. If compilation fails, the error messages guide the LLM to fix and retry.

## Workflow Patterns

### Quick factual lookup
```
1. info.py → get TOC + page count
2. search.py "keyword" → find page numbers
3. read.py --page-start N --page-end M → extract matched pages as markdown
4. Present answer to user
```

### Structured document analysis
```
1. info.py → get TOC, identify sections
2. read.py --page-start 1 --page-end 3 → read intro/abstract
3. For each TOC section of interest:
     read.py --page-start N --page-end M → extract section
4. extract_images.py → get figures/charts
5. Synthesize analysis
```

### OCR a scanned/image-only PDF
```
1. info.py → check per-page has_text flags
2. Pages with has_text=false are image-only (scanned)
3. render.py --page-start N --page-end M --dpi 400 → get PNGs
4. LLM reads each PNG via its vision capability
5. Combine extracted text into structured output
```

### Convert markdown to beautiful PDF
```
1. LLM reads the user's .md file(s)
2. LLM generates a .typ file using Typst markup (see Typst Quick Reference)
3. Write the .typ file to disk
4. write.py source.typ --output output.pdf → compile
5. If errors: read error messages, fix .typ source, retry
6. Optional: render.py output.pdf --page-start 1 --page-end 1 → visual QA
```

### Extract all images from a large PDF
```
1. info.py → get page count
2. Process in batches:
     extract_images.py --page-start 1 --page-end 100 --output-dir /tmp/batch1
     extract_images.py --page-start 101 --page-end 200 --output-dir /tmp/batch2
     ...
3. Present manifest to user
```

## Large Document Strategy

For PDFs with 1000+ pages (or multi-GB files), NEVER read the entire document at once. Use page ranges to process in chunks:

1. **Start with `info.py`** — always lightweight, gives TOC + page count regardless of size
2. **Use `search.py`** to find relevant pages instead of reading everything
3. **Read in small batches** — `--page-start` and `--page-end` with 10-50 page ranges
4. **Extract images in batches** — process 50-100 pages at a time
5. **Render selectively** — only render specific pages needed for OCR, not the entire PDF

All scripts support `--page-start` and `--page-end` for this reason.

## OCR via LLM Vision

This skill does NOT bundle a third-party OCR engine. Instead, it relies on the LLM's own multimodal vision:

1. `info.py` detects which pages have no text layer (`has_text: false`)
2. `render.py` renders those pages to 400 DPI PNG images
3. The LLM reads the PNG images directly using its vision capability
4. The LLM extracts text, tables, diagrams with full semantic understanding

This approach is superior to traditional OCR for:
- Complex layouts (multi-column, mixed text/tables)
- Handwritten annotations
- Diagrams and charts (the LLM can describe them)
- Non-Latin scripts
- Low-quality scans

**Requirements:** The LLM must support multimodal vision input.

## Writing Beautiful PDFs

The skill uses [Typst](https://typst.app) — a modern typesetting system with Knuth-quality output. The `typst` Python package bundles the compiler, so it installs via pip with zero system dependencies.

### Fonts

Typst uses system fonts automatically. On macOS, **New Computer Modern** (Knuth's font family) is available by default. Other recommended fonts for beautiful documents:

| Style | Font family | Notes |
|---|---|---|
| Knuth classic | `New Computer Modern` | The TeX/Computer Modern successor, available on macOS |
| Elegant serif | `Palatino`, `Baskerville`, `Hoefler Text` | System fonts on macOS |
| Modern sans | `Helvetica Neue`, `Gill Sans`, `Avenir` | System fonts on macOS |
| Monospace | `Menlo`, `DejaVu Sans Mono` | For code blocks |

### Compile → Check → Fix Loop

Always use this feedback loop when generating PDFs:

```
1. Generate .typ source
2. write.py → compile
3. Check result JSON:
   - success: true → done
   - success: false → read errors[], fix .typ, go to step 2
4. Optional: render first page → visual QA via vision
```

## Typst Quick Reference

The LLM already knows Typst syntax. This section covers patterns specific to producing Knuth-quality documents.

### Book-quality document template

```typst
#set page(paper: "a4", margin: (x: 2.5cm, y: 3cm))
#set text(font: "New Computer Modern", size: 11pt)
#set par(justify: true, leading: 0.65em)  // justified text with comfortable leading
#set heading(numbering: "1.1")

// Title page
#align(center + horizon)[
  #text(size: 24pt, weight: "bold")[Document Title]
  #v(1em)
  #text(size: 14pt)[Author Name]
  #v(0.5em)
  #text(size: 12pt)[#datetime.today().display()]
]
#pagebreak()

// Table of contents
#outline()
#pagebreak()

= Introduction
Your content here...
```

### Key Typst patterns

```typst
// Math (inline and display)
The equation $E = m c^2$ is famous.
$ integral_0^infinity e^(-x^2) dif x = sqrt(pi) / 2 $

// Images
#figure(
  image("path/to/image.png", width: 80%),
  caption: [Description of the figure],
)

// Tables
#figure(
  table(
    columns: 3,
    [Header 1], [Header 2], [Header 3],
    [Cell 1], [Cell 2], [Cell 3],
  ),
  caption: [Table description],
)

// Code blocks
#raw(block: true, lang: "python", "def hello():\n    print('Hello')")

// Footnotes
Some text#footnote[This is a footnote.]

// Lists
- Bullet item
- Another item
  - Nested item

+ Numbered item
+ Another numbered item
```

### Converting Markdown to Typst

| Markdown | Typst |
|---|---|
| `# Heading` | `= Heading` |
| `## Heading` | `== Heading` |
| `**bold**` | `*bold*` |
| `*italic*` | `_italic_` |
| `` `code` `` | `` `code` `` |
| `[text](url)` | `#link("url")[text]` |
| `![alt](img.png)` | `#image("img.png")` |
| `> blockquote` | `#quote[text]` |
| `---` | `#line(length: 100%)` |

## Limitations

- **OCR requires vision-capable LLM** — if the model has no vision, scanned PDFs can only be processed via `read.py` (which reads any existing OCR text layer in the PDF itself)
- **Typst fonts** — uses system fonts; on headless servers, font availability may be limited. On macOS, all system fonts including New Computer Modern are available
- **PDF forms/annotations** — not yet supported for reading or writing
- **Encrypted PDFs** — password-protected PDFs are not supported
