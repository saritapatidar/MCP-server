"""
LLM-based code review.

This module runs a set of diff hunk contexts through an LLMClient and
parses the response into structured Finding objects. It does not
decide whether a finding is good enough to post to GitHub -- that is
the validator's job (app/review/validator.py).
"""

from __future__ import annotations

import json

from app.core.logging import get_logger
from app.llm.client import LLMClient, LLMClientError
from app.llm.prompts import SYSTEM_PROMPT, build_review_prompt
from app.models.review import Category, Finding, Severity
from app.review.context_builder import HunkContext

logger = get_logger(__name__)


def review_hunks(
    llm_client: LLMClient, file_path: str, contexts: list[HunkContext]
) -> list[Finding]:
    """
    Review a file's diff hunks with the LLM and return raw findings.

    Args:
        llm_client: The LLM provider to use.
        file_path: Path of the file the contexts belong to (used to
            fill in file_path on findings, and for logging).
        contexts: Reviewable hunk contexts for the file, as built by
            app/review/context_builder.py.

    Returns:
        The findings the LLM reported, without validation applied.
        Returns an empty list if there is nothing to review, if the
        LLM call fails, or if the LLM's response cannot be parsed.
    """
    if not contexts:
        return []

    prompt = build_review_prompt(contexts)

    try:
        raw_response = llm_client.complete(SYSTEM_PROMPT, prompt)
    except LLMClientError as exc:
        logger.error("LLM review failed for %s: %s", file_path, exc)
        return []

    return _parse_findings(raw_response, file_path, contexts)


def _parse_findings(
    raw_response: str, file_path: str, contexts: list[HunkContext]
) -> list[Finding]:
    """
    Parse the LLM's raw JSON response into Finding objects.

    Malformed entries are skipped and logged rather than raising, so
    one bad finding does not discard an otherwise-useful response.

    Args:
        raw_response: The LLM's raw text response, expected to be a
            JSON array.
        file_path: Path of the file being reviewed, used for logging.
        contexts: The hunk contexts sent to the LLM, used to validate
            that reported line numbers were actually reviewable.

    Returns:
        Successfully parsed findings.
    """
    valid_line_numbers = {
        line_number
        for context in contexts
        for line_number in context.added_line_numbers
    }

    try:
        payload = json.loads(_strip_code_fence(raw_response))
    except json.JSONDecodeError:
        logger.warning("LLM response for %s was not valid JSON; discarding.", file_path)
        return []

    if not isinstance(payload, list):
        logger.warning("LLM response for %s was not a JSON array; discarding.", file_path)
        return []

    findings: list[Finding] = []
    for entry in payload:
        finding = _parse_single_finding(entry, file_path, valid_line_numbers)
        if finding is not None:
            findings.append(finding)

    return findings


def _parse_single_finding(
    entry: object, file_path: str, valid_line_numbers: set[int]
) -> Finding | None:
    """
    Parse and validate a single finding entry from the LLM response.

    Args:
        entry: One element of the parsed JSON array.
        file_path: Path of the file being reviewed, used for logging
            and as a fallback if the entry omits file_path.
        valid_line_numbers: Line numbers that were actually part of
            the reviewed diff; findings outside this set are rejected.

    Returns:
        A Finding, or None if the entry is malformed or references a
        line that was not part of the diff.
    """
    if not isinstance(entry, dict):
        logger.warning("Skipping non-object finding entry for %s.", file_path)
        return None

    try:
        line_number = int(entry["line_number"])
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("Skipping finding with invalid line_number for %s: %s", file_path, exc)
        return None

    if line_number not in valid_line_numbers:
        logger.warning(
            "Skipping finding for %s: line %s was not part of the reviewed diff.",
            file_path,
            line_number,
        )
        return None

    try:
        return Finding(
            file_path=str(entry.get("file_path") or file_path),
            line_number=line_number,
            severity=Severity(entry["severity"]),
            category=Category(entry["category"]),
            title=str(entry["title"]),
            description=str(entry["description"]),
            suggestion=str(entry["suggestion"]),
            confidence=float(entry["confidence"]),
        )
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("Skipping malformed finding for %s: %s", file_path, exc)
        return None


def _strip_code_fence(text: str) -> str:
    """
    Strip a Markdown code fence from an LLM response, if present.

    Some models wrap JSON output in ```json ... ``` fences despite
    being instructed not to. This makes parsing robust to that.

    Args:
        text: Raw LLM response text.

    Returns:
        The text with a single leading/trailing code fence removed.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else ""
        if stripped.endswith("```"):
            stripped = stripped.rsplit("```", 1)[0]
    return stripped.strip()
