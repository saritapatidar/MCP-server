"""
Optional lint analyzer.

Runs Ruff against the added lines of a changed Python file, as a
best-effort supporting signal alongside the AI review -- not a
replacement for it. The pipeline continues normally if Ruff is not
installed or the check fails for any reason.

Limitation: the pipeline works from PR diffs fetched via the GitHub
API and does not check out the full repository. This analyzer
therefore lints only the added-lines snippet in isolation, which
catches self-contained issues but not ones that depend on the rest of
the file.
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
    Run Ruff against the added lines of a Python file's diff.

    Args:
        filename: Path of the changed file, used to decide whether
            this analyzer applies.
        patch: The unified diff patch for the file.

    Returns:
        Human-readable notes, one per Ruff finding. Empty if the file
        is not Python, Ruff is not installed, or nothing was found.
    """
    if not filename.endswith(".py"):
        return []

    if shutil.which("ruff") is None:
        logger.debug("Ruff is not installed; skipping lint analysis for %s.", filename)
        return []

    added_source = extract_added_source(patch)
    if not added_source.strip():
        return []

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_file = Path(tmp_dir) / Path(filename).name
        tmp_file.write_text(added_source)

        try:
            result = subprocess.run(
                ["ruff", "check", "--output-format=concise", str(tmp_file)],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            logger.warning("Ruff failed to run for %s: %s", filename, exc)
            return []

        if not result.stdout.strip():
            return []

        return [f"[lint] {filename}: {line}" for line in result.stdout.strip().splitlines()]
