"""
GitHub Pull Request diff operations.

This module provides functions to fetch the files changed in a
Pull Request and extract their diff information.
"""

from github.PullRequest import PullRequest
from github.File import File as PullRequestFile

def get_changed_files(pr: PullRequest) -> list[PullRequestFile]:
    """
    Get all files changed in a Pull Request.

    Args:
        pr: GitHub Pull Request object.

    Returns:
        A list of files changed in the Pull Request.
    """
    return list(pr.get_files())


def get_file_diff(file: PullRequestFile) -> str:
    """
    Get the diff/patch for a changed file.

    Args:
        file: GitHub Pull Request file object.

    Returns:
        The patch containing the changes made to the file.

    Raises:
        ValueError: If the file does not contain a patch.
    """
    if not file.patch:
        raise ValueError(
            f"No patch available for changed file: {file.filename}"
        )

    return file.patch