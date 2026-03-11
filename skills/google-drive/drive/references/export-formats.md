# Export Format Reference

When downloading Google Workspace files (Docs, Sheets, Slides, Drawings), they must be
exported to a specific format. Use the `--format` flag with `download.py`.

## Google Docs

| Format | Extension | MIME Type |
|--------|-----------|-----------|
| Markdown | `md` | `text/markdown` |
| PDF | `pdf` | `application/pdf` |
| Word | `docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| Plain Text | `txt` | `text/plain` |
| HTML | `html` | `text/html` |
| RTF | `rtf` | `application/rtf` |
| OpenDocument | `odt` | `application/vnd.oasis.opendocument.text` |
| EPUB | `epub` | `application/epub+zip` |

Default: `md` (includes inline comments)

## Google Sheets

| Format | Extension | MIME Type |
|--------|-----------|-----------|
| CSV | `csv` | `text/csv` |
| Excel | `xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |
| PDF | `pdf` | `application/pdf` |
| OpenDocument | `ods` | `application/vnd.oasis.opendocument.spreadsheet` |
| TSV | `tsv` | `text/tab-separated-values` |

## Google Slides

| Format | Extension | MIME Type |
|--------|-----------|-----------|
| PDF | `pdf` | `application/pdf` |
| PowerPoint | `pptx` | `application/vnd.openxmlformats-officedocument.presentationml.presentation` |
| OpenDocument | `odp` | `application/vnd.oasis.opendocument.presentation` |

## Google Drawings

| Format | Extension | MIME Type |
|--------|-----------|-----------|
| PDF | `pdf` | `application/pdf` |
| PNG | `png` | `image/png` |
| SVG | `svg` | `image/svg+xml` |
| JPEG | `jpg` | `image/jpeg` |

## Regular Files

Non-Google-Workspace files (PDFs, images, ZIPs, etc.) are downloaded as-is without conversion.
