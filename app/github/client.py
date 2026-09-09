"""
GitHub API client.

This module creates an authenticated GitHub client that can be used
by other parts of the application to interact with GitHub.
"""

from github import Github

from app.core.config import GITHUB_TOKEN


def get_github_client() -> Github:
    """
    Create and return an authenticated GitHub client.

    Returns:
        An authenticated PyGithub client.

    Raises:
        ValueError: If the GitHub token is not configured.
    """
    if not GITHUB_TOKEN:
        raise ValueError(
            "GITHUB_TOKEN is not configured. "
            "Please add it to the .env file."
        )

    return Github(GITHUB_TOKEN)