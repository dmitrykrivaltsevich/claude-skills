# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "google-api-python-client",
#     "google-auth",
#     "google-auth-httplib2",
#     "keyring",
# ]
# ///
"""List, add, and reply to comments on Google Drive files.

Usage:
    uv run comments.py list  --file-id ID
    uv run comments.py add   --file-id ID --content TEXT
    uv run comments.py reply --file-id ID --comment-id CID --content TEXT
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from auth import get_drive_service
from contracts import precondition, ContractViolationError


@precondition(lambda file_id, **kw: file_id and file_id.strip(), "file_id must be non-empty")
def list_comments(file_id: str) -> list[dict]:
    """List all comments and replies on a file.

    Args:
        file_id: Google Drive file ID.

    Returns:
        List of comment dicts including replies.
    """
    service = get_drive_service()

    result = service.comments().list(
        fileId=file_id,
        fields="comments(commentId,author(displayName,emailAddress),content,createdTime,resolved,quotedFileContent,replies(author(displayName,emailAddress),content,createdTime,replyId))",
        includeDeleted=False,
        pageSize=100,
    ).execute()

    comments = result.get("comments", [])
    for c in comments:
        author = c.get("author", {}).get("displayName", "Unknown")
        status = "resolved" if c.get("resolved") else "open"
        print(f"[{status}] {author}: {c.get('content', '')}")
        for r in c.get("replies", []):
            r_author = r.get("author", {}).get("displayName", "Unknown")
            print(f"    ↳ {r_author}: {r.get('content', '')}")

    return comments


@precondition(lambda file_id, **kw: file_id and file_id.strip(), "file_id must be non-empty")
@precondition(lambda file_id, content, **kw: content and content.strip(), "content must be non-empty")
def add_comment(file_id: str, content: str) -> dict:
    """Add a comment to a file.

    Args:
        file_id: Google Drive file ID.
        content: Comment text.

    Returns:
        Dict with created comment metadata.
    """
    service = get_drive_service()

    result = service.comments().create(
        fileId=file_id,
        body={"content": content},
        fields="commentId, content, author(displayName), createdTime",
    ).execute()

    print(f"Comment added: {result.get('commentId')}")
    return result


@precondition(lambda file_id, **kw: file_id and file_id.strip(), "file_id must be non-empty")
@precondition(lambda file_id, comment_id, **kw: comment_id and comment_id.strip(), "comment_id must be non-empty")
@precondition(lambda file_id, comment_id, content, **kw: content and content.strip(), "content must be non-empty")
def add_reply(file_id: str, comment_id: str, content: str) -> dict:
    """Add a reply to an existing comment.

    Args:
        file_id: Google Drive file ID.
        comment_id: Comment ID to reply to.
        content: Reply text.

    Returns:
        Dict with created reply metadata.
    """
    service = get_drive_service()

    result = service.replies().create(
        fileId=file_id,
        commentId=comment_id,
        body={"content": content},
        fields="replyId, content, author(displayName), createdTime",
    ).execute()

    print(f"Reply added: {result.get('replyId')}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage file comments")
    sub = parser.add_subparsers(dest="action")

    list_p = sub.add_parser("list", help="List comments")
    list_p.add_argument("--file-id", required=True)

    add_p = sub.add_parser("add", help="Add comment")
    add_p.add_argument("--file-id", required=True)
    add_p.add_argument("--content", required=True)

    reply_p = sub.add_parser("reply", help="Reply to comment")
    reply_p.add_argument("--file-id", required=True)
    reply_p.add_argument("--comment-id", required=True)
    reply_p.add_argument("--content", required=True)

    args = parser.parse_args()

    if args.action == "list":
        list_comments(file_id=args.file_id)
    elif args.action == "add":
        add_comment(file_id=args.file_id, content=args.content)
    elif args.action == "reply":
        add_reply(file_id=args.file_id, comment_id=args.comment_id, content=args.content)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
