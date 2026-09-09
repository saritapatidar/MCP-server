"""
GitHub Pull Request review posting.

Takes generated review comments and posts them to a Pull Request as a
single GitHub review, using the line-based inline comment API (path +
line + side) rather than the legacy diff-position API, so comments
land on the correct line even as a PR's diff context shifts.
"""

from __future__ import annotations

from github.PullRequest import PullRequest

from app.core.logging import get_logger
from app.review.comment_generator import ReviewComment

logger = get_logger(__name__)

# A hard ceiling so a noisy diff can never produce an overwhelming
# wall of comments, even if validation lets more than this through.
MAX_COMMENTS_PER_REVIEW = 50


def post_review(
    pr: PullRequest,
    comments: list[ReviewComment],
    summary: str | None = None,
) -> None:
    """
    Post review comments to a Pull Request as a single GitHub review.

    Args:
        pr: The Pull Request to review.
        comments: Validated, generated review comments to post.
        summary: Optional top-level review body. Defaults to a short
            auto-generated summary based on the number of comments.

    Raises:
        ValueError: If comments is empty -- there is nothing to post.
    """
    if not comments:
        raise ValueError("post_review requires at least one comment.")

    if len(comments) > MAX_COMMENTS_PER_REVIEW:
        logger.warning(
            "Truncating review from %d to %d comments to avoid an overwhelming review.",
            len(comments),
            MAX_COMMENTS_PER_REVIEW,
        )
        comments = comments[:MAX_COMMENTS_PER_REVIEW]

    commit = list(pr.get_commits())[-1]

    review_body = summary or (
        f"AI code review found {len(comments)} issue"
        f"{'s' if len(comments) != 1 else ''} worth a look."
    )

    payload = [
        {
            "path": comment.path,
            "line": comment.line,
            "side": comment.side,
            "body": comment.body,
        }
        for comment in comments
    ]

    pr.create_review(commit=commit, body=review_body, event="COMMENT", comments=payload)
    logger.info("Posted review with %d comment(s) to PR #%d.", len(comments), pr.number)
