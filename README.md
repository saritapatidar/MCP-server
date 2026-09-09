# AI Code Review Agent

An AI-powered agent that reviews a GitHub Pull Request and posts
meaningful inline review comments directly on it -- triggered by an
MCP tool call, so you can just prompt an MCP-connected AI agent (e.g.
Claude Desktop / Claude Code) with something like:

> Could you please review this PR: https://github.com/owner/repo/pull/123

No terminal command and no manual PR-link attachment step is needed
once the MCP server below is connected -- the agent calls the
`review_pull_request` tool on its own when you ask it to review a PR.

## How it works

```
Claude / AI Agent
        |
        | MCP tool call: review_pull_request(pr_url)
        v
MCP Server (app/mcp/server.py)
        |
        v
Review Pipeline (app/review/pipeline.py)
        |
        +-- Fetch PR + changed files + diffs      (app/github/*)
        +-- Parse diffs into hunks/lines           (app/review/line_analyzer.py)
        +-- Build LLM context per hunk             (app/review/context_builder.py)
        +-- Optional static analysis (best-effort) (app/analyzers/*)
        +-- AI review via Claude                   (app/llm/*, app/review/reviewer.py)
        +-- Validate findings (drop noise)         (app/review/validator.py)
        +-- Generate comment bodies                (app/review/comment_generator.py)
        v
Post inline comments to GitHub                     (app/github/reviews.py)
```

The reviewer only comments where it finds a real, meaningful issue
(bugs, security, performance, logic, error handling, missing
validation, etc.) -- not on every changed line, and never on style or
formatting nits.

## 1. Setup

```bash
cd ai-code-review-agent
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

```env
GITHUB_TOKEN=ghp_your_personal_access_token       # needs "repo" scope
ANTHROPIC_API_KEY=sk-ant-your-api-key
```

Optional static analyzers (Ruff, Bandit, MyPy) are used automatically
if installed on your machine (`pip install ruff bandit mypy`), and are
silently skipped if not -- they never block the AI review.

## 2. Run the tests

```bash
pip install pytest
pytest -v
```

## 3. Try it without MCP first (dry run, no posting)

```python
from app.review.pipeline import run_review_pipeline

result = run_review_pipeline(
    "https://github.com/owner/repo/pull/123",
    post_to_github=False,   # set True to actually post comments
)
print(result)
```

## 4. Connect the MCP server to Claude

**Claude Desktop** -- add this to your `claude_desktop_config.json`
(Settings -> Developer -> Edit Config):

```json
{
  "mcpServers": {
    "ai-code-review-agent": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["-m", "app.mcp.server"],
      "cwd": "/absolute/path/to/ai-code-review-agent"
    }
  }
}
```

Restart Claude Desktop. The `review_pull_request` tool will then show
up as an available tool.

**Claude Code** -- from the project directory:

```bash
claude mcp add ai-code-review-agent -- .venv/bin/python -m app.mcp.server
```

## 5. Use it

Once connected, just prompt the agent naturally:

> Review this PR and add review comments:
> https://github.com/owner/repo/pull/123

The agent recognizes the request, calls `review_pull_request(pr_url)`
on the MCP server, and the pipeline above runs end to end -- fetching
the diff, reviewing it, and posting inline comments to the PR.

## Project structure

See `app/` for the implementation, organized by responsibility:
`github/` (GitHub API), `review/` (pipeline, diff parsing, context
building, validation, comment generation), `llm/` (provider-agnostic
LLM client + prompts), `analyzers/` (optional static analysis),
`models/` (data structures), `mcp/` (MCP server + tools), `core/`
(config, logging).

## Notes and limitations

- The pipeline works from PR diffs via the GitHub API; it does not
  check out the full repository. Static analyzers therefore run
  against added-lines snippets only, not whole files.
- Only `claude` is implemented as an LLM provider today.
  `app/llm/client.py` is structured so OpenAI/Ollama/Gemini can be
  added as additional classes without changing the pipeline.
- A GitHub review is posted as a single review with all inline
  comments batched together (capped at 50 comments per review).
