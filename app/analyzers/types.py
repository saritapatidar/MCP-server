"""
Optional type-checking analyzer.

Runs MyPy against the added lines of a changed Python file, as a
best-effort supporting signal alongside the AI review. See
app/analyzers/lint.py for the shared limitation: only the added-lines
snippet is checked in isolation, so cross-file type issues will not
surface here.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from app.core.logging import get_logger
from app.review.line_analyzer import extract_added_source

logger = get_logger(__name__)


def analyze(filename: str, patch: str) -> list[str]:
    """
    Run MyPy against the added lines of a Python file's diff.

    Args:
        filename: Path of the changed file.
        patch: The unified diff patch for the file.

    Returns:
        Human-readable notes, one per MyPy error. Empty if the file
        is not Python, MyPy is not installed, or nothing was found.
    """
    if not filename.endswith(".py"):
        return []

    if shutil.which("mypy") is None:
        logger.debug("MyPy is not installed; skipping type analysis for %s.", filename)
        return []

    added_source = extract_added_source(patch)
    if not added_source.strip():
        return []

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_file = Path(tmp_dir) / Path(filename).name
        tmp_file.write_text(added_source)

        try:
            result = subprocess.run(
                ["mypy", "--ignore-missing-imports", "--no-error-summary", str(tmp_file)],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            logger.warning("MyPy failed to run for %s: %s", filename, exc)
            return []

        if not result.stdout.strip():
            return []

        return [
            f"[types] {filename}: {line}"
            for line in result.stdout.strip().splitlines()
            if "error" in line.lower()
        ]
