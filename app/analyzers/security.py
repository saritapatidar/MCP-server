"""
Optional security analyzer.

Runs Bandit against the added lines of a changed Python file, as a
best-effort supporting signal alongside the AI review. See
app/analyzers/lint.py for the shared limitation: only the added-lines
snippet is scanned, not the full file.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.core.logging import get_logger
from app.review.line_analyzer import extract_added_source

logger = get_logger(__name__)


def analyze(filename: str, patch: str) -> list[str]:
    """
    Run Bandit against the added lines of a Python file's diff.

    Args:
        filename: Path of the changed file.
        patch: The unified diff patch for the file.

    Returns:
        Human-readable notes, one per Bandit finding. Empty if the
        file is not Python, Bandit is not installed, or nothing was
        found.
    """
    if not filename.endswith(".py"):
        return []

    if shutil.which("bandit") is None:
        logger.debug("Bandit is not installed; skipping security analysis for %s.", filename)
        return []

    added_source = extract_added_source(patch)
    if not added_source.strip():
        return []

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_file = Path(tmp_dir) / Path(filename).name
        tmp_file.write_text(added_source)

        try:
            result = subprocess.run(
                ["bandit", "-f", "json", "-q", str(tmp_file)],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            logger.warning("Bandit failed to run for %s: %s", filename, exc)
            return []

        try:
            payload = json.loads(result.stdout or "{}")
        except json.JSONDecodeError:
            return []

        issues = payload.get("results", [])
        return [
            f"[security] {filename}:{issue.get('line_number')}: {issue.get('issue_text', '').strip()}"
            for issue in issues
        ]
