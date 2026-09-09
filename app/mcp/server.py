"""
MCP server entry point.

Exposes review_pull_request as an MCP tool so an AI agent (such as
Claude, connected to this server) can trigger a full Pull Request
review just by being asked in plain language -- e.g. "Could you
please review this PR: <url>" -- with no terminal command and no
manually attached PR link required from the user.

Run directly:
    python -m app.mcp.server

Then connect it as an MCP server in Claude Desktop / Claude Code (see
README.md for the exact config). Once connected, prompting the agent
naturally is enough to invoke this tool.
"""

from __future__ import annotations
from mcp.server import MCPServer
from app.core.logging import get_logger
from app.mcp.tools import review_pull_request as _review_pull_request

logger = get_logger(__name__)

mcp = MCPServer("ai-code-review-agent")


@mcp.tool()
def review_pull_request(pr_url: str) -> str:
    """
    Review a GitHub Pull Request and post inline review comments.

    Call this whenever the user asks you to review, check, or comment
    on a GitHub Pull Request and gives (or clearly implies) its URL.

    Args:
        pr_url: URL of the GitHub Pull Request to review, e.g.
            "https://github.com/owner/repository/pull/123".

    Returns:
        A summary of the review: how many files were reviewed and how
        many comments were posted.
    """
    logger.info("MCP tool call: review_pull_request(%s)", pr_url)
    return _review_pull_request(pr_url)


if __name__ == "__main__":
    mcp.run()
