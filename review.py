"""
Entry point for the AI Code Review Agent.

This module accepts a GitHub Pull Request URL from the command line,
validates the URL, and extracts the repository owner, repository name,
and pull request number.
"""

import sys
from urllib.parse import urlparse


def parse_pr_url(pr_url: str) -> tuple[str, str, int]:
    """
    Parse a GitHub Pull Request URL.

    Args:
        pr_url: GitHub Pull Request URL.

    Returns:
        A tuple containing:
            - repository owner
            - repository name
            - pull request number

    Raises:
        ValueError: If the URL is not a valid GitHub Pull Request URL.
    """
    parsed_url = urlparse(pr_url)

    if parsed_url.netloc != "github.com":
        raise ValueError("Invalid GitHub URL.")

    parts = parsed_url.path.strip("/").split("/")

    if len(parts) != 4 or parts[2] != "pull":
        raise ValueError("Invalid GitHub Pull Request URL.")

    owner = parts[0]
    repository = parts[1]

    try:
        pr_number = int(parts[3])
    except ValueError as exc:
        raise ValueError("Pull Request number must be an integer.") from exc

    return owner, repository, pr_number


def main() -> None:
    """Start the AI Code Review Agent."""

    if len(sys.argv) != 2:
        print("Usage: python review.py <github_pr_url>")
        return

    pr_url = sys.argv[1]

    try:
        owner, repository, pr_number = parse_pr_url(pr_url)
    except ValueError as exc:
        print(f"Error: {exc}")
        return

    print(f"Owner      : {owner}")
    print(f"Repository : {repository}")
    print(f"PR Number  : {pr_number}")


if __name__ == "__main__":
    main()