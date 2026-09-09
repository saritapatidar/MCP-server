"""
Finding validation.

The LLM can produce false positives, duplicates, and vague findings.
This module is the gate between raw LLM output (app/review/reviewer.py)
and what actually gets posted to GitHub
(app/review/comment_generator.py) -- nothing reaches GitHub without
passing through validate_findings().
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger
from app.models.review import Finding

logger = get_logger(__name__)

DEFAULT_MIN_CONFIDENCE = 0.6
DEFAULT_MIN_DESCRIPTION_WORDS = 8
DEFAULT_MIN_SUGGESTION_WORDS = 3


@dataclass
class ValidationConfig:
    """Thresholds used when deciding whether to keep a finding."""

    min_confidence: float = DEFAULT_MIN_CONFIDENCE
    min_description_words: int = DEFAULT_MIN_DESCRIPTION_WORDS
    min_suggestion_words: int = DEFAULT_MIN_SUGGESTION_WORDS


def validate_findings(
    findings: list[Finding],
    valid_line_numbers_by_file: dict[str, set[int]],
    config: ValidationConfig | None = None,
) -> list[Finding]:
    """
    Filter raw findings down to the ones worth posting to GitHub.

    Args:
        findings: Raw findings, typically gathered across multiple
            files and hunks.
        valid_line_numbers_by_file: Maps each file path to the set of
            added line numbers that were actually part of the diff.
            Findings that can't be mapped to a real changed line are
            rejected, even if an earlier stage already checked this
            for a single file in isolation.
        config: Validation thresholds. Defaults to ValidationConfig().

    Returns:
        Findings that passed every check and were not duplicates of
        an earlier finding, in the order they were kept.
    """
    config = config or ValidationConfig()

    survivors: list[Finding] = []
    seen_keys: set[tuple[str, int, str]] = set()

    for finding in findings:
        if not _passes_line_mapping(finding, valid_line_numbers_by_file):
            continue
        if not _passes_confidence(finding, config):
            continue
        if not _passes_explanation_quality(finding, config):
            continue

        key = _dedup_key(finding)
        if key in seen_keys:
            logger.info(
                "Dropping duplicate finding for %s:%s (%s)",
                finding.file_path,
                finding.line_number,
                finding.title,
            )
            continue
        seen_keys.add(key)

        survivors.append(finding)

    return survivors


def _passes_line_mapping(
    finding: Finding, valid_line_numbers_by_file: dict[str, set[int]]
) -> bool:
    """Reject findings that cannot be mapped to a changed line."""
    valid_lines = valid_line_numbers_by_file.get(finding.file_path)
    if not valid_lines or finding.line_number not in valid_lines:
        logger.info(
            "Rejecting finding for %s:%s -- not a changed line in this diff.",
            finding.file_path,
            finding.line_number,
        )
        return False
    return True


def _passes_confidence(finding: Finding, config: ValidationConfig) -> bool:
    """Reject low-confidence findings."""
    if finding.confidence < config.min_confidence:
        logger.info(
            "Rejecting finding for %s:%s -- confidence %.2f below threshold %.2f.",
            finding.file_path,
            finding.line_number,
            finding.confidence,
            config.min_confidence,
        )
        return False
    return True


def _passes_explanation_quality(finding: Finding, config: ValidationConfig) -> bool:
    """
    Reject vague findings and findings without an actionable suggestion.

    A finding whose description is too short to actually explain what
    the problem is, why it matters, and what could happen fails this
    check even at high confidence -- a generic one-liner like "this
    could be better" is not a real review comment.
    """
    if (
        not finding.title.strip()
        or not finding.description.strip()
        or not finding.suggestion.strip()
    ):
        logger.info(
            "Rejecting finding for %s:%s -- missing a required field.",
            finding.file_path,
            finding.line_number,
        )
        return False

    description_words = len(finding.description.split())
    if description_words < config.min_description_words:
        logger.info(
            "Rejecting finding for %s:%s -- description too vague (%d words).",
            finding.file_path,
            finding.line_number,
            description_words,
        )
        return False

    suggestion_words = len(finding.suggestion.split())
    if suggestion_words < config.min_suggestion_words:
        logger.info(
            "Rejecting finding for %s:%s -- suggestion not actionable (%d words).",
            finding.file_path,
            finding.line_number,
            suggestion_words,
        )
        return False

    return True


def _dedup_key(finding: Finding) -> tuple[str, int, str]:
    """
    Build a dedup key for a finding.

    Two findings at the same file and line with the same category are
    treated as duplicates of the same underlying issue, even if the
    LLM phrased them differently.
    """
    return (finding.file_path, finding.line_number, finding.category.value)
