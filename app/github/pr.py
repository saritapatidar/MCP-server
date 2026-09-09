"""
GitHub Pull Request operations.

This module provides functions to extract repository information
from a GitHub Pull Request URL and fetch the corresponding
Pull Request from GitHub.
"""

from urllib.parse import urlparse

from github.PullRequest import PullRequest

from app.github.client import get_github_client


def parse_pr_url(pr_url: str) -> tuple[str, str, int]:
    """
    Parse a GitHub Pull Request URL.

    Args:
        pr_url: GitHub Pull Request URL.

    Returns:
        A tuple containing:
            - owner: GitHub repository owner
            - repository: GitHub repository name
            - pr_number: Pull Request number

    Raises:
        ValueError: If the URL is not a valid GitHub Pull Request URL.
    """
    parsed_url = urlparse(pr_url)

    if parsed_url.netloc != "github.com":
        raise ValueError("Invalid GitHub Pull Request URL.")

    parts = parsed_url.path.strip("/").split("/")

    if len(parts) != 4 or parts[2] != "pull":
        raise ValueError("Invalid GitHub Pull Request URL.")

    owner = parts[0]
    repository = parts[1]

    try:
        pr_number = int(parts[3])
    except ValueError as exc:
        raise ValueError("Invalid Pull Request number.") from exc

    return owner, repository, pr_number


def get_pull_request(pr_url: str) -> PullRequest:
    """
    Fetch a GitHub Pull Request using its URL.

    Args:
        pr_url: GitHub Pull Request URL.

    Returns:
        The corresponding PyGithub PullRequest object.

    Raises:
        ValueError: If the PR URL is invalid.
    """
    owner, repository, pr_number = parse_pr_url(pr_url)

    github = get_github_client()

    repo = github.get_repo(f"{owner}/{repository}")

    return repo.get_pull(pr_number)