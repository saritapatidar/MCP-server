"""Tests for LLM-based review parsing, using a mocked LLMClient."""

import json

from app.llm.client import LLMClient, LLMClientError
from app.models.review import Category, Severity
from app.review.context_builder import build_file_contexts
from app.review.line_analyzer import parse_patch
from app.review.reviewer import review_hunks

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


class FakeLLMClient(LLMClient):
    """A stand-in LLMClient that returns a canned response."""

    def __init__(self, response: str | None = None, raise_error: bool = False):
        self.response = response
        self.raise_error = raise_error
        self.last_prompt: str | None = None

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.last_prompt = user_prompt
        if self.raise_error:
            raise LLMClientError("simulated provider failure")
        return self.response


def _build_contexts():
    hunks = parse_patch(SAMPLE_PATCH)
    return build_file_contexts("app/auth.py", hunks)


def test_review_hunks_parses_valid_findings():
    contexts = _build_contexts()
    canned_response = json.dumps(
        [
            {
                "file_path": "app/auth.py",
                "line_number": 13,
                "severity": "high",
                "category": "security",
                "title": "Missing authorization check",
                "description": "Access is granted based on a flag with no verification.",
                "suggestion": "Verify the admin claim against a trusted source.",
                "confidence": 0.9,
            }
        ]
    )
    client = FakeLLMClient(response=canned_response)

    findings = review_hunks(client, "app/auth.py", contexts)

    assert len(findings) == 1
    assert findings[0].severity is Severity.HIGH
    assert findings[0].category is Category.SECURITY
    assert findings[0].line_number == 13


def test_review_hunks_returns_empty_list_for_empty_findings():
    client = FakeLLMClient(response="[]")
    findings = review_hunks(client, "app/auth.py", _build_contexts())
    assert findings == []


def test_review_hunks_returns_empty_list_with_no_contexts():
    client = FakeLLMClient(response="[]")
    findings = review_hunks(client, "app/auth.py", [])
    assert findings == []
    assert client.last_prompt is None


def test_review_hunks_handles_llm_error_gracefully():
    client = FakeLLMClient(raise_error=True)
    findings = review_hunks(client, "app/auth.py", _build_contexts())
    assert findings == []


def test_review_hunks_discards_malformed_json():
    client = FakeLLMClient(response="not json")
    findings = review_hunks(client, "app/auth.py", _build_contexts())
    assert findings == []


def test_review_hunks_strips_markdown_code_fence():
    canned_response = "```json\n[]\n```"
    client = FakeLLMClient(response=canned_response)
    findings = review_hunks(client, "app/auth.py", _build_contexts())
    assert findings == []


def test_review_hunks_rejects_line_number_outside_diff():
    canned_response = json.dumps(
        [
            {
                "file_path": "app/auth.py",
                "line_number": 999,
                "severity": "low",
                "category": "bug",
                "title": "Hallucinated finding",
                "description": "This line was never part of the diff.",
                "suggestion": "N/A",
                "confidence": 0.5,
            }
        ]
    )
    client = FakeLLMClient(response=canned_response)
    findings = review_hunks(client, "app/auth.py", _build_contexts())
    assert findings == []


def test_review_hunks_rejects_invalid_severity():
    canned_response = json.dumps(
        [
            {
                "file_path": "app/auth.py",
                "line_number": 13,
                "severity": "catastrophic",
                "category": "bug",
                "title": "Bad severity",
                "description": "x",
                "suggestion": "x",
                "confidence": 0.5,
            }
        ]
    )
    client = FakeLLMClient(response=canned_response)
    findings = review_hunks(client, "app/auth.py", _build_contexts())
    assert findings == []
