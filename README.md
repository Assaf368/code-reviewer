# Code Reviewer

An AI code review agent built with [LangChain](https://docs.langchain.com). It reads a Python file and returns a structured review: each issue has a line number, a category, a severity, an explanation and a suggested fix.

Every reported bug also comes with an assert-based test. The model writes the test, but the project's own code runs it and decides whether the bug is real. A bug that is not proven by its test is shown as unproven.

The project is built in stages, starting from a single agent and growing into a multi-agent system orchestrated with LangGraph.

## Example output

A real review of [`evals/dataset/store.py`](evals/dataset/store.py), a 200-line file with three planted bugs:

```
3 of 3 reported bugs confirmed, 0 crashed, 0 not reproduced, 0 need a manual check, 1 other issues.

[CRITICAL] line 180 · bug · charged_amount records the raw subtotal, not the amount charged ✓ confirmed
    The docstring says charged_amount is the amount actually charged, as returned by
    calculate_total. The code stores raw_subtotal, which has no discount and no tax.
    Test: sm=SessionManager();p=PaymentProcessor(sm,InventoryService())
          s=sm.create_session("u")
          items=[{"item_id":"item_02","quantity":4}]
          expected=p.calculate_total(items,"SUMMER10")
          assert p.process_payment(s,items,"SUMMER10")
          assert p.transaction_history[0]["charged_amount"]==expected
    Fix: Use "charged_amount": total_amount and remove the raw_subtotal computation.

[MAJOR] line 142 · bug · ENABLE_DISCOUNTS setting is ignored ✓ confirmed
    ...
```

## How a bug gets verified

1. The agent reads the file through a `read_file` tool that returns numbered lines, so it cites real line numbers.
2. For each bug it writes `test_code`: asserts that pass on correct code and fail because of the bug.
3. `verify_issue` runs the test in a separate process with a timeout. The file is imported as a module and the test runs in a namespace that holds only the file's names.
4. The result is classified by where the failure came from:

| Status | Meaning |
| --- | --- |
| `confirmed` | An assert in the test failed |
| `crashed` | The reviewed code raised an exception |
| `not_reproduced` | The test passed, so the claim did not hold |
| `line_not_reached` | The test failed, but the reported line never ran, so the failure proves something else |
| `inconclusive` | An assert inside the reviewed code failed |
| `test_error` | The test itself is broken (syntax error, unknown name, timeout) |
| `unverified` | The model explained why the bug cannot be tested with a simple assert |

`line_not_reached` uses `sys.settrace` to record which lines of the reviewed file ran. It was added after the eval showed a test that "confirmed" a bug on unreachable code: the test failed, but because of a different line.

## Evaluation

The eval runs the real pipeline on a labeled dataset and compares the reported bugs to the labels.

- **Dataset:** 7 files in [`evals/dataset`](evals/dataset). Five short algorithm files (four with known bugs, one clean), one file of traps (correct code that looks wrong), and one 200-line file with three bugs. 8 labeled bugs in total.
- **Isolation:** each run copies one file into an empty temp directory, so the agent cannot read the labels or other files.
- **Matching:** a reported bug matches a label if the category is the same and the line is within one of a labeled line.
- **Three levels:** all reported bugs, only `confirmed`, and `confirmed` + `crashed`. The gap between them shows what verification adds.
- Each file is reviewed 3 times, and raw results are saved so they can be re-scored or re-verified without calling the model.

### Results (Claude Sonnet, 3 runs per file)

| | Recall | Precision (all reports) | Precision (confirmed only) |
| --- | --- | --- | --- |
| First prompt | 24/24 | 24/30 | 18/21 |
| Prompt with "the docstring is the contract" | 24/24 | 24/24 | 18/18 |

Both false positives with the first prompt came back in every run: "three_sum mutates its input list" and "hash-based user ids may collide". Each is wrong only under an assumption the docstring does not make. The prompt now says that such issues are not bugs and should be reported as notes that name the assumption. The model did exactly that, and recall did not drop.

### What the eval showed

- The model found every labeled bug in every run, and never reported a bug on the clean file or on the traps.
- Verification caught claims that looked proven but were not. On unreachable code the model reported a bug whose test failed for a different reason, and on a file with two bugs the first one crashed before the test reached the second. `line_not_reached` moved these out of `confirmed`.
- A failing test proves something is broken, not that the explanation is right.

### Limits

- 7 files and 3 runs per file. Treat the numbers as a direction, not proof.
- The docstrings were written with the bugs in mind, so recall is optimistic. The same reason hides the possible cost of the docstring rule: no bug in this dataset sits outside the docstring.
- The dataset is now at its ceiling. The next experiments need harder files to show a difference.

## Design notes

- **The model proposes, code decides.** An earlier version let the model mark its own bugs as verified, and it marked correct behavior as a bug. Now the model only writes the test.
- **Prefer a deterministic check over a prompt rule.** Line numbers come from the tool, the summary line is built in code, and missing tests are caught in code. The prompt already said "do not report a bug you cannot demonstrate", and the model still did, so checks that matter live in code.
- **Model choice is measured.** On the same sample, Claude Haiku found surface issues but misdiagnosed the main logic bug, while Claude Sonnet found it with a correct failing input. The model is configurable.
- **Tests assert a property when several answers are valid**, for example `i != j and nums[i] + nums[j] == target` instead of one exact pair.

## Roadmap

| Stage | Feature | Tech | Status |
| --- | --- | --- | --- |
| 1 | Single agent reviews a file | LangChain `create_agent` | ✅ |
| 2 | Run code to verify reported bugs | Subprocess runner, `sys.settrace` | ✅ |
| 3 | Structured output: issues with severity and line numbers | Pydantic, structured output | ✅ |
| – | Eval with a labeled dataset | Python, unit tests | ✅ |
| 4 | Parallel specialist reviewers: security, performance, code quality | LangGraph | |
| 5 | Routing: small diffs get one reviewer, large diffs get all three | LangGraph conditional edges | |
| 6 | Critic agent that filters false positives and loops back for revisions | LangGraph cycles | |
| 7 | Human-in-the-loop approval before posting to GitHub | LangGraph checkpointer | |

## Project structure

```
code-reviewer/
├── code_reviewer/
│   ├── __main__.py        # CLI entry point
│   ├── pipeline.py        # review_file(): run the agent, then verify each issue
│   ├── verification.py    # Runs each bug's test and classifies the result
│   ├── config.py          # Settings and environment variables
│   ├── prompts.py         # System prompt
│   ├── schemas.py         # Pydantic models for the review output
│   ├── formatting.py      # Terminal rendering of a review
│   ├── tools/
│   │   ├── files.py       # Line-numbered, repo-scoped file reader
│   │   └── execution.py   # Test runner and the run_python tool
│   └── agents/
│       └── reviewer.py    # Reviewer agent definition
├── evals/
│   ├── dataset/           # Files with known bugs and traps
│   ├── labels.json        # Where the bugs are
│   ├── matching.py        # Matching and metrics (pure functions)
│   ├── run_eval.py        # Runs the eval, prints the table, saves raw results
│   └── results/           # baseline.json
├── samples/               # Example files for manual runs
├── tests/                 # Unit tests (no model calls)
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
python -m code_reviewer samples/two_sum.py     # review a file
pytest                                         # unit tests, no API calls

python -m evals.run_eval                       # full eval (calls the model)
python -m evals.run_eval --only store.py       # selected dataset files
python -m evals.run_eval --rescore evals/results/baseline.json    # re-score saved runs, no API calls
python -m evals.run_eval --reverify evals/results/baseline.json   # re-run saved tests with current verification
```

## Configuration

Set these in `.env`:

| Variable | Description | Default |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | Anthropic API key | required |
| `REVIEWER_MODEL` | Model in `provider:model` format. Sonnet is recommended for review quality | `claude-haiku-4-5` |
| `LANGSMITH_TRACING` | Set to `true` to enable tracing | off |
| `LANGSMITH_API_KEY` | LangSmith API key | |
| `LANGSMITH_ENDPOINT` | LangSmith API URL. EU accounts use `https://eu.api.smith.langchain.com` | US endpoint |
| `LANGSMITH_PROJECT` | LangSmith project that receives the traces | `default` |

## Security

- The `read_file` tool resolves every path against the project root and refuses anything outside it, so the agent cannot read arbitrary files (for example `../../.ssh/id_rsa`).
- Tests written by the model run locally in a separate process with a timeout. That is fine for a learning project, but production use would need a real sandbox such as a container.
