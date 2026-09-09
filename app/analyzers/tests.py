"""
Optional test-related analyzer.

Running the real test suite (pytest) requires a full repository
checkout, which this pipeline does not perform -- it works only from
PR diffs fetched via the GitHub API. This analyzer instead applies a
lightweight heuristic: it flags added test functions that contain no
detected assertion, a common and easy-to-miss mistake in PRs that add
tests.
"""

from __future__ import annotations

import re

from app.review.line_analyzer import extract_added_source

_TEST_FUNCTION_RE = re.compile(r"^\s*def (test_\w+)\s*\(")
_ASSERT_HINT_RE = re.compile(r"\bassert\b|self\.assert\w+\(|pytest\.raises")


def analyze(filename: str, patch: str) -> list[str]:
    """
    Flag added test functions that appear to contain no assertion.

    Args:
        filename: Path of the changed file.
        patch: The unified diff patch for the file.

    Returns:
        Human-readable notes for any added test function with no
        detected assertion. Empty if the file is not a Python test
        file or no such function is found.
    """
    if "test" not in filename.lower() or not filename.endswith(".py"):
        return []

    added_source = extract_added_source(patch)
    if not added_source.strip():
        return []

    lines = added_source.splitlines()
    notes: list[str] = []
    current_function: str | None = None
    current_body: list[str] = []

    def _flush() -> None:
        if current_function and not any(_ASSERT_HINT_RE.search(line) for line in current_body):
            notes.append(f"[testing] {filename}: '{current_function}' has no detected assertion.")

    for line in lines:
        match = _TEST_FUNCTION_RE.match(line)
        if match:
            _flush()
            current_function = match.group(1)
            current_body = []
        elif current_function is not None:
            current_body.append(line)

    _flush()
    return notes
