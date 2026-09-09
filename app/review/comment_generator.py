"""
Review comment generation.

Turns validated Finding objects into the payload shape GitHub's Pull
Request review API expects, ready to be posted by
app/github/reviews.py (added in a later step).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.review import Finding, Severity

_SEVERITY_EMOJI = {
    Severity.CRITICAL: "\U0001F534",  # red circle
    Severity.HIGH: "\U0001F7E0",  # orange circle
    Severity.MEDIUM: "\U0001F7E1",  # yellow circle
    Severity.LOW: "\U0001F535",  # blue circle
    Severity.INFO: "\u26AA",  # white circle
}


@dataclass
class ReviewComment:
    """A single inline comment ready to post to a GitHub PR review."""

    path: str
    line: int
    side: str
    body: str


def generate_comment(finding: Finding) -> ReviewComment:
    """
    Convert one validated finding into a ReviewComment.

    Args:
        finding: A finding that has already passed validation.

    Returns:
        A ReviewComment with a developer-friendly Markdown body,
        prefixed with a severity indicator.
    """
    emoji = _SEVERITY_EMOJI.get(finding.severity, "")
    body = f"{emoji} {finding.to_comment_body()}".strip()

    return ReviewComment(
        path=finding.file_path,
        line=finding.line_number,
        side=finding.side,
        body=body,
    )


def generate_comments(findings: list[Finding]) -> list[ReviewComment]:
    """
    Convert a list of validated findings into review comments.

    Args:
        findings: Findings that have already passed validation, in
            app/review/validator.py.

    Returns:
        One ReviewComment per finding, preserving order.
    """
    return [generate_comment(finding) for finding in findings]
