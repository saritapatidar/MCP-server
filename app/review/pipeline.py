"""
Review pipeline orchestration.

Wires together GitHub fetching, diff parsing, context building,
optional static analysis, AI review, validation, and comment posting
into the single end-to-end flow. Each step's real implementation
lives in its own module; this file only sequences them, per the
project's separation-of-responsibility requirement.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.analyzers import lint, security
from app.analyzers import tests as test_analyzer
from app.analyzers import types as type_analyzer
from app.core.logging import get_logger
from app.github.diff import get_changed_files, get_file_diff
from app.github.pr import get_pull_request
from app.github.reviews import post_review
from app.llm.client import LLMClient, get_llm_client
from app.models.review import Finding
from app.review.comment_generator import generate_comments
from app.review.context_builder import build_file_contexts
from app.review.line_analyzer import get_reviewable_lines, parse_patch
from app.review.reviewer import review_hunks
from app.review.validator import ValidationConfig, validate_findings

logger = get_logger(__name__)

# Binary/generated/vendored file types are skipped: diffs there are
# rarely meaningful for an AI code reviewer to comment on.
_SKIPPED_FILENAME_SUFFIXES = (
    ".lock",
    ".min.js",
    ".svg",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".woff",
    ".woff2",
)

_STATIC_ANALYZERS = (lint, security, type_analyzer, test_analyzer)


@dataclass
class ReviewResult:
    """Outcome of running the review pipeline on a Pull Request."""

    pr_url: str
    files_reviewed: int
    findings: list[Finding] = field(default_factory=list)
    comments_posted: int = 0
    static_analysis_notes: list[str] = field(default_factory=list)


def run_review_pipeline(
    pr_url: str,
    llm_client: LLMClient | None = None,
    validation_config: ValidationConfig | None = None,
    post_to_github: bool = True,
) -> ReviewResult:
    """
    Run the complete AI code review pipeline against a Pull Request.

    Args:
        pr_url: URL of the GitHub Pull Request to review, e.g.
            "https://github.com/owner/repository/pull/123".
        llm_client: LLM client to use. Defaults to get_llm_client()
            (Claude, configured via .env).
        validation_config: Validation thresholds. Defaults to
            ValidationConfig().
        post_to_github: Whether to actually post the review to
            GitHub. Set to False for a dry run that only reports
            findings.

    Returns:
        A ReviewResult summarizing what was found and posted.
    """
    llm_client = llm_client or get_llm_client()

    logger.info("Starting review for %s", pr_url)
    pr = get_pull_request(pr_url)

    changed_files = get_changed_files(pr)
    logger.info("Fetched %d changed file(s).", len(changed_files))

    all_findings: list[Finding] = []
    valid_line_numbers_by_file: dict[str, set[int]] = {}
    static_notes: list[str] = []
    files_reviewed = 0

    for file in changed_files:
        if _should_skip_file(file.filename):
            continue

        try:
            patch = get_file_diff(file)
        except ValueError:
            logger.info("Skipping %s -- no patch available (binary or renamed).", file.filename)
            continue

        hunks = parse_patch(patch)
        reviewable_lines = get_reviewable_lines(hunks)
        if not reviewable_lines:
            continue

        valid_line_numbers_by_file[file.filename] = {
            line.new_lineno for line in reviewable_lines
        }

        contexts = build_file_contexts(file.filename, hunks)
        if not contexts:
            continue

        static_notes.extend(_run_static_analyzers(file.filename, patch))

        findings = review_hunks(llm_client, file.filename, contexts)
        all_findings.extend(findings)
        files_reviewed += 1

    validated = validate_findings(all_findings, valid_line_numbers_by_file, validation_config)
    comments = generate_comments(validated)

    comments_posted = 0
    if comments and post_to_github:
        post_review(pr, comments)
        comments_posted = len(comments)
    elif comments:
        logger.info("Dry run: %d comment(s) generated but not posted.", len(comments))

    logger.info(
        "Review complete for %s: %d file(s) reviewed, %d finding(s) validated, %d comment(s) posted.",
        pr_url,
        files_reviewed,
        len(validated),
        comments_posted,
    )

    return ReviewResult(
        pr_url=pr_url,
        files_reviewed=files_reviewed,
        findings=validated,
        comments_posted=comments_posted,
        static_analysis_notes=static_notes,
    )


def _should_skip_file(filename: str) -> bool:
    """Decide whether a changed file should be excluded from AI review."""
    return filename.lower().endswith(_SKIPPED_FILENAME_SUFFIXES)


def _run_static_analyzers(filename: str, patch: str) -> list[str]:
    """
    Run every optional static analyzer against a changed file's patch.

    Each analyzer is best-effort: a failure or unavailable tool is
    logged and skipped rather than aborting the review, so the AI
    review always completes even if no static tools are installed.

    Args:
        filename: Path of the changed file.
        patch: The unified diff patch for the file.

    Returns:
        Human-readable notes from any analyzer that produced output.
    """
    notes: list[str] = []
    for analyzer in _STATIC_ANALYZERS:
        try:
            result = analyzer.analyze(filename, patch)
        except Exception as exc:  # noqa: BLE001 - analyzers must never break the pipeline
            logger.warning("Static analyzer %s failed for %s: %s", analyzer.__name__, filename, exc)
            continue
        if result:
            notes.extend(result)
    return notes
