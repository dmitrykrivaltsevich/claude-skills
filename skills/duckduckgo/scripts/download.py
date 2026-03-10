#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "curl_cffi >= 0.7",
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
import io
import os
import re
import sys
import tarfile
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

# ---------------------------------------------------------------------------
#  PDF typesetting — Computer Modern / Knuth-inspired layout
# ---------------------------------------------------------------------------

# CM Unicode font archive (SIL Open Font License).
_CMU_URL = (
    "https://downloads.sourceforge.net/project/"
    "cm-unicode/cm-unicode/0.7.0/cm-unicode-0.7.0-ttf.tar.xz"
)
_FONT_CACHE = Path.home() / ".cache" / "duckduckgo-skill" / "fonts" / "cmu"

# The four TTF variants we embed.  Keys match fpdf2 style strings.
_CMU_FILES = {
    "":   "cmunrm.ttf",   # CMU Serif — Roman (regular)
    "B":  "cmunbx.ttf",   # CMU Serif — Bold Extended
    "I":  "cmunti.ttf",   # CMU Serif — Italic
    "BI": "cmunbi.ttf",   # CMU Serif — Bold Italic
}

# Page geometry (mm) — generous margins in the Knuth / TeX tradition.
# Knuth uses a ~4.5 in text block on a 6×9 page.  For A4 (210×297) we
# replicate the same *proportion*: ~60 % text width, centred.
_PAGE_W = 210                      # A4 width
_MARGIN_LR = 32                    # left = right = 32 mm → text block ≈ 146 mm
_MARGIN_TOP = 36                   # generous head space
_MARGIN_BOT = 32                   # bottom margin (auto-page-break threshold)

# Type sizes (pt) — Knuth uses 10/12 for body text.
_BODY_SIZE = 10.5                  # slightly above 10 for screen readability
_BODY_LEAD = _BODY_SIZE * 1.42    # ~14.9 pt leading — golden ratio-ish line height
_H1_SIZE = 20                      # title
_H1_LEAD = _H1_SIZE * 1.3
_META_SIZE = 8                     # URL, date, footer
_META_LEAD = _META_SIZE * 1.5

# First-line paragraph indent (mm).  Classic TeX uses 1.5 em ≈ 5.25 mm at 10pt.
_PAR_INDENT = 5.5
# Inter-paragraph skip when a blank line separates paragraphs (mm).
_PAR_SKIP = _BODY_LEAD * 0.35     # ~0.35 × leading — subtle but visible

# fpdf2 text-block width after margins
_TEXT_W = _PAGE_W - 2 * _MARGIN_LR


def _ensure_cmu_fonts() -> Path:
    """Download and cache CM Unicode TTFs.  Returns the directory containing them."""
    if _FONT_CACHE.exists() and all(
        (_FONT_CACHE / f).exists() for f in _CMU_FILES.values()
    ):
        return _FONT_CACHE

    print("Downloading Computer Modern Unicode fonts (one-time) …", file=sys.stderr)
    _FONT_CACHE.mkdir(parents=True, exist_ok=True)

    with httpx.Client(follow_redirects=True, timeout=30, verify=_SSL_CTX) as client:
        resp = client.get(_CMU_URL)
        resp.raise_for_status()

    import lzma
    decompressed = lzma.decompress(resp.content)
    needed = set(_CMU_FILES.values())
    with tarfile.open(fileobj=io.BytesIO(decompressed), mode="r:") as tar:
        for member in tar.getmembers():
            basename = Path(member.name).name
            if basename in needed:
                data = tar.extractfile(member)
                if data:
                    (_FONT_CACHE / basename).write_bytes(data.read())
                    needed.discard(basename)
            if not needed:
                break

    if needed:
        sys.exit(f"ERROR: Could not find fonts in archive: {needed}")

    return _FONT_CACHE


def _register_cmu(pdf: "FPDF", font_dir: Path) -> str:
    """Register all four CMU Serif variants with *pdf*.  Returns the family name."""
    family = "CMUSerif"
    for style, filename in _CMU_FILES.items():
        pdf.add_font(family, style=style, fname=str(font_dir / filename))
    return family


def save_pdf(html: str, dest: Path, source_url: str) -> None:
    """Save *html* as an elegantly typeset PDF in the tradition of Knuth's books."""
    import logging
    import warnings

    from fpdf import FPDF

    # Suppress fontTools subsetting debug messages.  The CMU TTFs include
    # TeX-specific SFNT tables that fontTools cannot subset — but the fonts
    # embed correctly regardless.
    logging.getLogger("fontTools.subset").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore", message=".*NOT subset.*")

    title, text = _extract_readable(html)
    font_dir = _ensure_cmu_fonts()

    pdf = FPDF(unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=_MARGIN_BOT)
    pdf.set_margins(_MARGIN_LR, _MARGIN_TOP, _MARGIN_LR)

    family = _register_cmu(pdf, font_dir)

    # ── Title page ─────────────────────────────────────────────────────
    pdf.add_page()

    if title:
        # Push title down ~40 % from the top for a centred feel.
        pdf.ln(65)

        # Thin decorative rule above title.
        x = _MARGIN_LR
        pdf.set_draw_color(120, 120, 120)
        pdf.set_line_width(0.3)
        pdf.line(x, pdf.get_y(), x + _TEXT_W, pdf.get_y())
        pdf.ln(6)

        # Title — bold, large, centred.
        pdf.set_font(family, style="B", size=_H1_SIZE)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(_TEXT_W, _H1_LEAD * 0.353, text=title, align="C")
        pdf.ln(6)

        # Thin rule below title.
        pdf.line(x, pdf.get_y(), x + _TEXT_W, pdf.get_y())
        pdf.ln(10)

        # Source URL in italic grey — quiet but present.
        pdf.set_font(family, style="I", size=_META_SIZE)
        pdf.set_text_color(110, 110, 110)
        pdf.multi_cell(_TEXT_W, _META_LEAD * 0.353, text=source_url, align="C")
        pdf.set_text_color(0, 0, 0)

    # ── Body pages ─────────────────────────────────────────────────────
    pdf.add_page()

    # Footer: centred page number in the Knuth style (italic, small).
    class _Styled(pdf.__class__):
        """Mixin that adds elegant page footers."""
        _font_family = family
        _meta_size = _META_SIZE

        def footer(self):
            self.set_y(-_MARGIN_BOT + 5)
            self.set_font(self._font_family, style="I", size=self._meta_size)
            self.set_text_color(130, 130, 130)
            # Page numbering starts from the body page (page 2 is "1").
            self.cell(0, 10, text=f"— {self.page_no() - 1} —", align="C")
            self.set_text_color(0, 0, 0)

    pdf.__class__ = _Styled

    pdf.set_font(family, size=_BODY_SIZE)
    line_h = _BODY_LEAD * 0.353  # pt → mm conversion factor

    paragraphs = text.split("\n")
    prev_blank = True  # treat start as "after blank" so first para is not indented

    for para in paragraphs:
        stripped = para.strip()

        # Blank line → paragraph break.
        if not stripped:
            pdf.ln(_PAR_SKIP)
            prev_blank = True
            continue

        # First-line indent (Knuth style: indent continuation paragraphs,
        # not the first paragraph after a heading / blank line).
        if not prev_blank:
            pdf.set_x(_MARGIN_LR + _PAR_INDENT)
            pdf.multi_cell(
                _TEXT_W - _PAR_INDENT, line_h, text=stripped, align="J",
            )
        else:
            pdf.multi_cell(_TEXT_W, line_h, text=stripped, align="J")

        prev_blank = False

    pdf.output(str(dest))


def _slug_from_url(url: str) -> str:
    """Derive a safe filename stem from a URL."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "index"
    stem = Path(path).stem or "page"
    stem = re.sub(r"[^\w\-]", "_", stem)
    return stem[:80] or "page"


def fetch(url: str) -> tuple[str, str]:
    """Fetch *url* and return (html_text, final_url).

    Uses curl_cffi with Chrome TLS fingerprint impersonation to bypass
    Cloudflare and similar bot-detection systems.  Falls back to Wayback
    Machine and Google Cache when the primary fetch fails.

    Raises SystemExit with an actionable message on network errors.
    """
    from curl_cffi import requests as cffi_requests
    from curl_cffi import CurlError

    # Minimum bytes for a page to count as real content (not an error page).
    _MIN_USEFUL_BYTES = 1024  # 1 KB — any real article is larger

    def _cffi_get(target_url: str) -> cffi_requests.Response:
        """GET with Chrome TLS impersonation — bypasses Cloudflare."""
        return cffi_requests.get(
            target_url,
            impersonate="chrome",
            timeout=TIMEOUT,
            allow_redirects=True,
        )

    def _httpx_get(target_url: str) -> httpx.Response:
        """Plain httpx GET — for archive services that don't need TLS tricks."""
        with httpx.Client(
            follow_redirects=True,
            timeout=TIMEOUT,
            verify=_SSL_CTX,
        ) as client:
            resp = client.get(target_url)
            resp.raise_for_status()
            return resp

    # --- Attempt 1: curl_cffi with Chrome impersonation ---
    try:
        resp = _cffi_get(url)
        status = resp.status_code
        if status < 400:
            content = resp.content[:MAX_BYTES]
            encoding = resp.encoding or "utf-8"
            return content.decode(encoding, errors="replace"), str(resp.url)
        # Only fall through to caches for bot-block status codes.
        if status in (401, 403, 451):
            print(
                f"Direct fetch returned {status}. Trying fallbacks …",
                file=sys.stderr,
            )
        else:
            sys.exit(
                f"ERROR: HTTP {status} from {url}\n"
                "Check the URL or try again later."
            )
    except CurlError as exc:
        sys.exit(f"ERROR: Could not reach {url} — {exc}\nCheck your network connection.")

    # --- Attempt 2: Wayback Machine (most reliable archive) ---
    wayback_url = f"https://web.archive.org/web/{url}"
    try:
        resp = _httpx_get(wayback_url)
        content = resp.content[:MAX_BYTES]
        if len(content) > _MIN_USEFUL_BYTES:
            encoding = resp.encoding or "utf-8"
            print("Fetched from Wayback Machine.", file=sys.stderr)
            return content.decode(encoding, errors="replace"), str(resp.url)
        print("Wayback Machine returned too little content.", file=sys.stderr)
    except (httpx.HTTPStatusError, httpx.RequestError):
        print("Wayback Machine unavailable. Trying Google Cache …", file=sys.stderr)

    # --- Attempt 3: Google Cache (often blocked, last resort) ---
    cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{url}"
    try:
        resp = _cffi_get(cache_url)
        if resp.status_code < 400:
            content = resp.content[:MAX_BYTES]
            encoding = resp.encoding or "utf-8"
            html_text = content.decode(encoding, errors="replace")
            if len(content) > _MIN_USEFUL_BYTES and "trouble accessing Google" not in html_text:
                print("Fetched from Google Cache.", file=sys.stderr)
                return html_text, str(resp.url)
        print("Google Cache unavailable.", file=sys.stderr)
    except CurlError:
        pass

    sys.exit(
        f"ERROR: Could not fetch {url} — blocked by the site "
        "and no cached version found in Wayback Machine or Google Cache."
    )


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
        dest = Path("/tmp") / f"{slug}.{fmt}"

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
