"""Tests for GitHub Pull Request URL parsing and fetching."""

from unittest.mock import MagicMock, patch

from app.github.pr import get_pull_request, parse_pr_url


def test_parse_pr_url_extracts_owner_repo_and_number():
    owner, repo, number = parse_pr_url("https://github.com/owner/repository/pull/123")
    assert owner == "owner"
    assert repo == "repository"
    assert number == 123


def test_parse_pr_url_rejects_non_github_host():
    try:
        parse_pr_url("https://gitlab.com/owner/repository/pull/123")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_parse_pr_url_rejects_non_pull_path():
    try:
        parse_pr_url("https://github.com/owner/repository/issues/123")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_parse_pr_url_rejects_non_numeric_pr_number():
    try:
        parse_pr_url("https://github.com/owner/repository/pull/abc")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


@patch("app.github.pr.get_github_client")
def test_get_pull_request_fetches_correct_repo_and_number(mock_get_client):
    mock_pr = MagicMock()
    mock_repo = MagicMock()
    mock_repo.get_pull.return_value = mock_pr
    mock_github = MagicMock()
    mock_github.get_repo.return_value = mock_repo
    mock_get_client.return_value = mock_github

    result = get_pull_request("https://github.com/owner/repository/pull/123")

    mock_github.get_repo.assert_called_once_with("owner/repository")
    mock_repo.get_pull.assert_called_once_with(123)
    assert result is mock_pr
