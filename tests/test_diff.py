"""Tests for diff parsing and reviewable line extraction."""

import pytest

from app.review.line_analyzer import LineType, get_reviewable_lines, parse_patch

SAMPLE_PATCH = (
    "@@ -10,6 +10,8 @@\n"
    " def login_user(username):\n"
    "     user = get_user(username)\n"
    " \n"
    "+    if user.is_admin:\n"
    "+        grant_access(user)\n"
    "+\n"
    "     return user\n"
)


def test_parse_patch_returns_one_hunk():
    hunks = parse_patch(SAMPLE_PATCH)
    assert len(hunks) == 1


def test_parse_patch_hunk_header_values():
    hunk = parse_patch(SAMPLE_PATCH)[0]
    assert hunk.old_start == 10
    assert hunk.old_count == 6
    assert hunk.new_start == 10
    assert hunk.new_count == 8


def test_parse_patch_line_type_counts():
    hunk = parse_patch(SAMPLE_PATCH)[0]
    line_types = [line.line_type for line in hunk.lines]
    assert line_types.count(LineType.ADDED) == 3
    assert line_types.count(LineType.CONTEXT) == 4


def test_parse_patch_new_line_numbers_are_sequential():
    hunk = parse_patch(SAMPLE_PATCH)[0]
    added = [line for line in hunk.lines if line.line_type is LineType.ADDED]
    assert [line.new_lineno for line in added] == [13, 14, 15]


def test_parse_patch_raises_on_empty_patch():
    with pytest.raises(ValueError):
        parse_patch("")


def test_get_reviewable_lines_returns_only_added_lines():
    hunks = parse_patch(SAMPLE_PATCH)
    reviewable = get_reviewable_lines(hunks)
    assert len(reviewable) == 3
    assert all(line.line_type is LineType.ADDED for line in reviewable)
    assert reviewable[0].content == "    if user.is_admin:"
