"""Tests for finding validation."""

from app.models.review import Category, Finding, Severity
from app.review.validator import ValidationConfig, validate_findings

VALID_LINES = {"app/auth.py": {13, 14, 15}}


def _make_finding(**overrides) -> Finding:
    defaults = dict(
        file_path="app/auth.py",
        line_number=13,
        severity=Severity.HIGH,
        category=Category.SECURITY,
        title="Missing authorization check",
        description="Access is granted based on a client-controlled flag with no server-side verification.",
        suggestion="Verify the admin claim against a trusted, server-side source before granting access.",
        confidence=0.9,
    )
    defaults.update(overrides)
    return Finding(**defaults)


def test_valid_finding_is_kept():
    findings = [_make_finding()]
    result = validate_findings(findings, VALID_LINES)
    assert len(result) == 1


def test_low_confidence_finding_is_rejected():
    findings = [_make_finding(confidence=0.2)]
    result = validate_findings(findings, VALID_LINES)
    assert result == []


def test_confidence_at_threshold_is_kept():
    config = ValidationConfig(min_confidence=0.6)
    findings = [_make_finding(confidence=0.6)]
    result = validate_findings(findings, VALID_LINES, config)
    assert len(result) == 1


def test_vague_description_is_rejected():
    findings = [_make_finding(description="This could be better.")]
    result = validate_findings(findings, VALID_LINES)
    assert result == []


def test_unactionable_suggestion_is_rejected():
    findings = [_make_finding(suggestion="Fix it.")]
    result = validate_findings(findings, VALID_LINES)
    assert result == []


def test_finding_on_unmapped_line_is_rejected():
    findings = [_make_finding(line_number=999)]
    result = validate_findings(findings, VALID_LINES)
    assert result == []


def test_finding_for_unknown_file_is_rejected():
    findings = [_make_finding(file_path="app/other.py")]
    result = validate_findings(findings, VALID_LINES)
    assert result == []


def test_duplicate_findings_are_deduplicated():
    findings = [
        _make_finding(title="Missing authorization check"),
        _make_finding(title="Same issue, worded differently"),
    ]
    result = validate_findings(findings, VALID_LINES)
    assert len(result) == 1
    assert result[0].title == "Missing authorization check"


def test_same_line_different_category_is_not_a_duplicate():
    findings = [
        _make_finding(category=Category.SECURITY),
        _make_finding(category=Category.PERFORMANCE),
    ]
    result = validate_findings(findings, VALID_LINES)
    assert len(result) == 2


def test_custom_config_thresholds_are_respected():
    config = ValidationConfig(min_confidence=0.95)
    findings = [_make_finding(confidence=0.9)]
    result = validate_findings(findings, VALID_LINES, config)
    assert result == []
