"""
Context building for LLM-based code review.

This module combines a diff hunk with file-level metadata into a
self-contained context block that gives the LLM enough information to
review the changed lines accurately, without sending the entire
repository.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from app.review.line_analyzer import DiffHunk, LineType

_EXTENSION_LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".php": "php",
    ".sh": "bash",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".sql": "sql",
}


def detect_language(file_path: str) -> str:
    """
    Guess a file's programming language from its extension.

    Args:
        file_path: Path of the file within the repository.

    Returns:
        A lowercase language name, or "text" if the extension is not
        recognized.
    """
    _, extension = os.path.splitext(file_path)
    return _EXTENSION_LANGUAGE_MAP.get(extension.lower(), "text")


@dataclass
class HunkContext:
    """A ready-to-send review context block for a single diff hunk."""

    file_path: str
    language: str
    hunk_header: str
    code_block: str
    added_line_numbers: list[int] = field(default_factory=list)

    def to_prompt_section(self) -> str:
        """
        Render this context as a Markdown section for an LLM prompt.

        Returns:
            A fenced code block, labeled with the file path and hunk
            header, ready to be embedded in a review prompt.
        """
        return (
            f"File: {self.file_path}\n"
            f"Hunk: {self.hunk_header}\n"
            f"```{self.language}\n"
            f"{self.code_block}\n"
            f"```"
        )


def build_hunk_context(file_path: str, hunk: DiffHunk) -> HunkContext:
    """
    Build a review context block for a single diff hunk.

    The context includes every line in the hunk -- added, removed, and
    context lines -- rendered together with the new-file line numbers,
    so the LLM sees each change in place rather than as an isolated
    snippet.

    Args:
        file_path: Path of the file the hunk belongs to.
        hunk: A parsed diff hunk.

    Returns:
        A HunkContext ready to be passed to the LLM layer.
    """
    code_lines: list[str] = []
    added_line_numbers: list[int] = []

    for line in hunk.lines:
        if line.line_type is LineType.REMOVED:
            marker = "-"
            lineno_display = ""
        elif line.line_type is LineType.ADDED:
            marker = "+"
            lineno_display = str(line.new_lineno)
            added_line_numbers.append(line.new_lineno)
        else:
            marker = " "
            lineno_display = str(line.new_lineno)

        code_lines.append(f"{lineno_display:>5} {marker} {line.content}")

    return HunkContext(
        file_path=file_path,
        language=detect_language(file_path),
        hunk_header=hunk.header,
        code_block="\n".join(code_lines),
        added_line_numbers=added_line_numbers,
    )


def build_file_contexts(file_path: str, hunks: list[DiffHunk]) -> list[HunkContext]:
    """
    Build review context blocks for every hunk in a file's diff.

    Args:
        file_path: Path of the file the hunks belong to.
        hunks: Parsed diff hunks for the file.

    Returns:
        One HunkContext per hunk that contains at least one added
        line. Hunks with no added lines (pure deletions) are skipped
        since there is nothing new to review.
    """
    contexts = [build_hunk_context(file_path, hunk) for hunk in hunks]
    return [context for context in contexts if context.added_line_numbers]
