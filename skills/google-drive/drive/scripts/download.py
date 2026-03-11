# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "google-api-python-client",
#     "google-auth",
#     "google-auth-httplib2",
#     "keyring",
# ]
# ///
"""Download or export a Google Drive file with inline comments.

Usage:
    uv run download.py --file-id ID [--format FMT] [--output-dir DIR]
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from auth import get_drive_service
from contracts import precondition, ContractViolationError

# Google Workspace MIME types that require export
GOOGLE_MIME_TYPES = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
    "application/vnd.google-apps.drawing",
}

# Format → export MIME type mapping
EXPORT_FORMATS = {
    # Documents
    "md": "text/markdown",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
    "html": "text/html",
    "rtf": "application/rtf",
    "odt": "application/vnd.oasis.opendocument.text",
    "epub": "application/epub+zip",
    # Spreadsheets
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ods": "application/vnd.oasis.opendocument.spreadsheet",
    "tsv": "text/tab-separated-values",
    # Presentations
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "odp": "application/vnd.oasis.opendocument.presentation",
    # Drawings
    "png": "image/png",
    "svg": "image/svg+xml",
    "jpg": "image/jpeg",
}

FORMAT_EXTENSIONS = {v: k for k, v in EXPORT_FORMATS.items()}


def _fetch_comments(service, file_id: str) -> list[dict]:
    """Fetch all comments and replies for a file."""
    try:
        result = service.comments().list(
            fileId=file_id,
            fields="comments(id,author(displayName,emailAddress),content,createdTime,resolved,quotedFileContent,replies(id,author(displayName,emailAddress),content,createdTime))",
            includeDeleted=False,
            pageSize=100,
        ).execute()
        return result.get("comments", [])
    except Exception:
        return []


def _format_comments_markdown(comments: list[dict]) -> str:
    """Format comments as a Markdown section."""
    if not comments:
        return ""

    lines = ["\n\n---\n\n## Comments & Discussions\n"]
    for c in comments:
        author = c.get("author", {}).get("displayName", "Unknown")
        date = c.get("createdTime", "")[:10]
        status = "resolved" if c.get("resolved") else "open"
        content = c.get("content", "")
        anchor = c.get("quotedFileContent", {}).get("value", "")

        lines.append(f"\n### Comment by {author} ({date}) [{status}]")
        if anchor:
            lines.append(f'\n> Anchor: "{anchor}"')
        lines.append(f"\n{content}")

        for r in c.get("replies", []):
            r_author = r.get("author", {}).get("displayName", "Unknown")
            r_date = r.get("createdTime", "")[:10]
            r_content = r.get("content", "")
            lines.append(f"\n- **Reply by {r_author}** ({r_date}): {r_content}")

    return "\n".join(lines)


def _print_comments_stdout(comments: list[dict]) -> None:
    """Print comments to stdout for binary format downloads."""
    if not comments:
        return

    print("\n=== Document Comments & Discussions ===\n")
    for c in comments:
        author = c.get("author", {}).get("displayName", "Unknown")
        date = c.get("createdTime", "")[:10]
        status = "RESOLVED" if c.get("resolved") else "OPEN"
        content = c.get("content", "")
        anchor = c.get("quotedFileContent", {}).get("value", "")

        print(f"[{status}] {author} ({date}):")
        if anchor:
            print(f'  Anchor: "{anchor}"')
        print(f"  {content}")

        for r in c.get("replies", []):
            r_author = r.get("author", {}).get("displayName", "Unknown")
            r_date = r.get("createdTime", "")[:10]
            r_content = r.get("content", "")
            print(f"    ↳ {r_author} ({r_date}): {r_content}")
        print()


@precondition(lambda file_id, **kw: file_id and file_id.strip(), "file_id must be non-empty")
def download_file(
    file_id: str,
    fmt: str | None = None,
    output_dir: str = ".",
) -> dict:
    """Download or export a Google Drive file with inline comments.

    Args:
        file_id: Google Drive file ID.
        fmt: Export format (md, pdf, docx, csv, etc.). Auto-detected if None.
        output_dir: Directory to save the file.

    Returns:
        Dict with file metadata and download info.
    """
    service = get_drive_service()

    # Get file metadata
    meta = service.files().get(
        fileId=file_id,
        fields="id, name, mimeType, size, modifiedTime",
        supportsAllDrives=True,
    ).execute()

    name = meta["name"]
    mime = meta["mimeType"]
    is_google = mime in GOOGLE_MIME_TYPES

    # Fetch comments
    comments = _fetch_comments(service, file_id)

    if is_google:
        # Export Google Workspace files
        fmt = fmt or "md"
        export_mime = EXPORT_FORMATS.get(fmt, EXPORT_FORMATS.get("pdf"))
        content = service.files().export_media(
            fileId=file_id, mimeType=export_mime
        ).execute()
        ext = fmt
    else:
        # Download regular files
        content = service.files().get_media(fileId=file_id).execute()
        ext = name.rsplit(".", 1)[-1] if "." in name else "bin"

    # Build output filename
    base_name = name.rsplit(".", 1)[0] if "." in name else name
    out_name = f"{base_name}.{ext}"
    out_path = os.path.join(output_dir, out_name)

    # Handle inline comments for markdown
    if fmt == "md" and comments:
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        content += _format_comments_markdown(comments)
        content = content.encode("utf-8")

    # Write file
    os.makedirs(output_dir, exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(content if isinstance(content, bytes) else content.encode("utf-8"))

    # For non-markdown formats, print comments to stdout
    if fmt != "md" and comments:
        _print_comments_stdout(comments)

    print(f"File saved to: {out_path}")

    return {
        "name": name,
        "id": file_id,
        "format": fmt or ext,
        "path": out_path,
        "comments_count": len(comments),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Google Drive file")
    parser.add_argument("--file-id", required=True, help="File ID to download")
    parser.add_argument("--format", dest="fmt", help="Export format (md, pdf, docx, csv, etc.)")
    parser.add_argument("--output-dir", default=".", help="Output directory")
    args = parser.parse_args()

    download_file(file_id=args.file_id, fmt=args.fmt, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
