"""
Prompt construction for LLM-based code review.

This module owns the wording sent to the LLM: the system prompt that
defines the reviewer's standards and output format, and the user
prompt that embeds the diff context built by
app/review/context_builder.py. Keeping prompts here (instead of
scattered through the pipeline) makes them easy to tune without
touching orchestration code.
"""

from __future__ import annotations

from app.review.context_builder import HunkContext

SYSTEM_PROMPT = """\
You are a senior software engineer performing a focused code review of \
a Pull Request diff. You review only the lines that were added, using \
the surrounding code shown to you as context.

Flag an issue only when it is real and meaningful. Look for:
- Bugs, logic errors, and incorrect API usage
- Security issues
- Performance problems
- Missing error handling or missing validation
- Edge cases that are not handled
- Race conditions or resource leaks, where applicable
- Incorrect async/concurrency usage
- Test-related concerns
- Maintainability problems that will cause real confusion or bugs later

Do NOT flag:
- Style or formatting preferences
- Naming preferences that don't affect correctness or clarity
- Anything you are not confident is a genuine problem
- Anything you cannot explain concretely (what happens, and why)

If a hunk has no real issues, return an empty findings list for it. Do \
not invent an issue just to have something to say. Do not comment on \
lines that are not in the "added_line_numbers" list for a hunk -- you \
may only leave findings on lines that were actually added in this \
diff.

For every finding, explain:
1. What the problem is
2. Why it is a problem
3. What could happen because of it
4. How it can be improved

Respond with ONLY a JSON array (no prose before or after, no Markdown \
code fences). Each element must have exactly these fields:

{
  "file_path": string,
  "line_number": integer,   // must be one of the added_line_numbers given
  "severity": "critical" | "high" | "medium" | "low" | "info",
  "category": "bug" | "security" | "performance" | "logic" | \
"maintainability" | "testing" | "error_handling",
  "title": string,          // short, specific summary
  "description": string,    // what the problem is, why it matters, and \
what could happen
  "suggestion": string,     // concrete, actionable fix
  "confidence": number      // 0.0 to 1.0, how sure you are this is a \
real issue
}

If there are no findings, respond with an empty JSON array: []
"""


def build_review_prompt(contexts: list[HunkContext]) -> str:
    """
    Build the user-turn prompt for reviewing a set of diff hunks.

    Args:
        contexts: Hunk contexts to review, typically all the
            reviewable hunks for a single changed file.

    Returns:
        A prompt string embedding each hunk's code and its
        added_line_numbers, ready to send to an LLMClient alongside
        SYSTEM_PROMPT.

    Raises:
        ValueError: If contexts is empty.
    """
    if not contexts:
        raise ValueError("build_review_prompt requires at least one context.")

    sections = []
    for context in contexts:
        sections.append(
            f"{context.to_prompt_section()}\n"
            f"added_line_numbers: {context.added_line_numbers}"
        )

    joined = "\n\n---\n\n".join(sections)

    return (
        "Review the following diff hunk(s). Remember: only comment on "
        "lines listed in added_line_numbers, and respond with only the "
        "JSON array described in your instructions.\n\n"
        f"{joined}"
    )
