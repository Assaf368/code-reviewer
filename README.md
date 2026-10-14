# Code Reviewer

An AI-powered code review agent built with [LangChain](https://docs.langchain.com). It reads source files from a repository and returns a structured review: each issue has a line number, a category, a severity, an explanation, a concrete failing input for bugs, and a suggested fix.

The project is being built in stages, starting from a single agent and growing into a multi-agent system orchestrated with LangGraph.

## Example output

```
The function gives wrong answers because it can pair an element with itself
and keeps state in a module-level dict that is never cleared.

[CRITICAL] line 14 · bug · Same element can be paired with itself
    The dict is fully populated before the lookup loop, so an element whose
    complement is itself matches its own entry.
    Example: two_sum([3, 2, 4], 6) returns [0, 0]. The correct answer is [1, 2].
    Fix: Build the map in a single pass and check before inserting.

[MAJOR] line 15 · performance · nums.index(x) makes the algorithm O(n^2)
    ...
```

## Current status

**Done**

- **Single reviewer agent:** a LangChain agent (`create_agent`) backed by Claude
- **Sandboxed `read_file` tool:** can only access files inside the repository, and returns line-numbered contents so the review cites accurate line numbers
- **Structured output:** reviews are validated Pydantic objects (`ReviewResult`) with a fixed severity scale (`critical`, `major`, `minor`) and categories (`bug`, `performance`, `security`, `readability`)
- **Evidence for bugs:** the prompt requires a concrete failing input for every reported bug
- **Tracing:** every run is traced in LangSmith (model calls, tool calls, latency, tokens, cost)

## Roadmap

| Stage | Feature | Tech | Status |
| --- | --- | --- | --- |
| 1 | Single agent reviews a file | LangChain `create_agent` | ✅ |
| 2 | More tools: run code to verify reported bugs, run a linter | LangChain tools, sandboxing | ⏳ |
| 3 | Structured output: issues with severity and line numbers | Pydantic, structured output | ✅ |
| 4 | Parallel specialist reviewers: security, performance, code quality | LangGraph | |
| 5 | Routing: small diffs get one reviewer, large diffs get all three | LangGraph conditional edges | |
| 6 | Critic agent that filters false positives and loops back for revisions | LangGraph cycles | |
| 7 | Human-in-the-loop approval before posting to GitHub | LangGraph checkpointer | |

Alongside the stages: evals with known-buggy samples, and unit tests.

## Design notes

- **Model choice is measured, not assumed.** The same sample was reviewed with Claude Haiku and Claude Sonnet. Haiku found the surface issues but misdiagnosed the main logic bug, while Sonnet identified it with a correct failing input. The reviewer defaults to a configurable model so cheaper models can be used for simpler agents later.
- **Line numbers come from the tool, not the model.** Without them, both models miscounted lines. `read_file` now prefixes every line with its number.
- **Claims must be verifiable.** Requiring a failing input for each bug makes weak claims easy to spot. The next stage will verify these inputs automatically by running them.

## Project structure

```
code-reviewer/
├── code_reviewer/
│   ├── __main__.py        # CLI entry point
│   ├── config.py          # Settings and environment variables
│   ├── prompts.py         # System prompts
│   ├── schemas.py         # Pydantic models for the review output
│   ├── formatting.py      # Terminal rendering of a review
│   ├── tools/
│   │   └── files.py       # Line-numbered, repo-scoped file reader
│   └── agents/
│       └── reviewer.py    # Reviewer agent definition
├── samples/               # Example files with known issues
├── tests/                 # Unit tests
├── evals/                 # Agent quality evaluations
├── .env.example
└── requirements.txt
```

## Setup

Requires Python 3.11+, an [Anthropic API key](https://console.anthropic.com), and optionally a [LangSmith](https://smith.langchain.com) API key for tracing.

```bash
git clone https://github.com/Assaf368/code-reviewer.git
cd code-reviewer

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env and add your keys
```

## Usage

```bash
python -m code_reviewer <file_path>
```

Example:

```bash
python -m code_reviewer samples/two_sum.py
```

Issues are printed sorted by severity, critical first.

## Configuration

Set these in `.env`:

| Variable | Description | Default |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | Anthropic API key (workspace-scoped) | required |
| `REVIEWER_MODEL` | Model in `provider:model` format. Sonnet is recommended for review quality | `anthropic:claude-haiku-4-5-20251001` |
| `LANGSMITH_TRACING` | Set to `true` to enable tracing | off |
| `LANGSMITH_API_KEY` | LangSmith API key | |
| `LANGSMITH_ENDPOINT` | LangSmith API URL. EU accounts use `https://eu.api.smith.langchain.com` | US endpoint |
| `LANGSMITH_PROJECT` | LangSmith project that receives the traces | `default` |

## Security

The `read_file` tool resolves every path against the project root and refuses anything outside it, so the agent cannot read arbitrary files on the machine (for example `../../.ssh/id_rsa`).