"""
Data models for AI code review results.

These structures represent a single review finding as it flows through
the pipeline: from the LLM's raw output, through validation, to the
comment that ultimately gets posted on GitHub.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    """How serious a finding is."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Category(str, Enum):
    """What kind of issue a finding represents."""

    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    LOGIC = "logic"
    MAINTAINABILITY = "maintainability"
    TESTING = "testing"
    ERROR_HANDLING = "error_handling"


@dataclass
class Finding:
    """A single potential issue identified in a changed line of code."""

    file_path: str
    line_number: int
    severity: Severity
    category: Category
    title: str
    description: str
    suggestion: str
    confidence: float
    side: str = "RIGHT"

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"confidence must be between 0.0 and 1.0, got {self.confidence}"
            )

    def to_comment_body(self) -> str:
        """
        Render this finding as a developer-friendly Markdown comment body.

        Returns:
            A Markdown string covering what the problem is, why it
            matters, and how to fix it -- suitable for posting directly
            as a GitHub inline review comment.
        """
        severity_label = self.severity.value.upper()
        category_label = self.category.value.replace("_", " ").title()

        return (
            f"**[{severity_label}] {self.title}** _({category_label})_\n\n"
            f"{self.description}\n\n"
            f"**Suggestion:** {self.suggestion}"
        )
