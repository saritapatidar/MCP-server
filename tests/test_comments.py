"""Tests for review comment generation."""

from app.models.review import Category, Finding, Severity
from app.review.comment_generator import generate_comment, generate_comments


def _make_finding(**overrides) -> Finding:
    defaults = dict(
        file_path="app/auth.py",
        line_number=13,
        severity=Severity.HIGH,
        category=Category.SECURITY,
        title="Missing authorization check",
        description="Access is granted based on a client-controlled flag with no verification.",
        suggestion="Verify the admin claim against a trusted source before granting access.",
        confidence=0.9,
    )
    defaults.update(overrides)
    return Finding(**defaults)


def test_generate_comment_maps_path_line_and_side():
    finding = _make_finding()
    comment = generate_comment(finding)
    assert comment.path == "app/auth.py"
    assert comment.line == 13
    assert comment.side == "RIGHT"


def test_generate_comment_body_contains_all_four_parts():
    finding = _make_finding()
    comment = generate_comment(finding)
    assert "Missing authorization check" in comment.body
    assert finding.description in comment.body
    assert finding.suggestion in comment.body
    assert "Suggestion" in comment.body


def test_generate_comment_includes_severity_indicator():
    high = generate_comment(_make_finding(severity=Severity.HIGH))
    info = generate_comment(_make_finding(severity=Severity.INFO))
    assert high.body != info.body
    assert high.body[0] != info.body[0]


def test_generate_comments_preserves_order_and_count():
    findings = [
        _make_finding(line_number=13, title="First"),
        _make_finding(line_number=14, title="Second"),
        _make_finding(line_number=15, title="Third"),
    ]
    comments = generate_comments(findings)
    assert [c.line for c in comments] == [13, 14, 15]
    assert [f.title for f in findings] == ["First", "Second", "Third"]


def test_generate_comments_handles_empty_list():
    assert generate_comments([]) == []
