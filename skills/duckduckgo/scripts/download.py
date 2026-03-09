#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "httpx >= 0.27",
#   "beautifulsoup4 >= 4.12",
#   "html2text >= 2024.2.26",
#   "fpdf2 >= 2.7",
#   "truststore >= 0.9",
# ]
# ///
"""Download a URL and save it as txt, md, or pdf.

Usage:
    uv run --no-config download.py <url> [--format txt|md|pdf] [--output PATH]

If --output is omitted the file is written to the current directory with a
name derived from the URL.  The format is inferred from the --output extension
when --format is not given.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import textwrap
from pathlib import Path
from urllib.parse import urlparse

import ssl

import httpx
import truststore
from bs4 import BeautifulSoup

# Use the OS native trust store (macOS Keychain / Windows cert store / Linux).
# This avoids SSL verification failures on macOS where Python's bundled certs
# may not match the system-trusted roots.
_SSL_CTX = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

# Maximum bytes to read from the remote page.  Large documents are truncated.
MAX_BYTES = 10 * 1024 * 1024  # 10 MB — avoids hanging on giant resources

# Request timeout in seconds.
TIMEOUT = 20  # generous enough for slow servers but not indefinite

# PDF page width and margins (mm).
PDF_LEFT_MARGIN = 15
PDF_RIGHT_MARGIN = 15
PDF_TOP_MARGIN = 15
PDF_LINE_HEIGHT = 5  # mm per text line
PDF_FONT_SIZE = 10  # pt
PDF_MAX_CHARS_PER_LINE = 95  # chars that fit in a portrait A4 with above settings


def _slug_from_url(url: str) -> str:
    """Derive a safe filename stem from a URL."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "index"
    stem = Path(path).stem or "page"
    stem = re.sub(r"[^\w\-]", "_", stem)
    return stem[:80] or "page"


def fetch(url: str) -> tuple[str, str]:
    """Fetch *url* and return (html_text, final_url).

    Raises SystemExit with an actionable message on network errors.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=TIMEOUT,
            verify=_SSL_CTX,
        ) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            content = resp.content[:MAX_BYTES]
            encoding = resp.encoding or "utf-8"
            return content.decode(encoding, errors="replace"), str(resp.url)
    except httpx.HTTPStatusError as exc:
        sys.exit(
            f"ERROR: HTTP {exc.response.status_code} from {url}\n"
            "Check the URL or try again later."
        )
    except httpx.RequestError as exc:
        sys.exit(f"ERROR: Could not reach {url} — {exc}\nCheck your network connection.")


def _extract_readable(html: str) -> tuple[str, str]:
    """Return (title, main_text) extracted from *html*."""
    soup = BeautifulSoup(html, "html.parser")

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    # Remove navigation, scripts, ads, footers, etc.
    for tag in soup(
        ["script", "style", "nav", "footer", "header", "aside",
         "noscript", "iframe", "svg", "form", "button"]
    ):
        tag.decompose()

    # Prefer <article> or <main> if present; fall back to <body>.
    main = soup.find("article") or soup.find("main") or soup.body or soup
    text = main.get_text(separator="\n", strip=True)

    # Collapse excessive blank lines.
    text = re.sub(r"\n{3,}", "\n\n", text)
    return title, text


def _html_to_markdown(html: str) -> tuple[str, str]:
    """Return (title, markdown_text) converted from *html*."""
    soup = BeautifulSoup(html, "html.parser")

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    import html2text

    h = html2text.HTML2Text()
    h.ignore_links = False       # preserve hyperlinks in markdown
    h.ignore_images = False      # keep image alt text
    h.body_width = 0             # no forced line-wrapping (let editor handle it)
    h.unicode_snob = True        # prefer unicode chars over ASCII approximations
    h.skip_internal_links = True # skip fragment anchors (#section)

    # Remove scripts/styles before conversion.
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    md = h.handle(str(soup))
    md = re.sub(r"\n{3,}", "\n\n", md)
    return title, md


def save_txt(html: str, dest: Path) -> None:
    """Save *html* as plain text to *dest*."""
    title, text = _extract_readable(html)
    parts = []
    if title:
        parts.append(title)
        parts.append("=" * min(len(title), 80))
        parts.append("")
    parts.append(text)
    dest.write_text("\n".join(parts), encoding="utf-8")


def save_md(html: str, dest: Path) -> None:
    """Save *html* as Markdown to *dest*."""
    title, md = _html_to_markdown(html)
    header = f"# {title}\n\n" if title else ""
    dest.write_text(header + md, encoding="utf-8")


def save_pdf(html: str, dest: Path, source_url: str) -> None:
    """Save *html* as a text-based PDF to *dest*."""
    from fpdf import FPDF  # type: ignore[import]

    title, text = _extract_readable(html)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=PDF_TOP_MARGIN)
    pdf.add_page()
    pdf.set_margins(PDF_LEFT_MARGIN, PDF_TOP_MARGIN, PDF_RIGHT_MARGIN)

    # Title
    if title:
        pdf.set_font("Helvetica", style="B", size=14)
        pdf.multi_cell(0, 8, text=title)
        pdf.ln(2)

    # Source URL
    pdf.set_font("Helvetica", style="I", size=8)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 5, text=source_url)
    pdf.ln(4)
    pdf.set_text_color(0, 0, 0)

    # Body — wrap long lines manually for readability
    pdf.set_font("Helvetica", size=PDF_FONT_SIZE)
    for para in text.split("\n"):
        if not para.strip():
            pdf.ln(PDF_LINE_HEIGHT)
            continue
        wrapped = textwrap.wrap(para, width=PDF_MAX_CHARS_PER_LINE) or [""]
        for line in wrapped:
            pdf.cell(0, PDF_LINE_HEIGHT, text=line, new_x="LMARGIN", new_y="NEXT")

    pdf.output(str(dest))


def infer_format(output: Path | None, fmt: str | None) -> str:
    """Resolve the output format from --format and/or --output extension."""
    if fmt:
        return fmt.lower()
    if output:
        ext = output.suffix.lower().lstrip(".")
        if ext in ("txt", "md", "pdf"):
            return ext
    return "txt"  # safe default


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download a URL and save as txt, md, or pdf."
    )
    parser.add_argument("url", help="URL to download")
    parser.add_argument(
        "--format",
        choices=["txt", "md", "pdf"],
        help="Output format (default: inferred from --output extension, else txt)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Destination file path (default: <slug>.<format> in current directory)",
    )
    args = parser.parse_args()

    fmt = infer_format(args.output, args.format)

    print(f"Fetching {args.url} …", file=sys.stderr)
    html, final_url = fetch(args.url)

    dest: Path
    if args.output:
        dest = args.output
        # Ensure parent dirs exist.
        dest.parent.mkdir(parents=True, exist_ok=True)
    else:
        slug = _slug_from_url(final_url)
        dest = Path.cwd() / f"{slug}.{fmt}"

    print(f"Saving to {dest} …", file=sys.stderr)

    if fmt == "txt":
        save_txt(html, dest)
    elif fmt == "md":
        save_md(html, dest)
    elif fmt == "pdf":
        save_pdf(html, dest, final_url)

    size_kb = dest.stat().st_size / 1024
    print(f"Saved: {dest}  ({size_kb:.1f} KB)", file=sys.stdout)


if __name__ == "__main__":
    main()
