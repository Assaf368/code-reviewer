# Code Reviewer: project context

## How to work with me (Assaf)

- **Talk to me in Hebrew.** Code, comments, commit messages and docs stay in English.
- This is a **learning project**. I'm preparing for Backend / AI Engineer interviews, and I come from Node.js and C#. Python is new to me.
- **I design, you critique.** For a new feature, let me propose the decomposition, tools, schemas and prompts first. Then review my design like a tech lead before writing code. Point out what I missed.
- Explain *why*, not only *what*. When you introduce a Python feature I may not know, compare it to JS/Node.
- Prefer small steps I can run and check. After each change, tell me exactly what to run and what output to expect.
- Don't over-praise. Tell me plainly when something is wrong.

## What the project is

A LangChain agent that reviews a Python file and returns a structured review. Every reported bug comes with an assert-based test, and **our own code** (not the model) runs that test to decide whether the bug is real.

Run it:

```bash
source .venv/bin/activate
python -m code_reviewer samples/two_sum.py
pytest
```

## Architecture

```
code_reviewer/
├── __main__.py      # CLI: check file exists → run agent → verify each issue → print
├── config.py        # MODEL_NAME from env (REVIEWER_MODEL)
├── prompts.py       # REVIEWER_SYSTEM_PROMPT
├── schemas.py       # Issue, ReviewResult (Pydantic; the model sees field descriptions)
├── verification.py  # verify_issue(): runs test_code, classifies the result. No model.
├── formatting.py    # prints the review; build_summary() builds the summary in code
├── tools/
│   ├── files.py     # resolve_repo_path(), read_file tool (line-numbered, repo-scoped)
│   └── execution.py # run_python tool, run_test() + RUNNER script, exit codes
└── agents/reviewer.py  # build_reviewer(): create_agent(model, tools, prompt, response_format)
tests/               # unit tests for the deterministic code (no model calls)
evals/               # (next) dataset + eval script measuring the model
samples/             # example files for manual runs
```

Tracing: LangSmith, EU endpoint, configured only through `.env` (`LANGSMITH_PROJECT=code-reviewer`).

## Key design decisions and why

1. **The model proposes, code decides.** The model writes `test_code`; `verify_issue` runs it and classifies by exit code. We removed a self-reported `verified` field because the model marked correct behavior as a bug.
2. **Prefer deterministic checks.** Before adding a prompt rule or a critic agent, ask: can code check this? (line numbers come from `read_file`; the summary is built in code; missing tests are caught in code.)
3. **Line numbers come from the tool**, because both Haiku and Sonnet miscounted lines.
4. **Sonnet for the reviewer.** Haiku found surface issues but misdiagnosed the main logic bug. Model is configurable via `.env`.
5. **Tests assert a property when several answers are valid** (e.g. `i != j and nums[i] + nums[j] == target`), not one exact value.
6. **The schema lets the model say "can't test".** `untestable_reason` exists so the model doesn't invent fake tests for bugs that need a network, DB, other files, timing, or concurrency.
7. **The test runner** imports the reviewed file as module `target` and runs the test in a separate namespace with only the target's names (a previous version leaked the runner's own variables and broke files that defined `f`, `test`, or `sys`). The failing frame decides the exit code.

Verification statuses: `confirmed`, `not_reproduced`, `inconclusive`, `test_error`, `source_error`, `unverified`, `missing_test`, `not_tested`.

## Known risks still open

- The assert itself may encode a wrong assumption about correct behavior (a failing assert ≠ a real bug).
- The model may not understand what undocumented code is supposed to do. Idea: an `intended_behavior` field so the assumption is visible.
- Idea: check each test against the suggested fix (it should fail on the original and pass on the fix).
- Results vary between runs (e.g. the O(n²) performance issue appears in some runs and not others). Only evals with repeated runs can tell.
- `run_python` executes model-written code locally. Production would need a Docker sandbox.
- The runner copies one file only, so files importing other project modules fail with `source_error`.

## Current task: first eval dataset

Scope: **bugs only**, small files with known bugs, match a reported bug to a label if the line is within ±1.

- `evals/dataset/*.py`: 4 files with 1–2 known bugs each (taken from my own buggy LeetCode attempts) + 1 clean file with no bugs.
- `evals/labels.json`: `{"file.py": [{"line": N, "description": "..."}], "clean.py": []}`.
- Each file must import without crashing (no top-level prints or syntax errors).
- Eval script: run the reviewer 3 times per file; compute **recall** and **precision**, both over all reported bugs and over `confirmed` only (the difference shows what verification is worth).
- With 5 files, treat the numbers as direction, not proof.

## Roadmap (from README)

Stage 4: parallel specialist reviewers (LangGraph). Stage 5: routing by diff size. Stage 6: critic agent with loop. Stage 7: human approval before posting to GitHub.



### Eval rules
- Dataset file names must be neutral (what the code does, never what is wrong with it). The model sees the path.
- The reviewer must never be able to read `evals/labels.json`: run each case on a copy in a temp dir, with PROJECT_ROOT pointing there.
- Labels use `"lines": [...]`; a reported bug matches a label if its line is within ±1 of any listed line.