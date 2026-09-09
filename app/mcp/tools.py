"""
MCP tool definitions.

These functions are thin wrappers: all business logic lives in
app/review/pipeline.py. This module only translates between an MCP
tool call and the pipeline's result, and turns any failure into a
readable message instead of an unhandled exception reaching the
calling agent.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.review.pipeline import run_review_pipeline

logger = get_logger(__name__)


def review_pull_request(pr_url: str) -> str:
    """
    Review a GitHub Pull Request and post inline review comments.

    Args:
        pr_url: URL of the GitHub Pull Request, e.g.
            "https://github.com/owner/repository/pull/123".

    Returns:
        A human-readable summary of what was reviewed and posted,
        suitable for an AI agent to relay directly to the user.
    """
    try:
        result = run_review_pipeline(pr_url)
    except Exception as exc:  # noqa: BLE001 - surface every failure to the caller
        logger.error("Review failed for %s: %s", pr_url, exc)
        return f"Review failed for {pr_url}: {exc}"

    if result.comments_posted == 0:
        return (
            f"Reviewed {result.files_reviewed} file(s) in {pr_url}. "
            "No issues met the bar for a comment, so nothing was posted."
        )

    return (
        f"Reviewed {result.files_reviewed} file(s) in {pr_url} and posted "
        f"{result.comments_posted} inline review comment(s)."
    )
