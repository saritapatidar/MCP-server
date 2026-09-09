"""
Diff and line analysis for GitHub Pull Request patches.

This module parses the unified diff format returned by GitHub's API for
each changed file (the `patch` string on a PullRequestFile) into
structured hunks and lines, and identifies which lines are candidates
for review comments.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class LineType(str, Enum):
    """The type of a single line within a diff hunk."""

    ADDED = "added"
    REMOVED = "removed"
    CONTEXT = "context"


@dataclass
class DiffLine:
    """A single line within a diff hunk."""

    content: str
    line_type: LineType
    new_lineno: int | None
    old_lineno: int | None


@dataclass
class DiffHunk:
    """A contiguous block of changes within a file's diff."""

    header: str
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[DiffLine] = field(default_factory=list)


_HUNK_HEADER_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@"
)


def parse_patch(patch: str) -> list[DiffHunk]:
    """
    Parse a unified diff patch string into structured hunks.

    Args:
        patch: The `patch` text for a single file, as returned by
            GitHub's Pull Request files API. This does not include
            file-level `---`/`+++` headers, only hunks.

    Returns:
        A list of parsed diff hunks, in order of appearance.

    Raises:
        ValueError: If the patch does not contain any valid hunk header.
    """
    hunks: list[DiffHunk] = []
    current_hunk: DiffHunk | None = None
    old_lineno = 0
    new_lineno = 0

    for raw_line in patch.splitlines():
        header_match = _HUNK_HEADER_RE.match(raw_line)

        if header_match:
            old_start = int(header_match.group("old_start"))
            new_start = int(header_match.group("new_start"))
            old_count = int(header_match.group("old_count") or 1)
            new_count = int(header_match.group("new_count") or 1)

            current_hunk = DiffHunk(
                header=raw_line,
                old_start=old_start,
                old_count=old_count,
                new_start=new_start,
                new_count=new_count,
            )
            hunks.append(current_hunk)

            old_lineno = old_start
            new_lineno = new_start
            continue

        if current_hunk is None:
            # Lines before the first hunk header aren't part of any
            # hunk (GitHub's per-file patch shouldn't normally have
            # any, but we guard against it defensively).
            continue

        if raw_line.startswith("\\"):
            # e.g. "\ No newline at end of file" -- not a real line.
            continue

        if raw_line.startswith("+"):
            current_hunk.lines.append(
                DiffLine(
                    content=raw_line[1:],
                    line_type=LineType.ADDED,
                    new_lineno=new_lineno,
                    old_lineno=None,
                )
            )
            new_lineno += 1
        elif raw_line.startswith("-"):
            current_hunk.lines.append(
                DiffLine(
                    content=raw_line[1:],
                    line_type=LineType.REMOVED,
                    new_lineno=None,
                    old_lineno=old_lineno,
                )
            )
            old_lineno += 1
        else:
            content = raw_line[1:] if raw_line.startswith(" ") else raw_line
            current_hunk.lines.append(
                DiffLine(
                    content=content,
                    line_type=LineType.CONTEXT,
                    new_lineno=new_lineno,
                    old_lineno=old_lineno,
                )
            )
            old_lineno += 1
            new_lineno += 1

    if not hunks:
        raise ValueError("Patch does not contain any valid diff hunks.")

    return hunks


def extract_added_source(patch: str) -> str:
    """
    Reconstruct just the added lines of a patch as plain source text.

    Used by the optional static analyzers (app/analyzers/*), which
    scan the added-lines snippet in isolation since the pipeline does
    not check out the full repository.

    Args:
        patch: The unified diff patch for a file.

    Returns:
        The added lines joined with newlines, in order. Empty string
        if the patch has no valid hunks or no added lines.
    """
    try:
        hunks = parse_patch(patch)
    except ValueError:
        return ""

    return "\n".join(
        line.content
        for hunk in hunks
        for line in hunk.lines
        if line.line_type is LineType.ADDED
    )


def get_reviewable_lines(hunks: list[DiffHunk]) -> list[DiffLine]:
    """
    Get the lines that are candidates for review comments.

    Only added lines are reviewable: GitHub's inline review comments
    attach to a line as it exists in the new version of the file, and
    reviewing removed code that no longer exists provides little
    value. Removed and context lines are still available on each hunk
    for building surrounding context.

    Args:
        hunks: Parsed diff hunks for a file.

    Returns:
        The added lines across all hunks, in the order they appear.
    """
    return [
        line
        for hunk in hunks
        for line in hunk.lines
        if line.line_type is LineType.ADDED
    ]
