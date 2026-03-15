# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Parse an Obsidian vault into a visualization-datascape JSON config.

Data pipe: reads an Obsidian vault directory, outputs JSON config to stdout.
Every .md note becomes a vault. Internal [[links]] become connections.
Temporal notes (YYYY-MM-DD filenames) automatically get synthetic year/month
vaults with hierarchical and chronological prev/next connections.

Usage:
    uv run --no-config obsidian_to_datascape.py /path/to/vault > config.json
    uv run --no-config obsidian_to_datascape.py /path/to/vault -o config.json
"""
from __future__ import annotations

import base64
import hashlib
import html as html_mod
import json
import os
import re
import sys
import argparse
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import contracts

# ── Regex patterns ──────────────────────────────────────────────────
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
EMBED_RE = re.compile(r"!\[\[([^\]]+)\]\]")
MD_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
MD_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")
EXT_URL_RE = re.compile(r"https?://[^\s\)\]>\"]+")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
TAG_RE = re.compile(r"(?:^|\s)#([a-zA-Z0-9/_-]+)")
# Matches YYYY-MM-DD anywhere in stem (e.g. "2025-01-15" or "diary 2025-01-15")
DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

MONTH_NAMES = [
    "", "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
]

# 12 distinct folder colors — wraps for >12 folders
FOLDER_COLORS = [
    "0x00ff66", "0x00ccff", "0xff6600", "0xff00ff",
    "0xffff00", "0x66ff33", "0xff3366", "0x33cccc",
    "0xcc99ff", "0xff9933", "0x00ff99", "0x6699ff",
]
# Temporal vaults get a distinctive color
TEMPORAL_YEAR_COLOR = "0xffffff"   # white — years are structural anchors
TEMPORAL_MONTH_COLOR = "0x99ccff"  # light blue — months are time containers

# Max image size for base64 embedding (512KB — keeps HTML under control)
MAX_IMAGE_BYTES = 512_000

IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"})
MIME_MAP = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".svg": "image/svg+xml", ".webp": "image/webp",
}


# ── Helpers ──────────────────────────────────────────────────────────

def _stable_id(text: str) -> str:
    """Deterministic short ID from any string."""
    return hashlib.md5(text.encode()).hexdigest()[:10]


def _resolve_wikilink(
    target: str,
    stem_map: dict[str, Path],
    rel_map: dict[str, Path],
) -> Path | None:
    """Resolve a [[target]] to a note Path."""
    target = target.split("#")[0].split("|")[0].strip()
    if not target:
        return None
    if target in stem_map:
        return stem_map[target]
    if target in rel_map:
        return rel_map[target]
    t2 = target.removesuffix(".md")
    if t2 in stem_map:
        return stem_map[t2]
    return None


def _find_image(ref: str, note_dir: Path, vault_root: Path) -> Path | None:
    """Resolve an image reference to an actual file."""
    ref = ref.strip()
    for base in (note_dir, vault_root, note_dir / "images"):
        candidate = base / ref
        if candidate.exists():
            return candidate
    fname = Path(ref).name
    for base in (note_dir, note_dir / "images", vault_root):
        candidate = base / fname
        if candidate.exists():
            return candidate
    # Last resort: recursive search
    for candidate in vault_root.rglob(fname):
        if ".obsidian" not in str(candidate):
            return candidate
    return None


def _image_to_data_uri(img_path: Path) -> str | None:
    """Convert a local image to a data: URI, or None if too large/unsupported."""
    mime = MIME_MAP.get(img_path.suffix.lower())
    if not mime:
        return None
    try:
        data = img_path.read_bytes()
        if len(data) > MAX_IMAGE_BYTES:
            return None
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return None


def _extract_date(stem: str) -> date | None:
    """Extract a YYYY-MM-DD date from a note stem, or None."""
    m = DATE_RE.search(stem)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _build_note_html(
    name: str,
    rel: Path,
    content: str,
    note_dir: Path,
    vault_root: Path,
) -> str:
    """Build the HTML panel content for a single note vault."""
    headings = HEADING_RE.findall(content)
    embeds = EMBED_RE.findall(content)
    md_images = MD_IMG_RE.findall(content)
    ext_urls = list(set(EXT_URL_RE.findall(content)))
    tags = list(set(TAG_RE.findall(content)))
    wikilinks = WIKILINK_RE.findall(content)

    h: list[str] = []

    # Title
    h.append(f'<div class="pt">{html_mod.escape(name)}</div>')

    # Folder path subtitle
    folder_str = str(rel.parent)
    if folder_str != ".":
        h.append(f'<div class="ps">{html_mod.escape(folder_str)}</div>')

    # Tags
    if tags:
        tag_str = " ".join(f"#{t}" for t in sorted(tags)[:8])
        h.append(f'<div class="ps" style="color:#0f8">{html_mod.escape(tag_str)}</div>')

    # Structure (headings)
    if headings:
        h.append('<div class="ph">Structure</div>')
        for level, text in headings[:12]:
            indent = "&nbsp;" * (len(level) - 1) * 2
            h.append(f'<div class="pd">{indent}{html_mod.escape(text.strip())}</div>')

    # Content preview
    lines = [
        l.strip() for l in content.split("\n")
        if l.strip() and not l.strip().startswith("#") and not l.strip().startswith("---")
    ]
    preview = []
    for l in lines:
        clean = WIKILINK_RE.sub("", EMBED_RE.sub("", l)).strip()
        if clean and len(clean) > 3:
            preview.append(clean)
    if preview:
        h.append('<div class="ph">Content Preview</div>')
        for l in preview[:8]:
            h.append(f'<div class="pd">{html_mod.escape(l[:200])}</div>')

    # Embedded images
    data_uris: list[str] = []
    for embed in embeds:
        embed_name = embed.split("|")[0].strip()
        img_path = _find_image(embed_name, note_dir, vault_root)
        if img_path and img_path.suffix.lower() in IMAGE_EXTS:
            uri = _image_to_data_uri(img_path)
            if uri:
                data_uris.append(uri)
    for _, src in md_images:
        if not src.startswith("http"):
            img_path = _find_image(src, note_dir, vault_root)
            if img_path:
                uri = _image_to_data_uri(img_path)
                if uri:
                    data_uris.append(uri)
    if data_uris:
        h.append('<div class="ph">Images</div>')
        if len(data_uris) > 1:
            h.append('<div class="pi-deck">')
            for uri in data_uris[:6]:
                h.append(f'<img src="{uri}">')
            h.append('</div>')
        else:
            h.append(f'<img class="pi" src="{data_uris[0]}">')

    # PDF references
    pdf_refs = [e.split("|")[0].strip() for e in embeds if e.lower().endswith(".pdf")]
    if pdf_refs:
        h.append('<div class="ph">PDFs</div>')
        for pdf_name in pdf_refs[:4]:
            h.append(f'<div class="pd">\U0001f4c4 {html_mod.escape(pdf_name)}</div>')

    # Internal links (display names)
    link_names = []
    for wl in wikilinks:
        display = wl.split("|")[-1].strip()
        if display:
            link_names.append(display)
    if link_names:
        h.append('<div class="ph">Linked Notes</div>')
        for ln in sorted(set(link_names))[:12]:
            h.append(f'<div class="pd">\U0001f517 {html_mod.escape(ln)}</div>')

    # External links
    if ext_urls:
        h.append('<div class="ph">External Links</div>')
        for url in ext_urls[:8]:
            display = url[:60] + ("\u2026" if len(url) > 60 else "")
            safe_url = html_mod.escape(url)
            h.append(f'<div class="pd"><a href="{safe_url}" target="_blank" style="color:#0cf">{html_mod.escape(display)}</a></div>')

    # Stats footer
    word_count = len(content.split())
    h.append(f'<div class="pw">{word_count} words \u00b7 {len(wikilinks)} links \u00b7 {len(embeds)} embeds</div>')

    return "\n".join(h)


# ── Main entry point ─────────────────────────────────────────────────

@contracts.precondition(
    lambda vault_path: Path(vault_path).is_dir(),
    "vault_path must be an existing directory",
)
def parse_vault(vault_path: str) -> dict:
    """Parse an Obsidian vault directory into a datascape JSON config.

    Returns a dict ready for json.dumps() / generate.py consumption.
    """
    vault_root = Path(vault_path)

    # Collect all .md files, excluding .obsidian
    md_files = sorted(
        p for p in vault_root.rglob("*.md")
        if ".obsidian" not in p.parts
    )

    if not md_files:
        raise contracts.ContractViolationError(
            f"No .md files found in {vault_path} (excluding .obsidian)",
            kind="precondition",
        )

    # ── Build stem/rel lookup maps ──
    stem_map: dict[str, Path] = {}
    rel_map: dict[str, Path] = {}
    for p in md_files:
        stem_map[p.stem] = p
        rel = p.relative_to(vault_root).with_suffix("")
        rel_map[str(rel)] = p

    # ── Assign IDs and colors ──
    id_map: dict[str, str] = {}  # str(path) → vault ID
    folder_colors: dict[str, str] = {}
    color_idx = 0

    for p in md_files:
        rel = str(p.relative_to(vault_root))
        id_map[str(p)] = _stable_id(rel)

    def get_color(p: Path) -> str:
        nonlocal color_idx
        rel = p.relative_to(vault_root)
        folder = rel.parts[0] if len(rel.parts) > 1 else "__root__"
        if folder not in folder_colors:
            folder_colors[folder] = FOLDER_COLORS[color_idx % len(FOLDER_COLORS)]
            color_idx += 1
        return folder_colors[folder]

    # ── Parse notes into vaults ──
    vaults: list[dict] = []
    connections: list[dict] = []
    seen_conn: set[tuple[str, str]] = set()
    dated_notes: list[tuple[date, str]] = []  # (date, vault_id) for temporal inference

    def add_conn(from_id: str, to_id: str) -> None:
        pair = tuple(sorted([from_id, to_id]))
        if pair not in seen_conn and from_id != to_id:
            seen_conn.add(pair)
            connections.append({"from": from_id, "to": to_id})

    total_words = 0

    for p in md_files:
        vid = id_map[str(p)]
        rel = p.relative_to(vault_root)
        name = p.stem

        try:
            content = p.read_text(encoding="utf-8")
        except Exception:
            content = "(unreadable)"

        total_words += len(content.split())

        # Build HTML panel
        vault_html = _build_note_html(name, rel, content, p.parent, vault_root)

        vaults.append({
            "id": vid,
            "name": name.upper()[:30],
            "html": vault_html,
            "color": get_color(p),
        })

        # Extract wikilink connections
        for wl in WIKILINK_RE.findall(content):
            target = _resolve_wikilink(wl, stem_map, rel_map)
            if target and str(target) in id_map:
                add_conn(vid, id_map[str(target)])

        # Check for temporal date in stem
        d = _extract_date(name)
        if d:
            dated_notes.append((d, vid))

    # ── Temporal inference ──────────────────────────────────────────
    # Group dated notes by (year, month)
    if dated_notes:
        dated_notes.sort(key=lambda x: x[0])

        # Discover which year/months we need
        year_months: dict[int, set[int]] = {}  # year → {month, ...}
        for d, _ in dated_notes:
            year_months.setdefault(d.year, set()).add(d.month)

        # Create month vaults
        month_ids: dict[tuple[int, int], str] = {}
        for year, months in sorted(year_months.items()):
            for month in sorted(months):
                mid = _stable_id(f"__month__{year}-{month:02d}")
                month_name = f"{MONTH_NAMES[month]} {year}"
                month_ids[(year, month)] = mid
                # Count notes in this month
                notes_in_month = [
                    vid for d, vid in dated_notes
                    if d.year == year and d.month == month
                ]
                vaults.append({
                    "id": mid,
                    "name": month_name,
                    "html": (
                        f'<div class="pt">{month_name}</div>'
                        f'<div class="ps">Temporal container \u00b7 {len(notes_in_month)} notes</div>'
                        f'<div class="ph">Date Range</div>'
                        f'<div class="pd">{year}-{month:02d}-01 \u2192 {year}-{month:02d}-28+</div>'
                    ),
                    "color": TEMPORAL_MONTH_COLOR,
                })

        # Create year vaults
        year_ids: dict[int, str] = {}
        for year in sorted(year_months.keys()):
            yid = _stable_id(f"__year__{year}")
            year_ids[year] = yid
            month_count = len(year_months[year])
            note_count = sum(1 for d, _ in dated_notes if d.year == year)
            vaults.append({
                "id": yid,
                "name": str(year),
                "html": (
                    f'<div class="pt">{year}</div>'
                    f'<div class="ps">Year container \u00b7 {month_count} months \u00b7 {note_count} notes</div>'
                ),
                "color": TEMPORAL_YEAR_COLOR,
            })

        # Link: dated notes → their month
        for d, vid in dated_notes:
            mid = month_ids[(d.year, d.month)]
            add_conn(vid, mid)

        # Link: months → their year
        for (year, _month), mid in month_ids.items():
            yid = year_ids[year]
            add_conn(mid, yid)

        # Chronological prev/next for dated notes
        for i in range(len(dated_notes) - 1):
            _, vid_a = dated_notes[i]
            _, vid_b = dated_notes[i + 1]
            add_conn(vid_a, vid_b)

        # Chronological prev/next for month vaults
        sorted_months = sorted(month_ids.keys())
        for i in range(len(sorted_months) - 1):
            add_conn(month_ids[sorted_months[i]], month_ids[sorted_months[i + 1]])

        # Chronological prev/next for year vaults
        sorted_years = sorted(year_ids.keys())
        for i in range(len(sorted_years) - 1):
            add_conn(year_ids[sorted_years[i]], year_ids[sorted_years[i + 1]])

    # ── Glyphs ──
    glyphs: set[str] = set()
    for p in md_files:
        rel = p.relative_to(vault_root)
        for part in rel.parts[:-1]:
            clean = re.sub(r"^\d+-\d+\s*", "", part)[:14]
            if clean:
                glyphs.add(clean)
        stem = p.stem[:14]
        if len(stem) > 3:
            glyphs.add(stem)
    glyphs.update(["OBSIDIAN", "VAULT", "NOTES", "LINKS", "GRAPH"])
    glyph_list = sorted(glyphs)[:24]

    # ── Stats ──
    media_count = sum(
        1 for v in vaults
        if "pi-deck" in v["html"] or 'class="pi"' in v["html"]
    )
    stats = [
        {"label": "data vaults", "value": str(len(vaults))},
        {"label": "connections", "value": str(len(connections))},
        {"label": "total words", "value": f"{total_words:,}"},
        {"label": "media files", "value": str(media_count)},
    ]

    # Vault name for title
    vault_name = vault_root.name
    return {
        "title": f"{vault_name.upper()} KNOWLEDGE GRAPH",
        "subtitle": f"Obsidian vault \u00b7 {len(md_files)} notes visualized",
        "stats": stats,
        "vaults": vaults,
        "glyphs": glyph_list,
        "connections": connections,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse Obsidian vault into datascape JSON config"
    )
    parser.add_argument("vault_path", help="Path to Obsidian vault directory")
    parser.add_argument("-o", "--output", help="Output JSON file (default: stdout)")
    args = parser.parse_args()

    config = parse_vault(args.vault_path)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"Config written to {args.output}", file=sys.stderr)
    else:
        json.dump(config, sys.stdout, ensure_ascii=False, indent=2)

    print(f"  Vaults: {len(config['vaults'])}", file=sys.stderr)
    print(f"  Connections: {len(config['connections'])}", file=sys.stderr)


if __name__ == "__main__":
    main()
