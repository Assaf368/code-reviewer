# Code Reviewer

An AI-powered code review agent built with [LangChain](https://docs.langchain.com). It reads source files from a repository and returns a structured review covering bugs, edge cases, performance, and readability.

The project is being built in stages, starting from a single agent and growing into a multi-agent system orchestrated with LangGraph.

## Current status

**Stage 1: single reviewer agent**

- A LangChain agent (`create_agent`) backed by Claude
- A sandboxed `read_file` tool that can only access files inside the repository
- Command-line interface for reviewing a single file

## Roadmap

| Stage | Feature | Tech |
| --- | --- | --- |
| 1 | Single agent reviews a file | LangChain `create_agent` |
| 2 | More tools: browse the repo, run a linter | LangChain tools |
| 3 | Structured output: issues with severity and line numbers | Pydantic, structured output |
| 4 | Parallel specialist reviewers: security, performance, code quality | LangGraph |
| 5 | Routing: small diffs get one reviewer, large diffs get all three | LangGraph conditional edges |
| 6 | Critic agent that filters false positives and loops back for revisions | LangGraph cycles |
| 7 | Human-in-the-loop approval before posting to GitHub | LangGraph checkpointer |

Alongside the stages: evals with known-buggy samples, tracing with LangSmith, and unit tests.

## Project structure

```
code-reviewer/
├── code_reviewer/
│   ├── __main__.py        # CLI entry point
│   ├── config.py          # Settings and environment variables
│   ├── prompts.py         # System prompts
│   ├── tools/
│   │   └── files.py       # File-reading tool (repo-scoped)
│   └── agents/
│       └── reviewer.py    # Reviewer agent definition
├── samples/               # Example files with known issues
├── tests/                 # Unit tests
├── evals/                 # Agent quality evaluations
├── .env.example
└── requirements.txt
```

## Setup

Requires Python 3.11+ and an [Anthropic API key](https://console.anthropic.com).

```bash
git clone <repo-url>
cd code-reviewer

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

## Usage

```bash
python -m code_reviewer <file_path>
```

Example:

```bash
python -m code_reviewer samples/two_sum.py
```

The output shows the full agent loop: the request, each tool call, the tool results, and the final review.

## Configuration

Set these in `.env`:

| Variable | Description | Default |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | Anthropic API key (workspace-scoped) | required |
| `REVIEWER_MODEL` | Model in `provider:model` format | `anthropic:claude-haiku-4-5-20251001` |

## Security

The `read_file` tool resolves every path against the project root and refuses anything outside it, so the agent cannot read arbitrary files on the machine (for example `../../.ssh/id_rsa`).