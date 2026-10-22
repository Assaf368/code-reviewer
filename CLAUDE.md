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
├── __main__.py      # CLI: check file exists → review_file() → print
├── pipeline.py      # review_file(): run agent → verify each issue (shared by CLI and evals)
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

Verification statuses: `confirmed`, `not_reproduced`, `crashed`, `inconclusive`, `line_not_reached`, `test_error`, `source_error`, `unverified`, `missing_test`, `not_tested`.

## Known risks still open

- The assert itself may encode a wrong assumption about correct behavior (a failing assert ≠ a real bug).
- A failing test does not prove the reported mechanism. Seen in the eval: a bug reported on unreachable palindrome.py:22 came out `confirmed` because its input failed on line 16. Now handled: the RUNNER records executed lines (sys.settrace), and a failure whose reported line never ran becomes `line_not_reached`. A line with code must run exactly (±1 would accept a dead `return` under a live `if`); a line without code (`else:`, comment) counts if a neighbor ran. It does not prove dead code, only that the confirmation does not belong to the claim. It still cannot catch a wrong explanation on a line that did run.
- Dead code as a reviewer capability (minor severity): a separate experiment, after the lines experiment, one variable at a time.
- The model may not understand what undocumented code is supposed to do. Idea: an `intended_behavior` field so the assumption is visible. Better idea (deferred): let the reviewer ask specific questions when unsure ("may nums be modified?") instead of guessing. In an eval nobody answers, so score whether it asked about the right things. A no-docstring run is a hint of how well it infers intent, not something to blame the model for.
- Idea: check each test against the suggested fix (it should fail on the original and pass on the fix).
- Results vary between runs (e.g. the O(n²) performance issue appears in some runs and not others). Only evals with repeated runs can tell.
- `run_python` executes model-written code locally. Production would need a Docker sandbox.
- The runner copies one file only, so files importing other project modules fail with `source_error`.
- `run_python` can open absolute paths, so eval isolation blocks `read_file` but not a determined model.
- Next experiment: change Issue.line to lines: list[int] (one report per bug). Compare to the eval baseline: duplicates should drop, recall should not.
  Definition of one bug, written the same way in the prompt and in the labels: if fixing one place leaves the other still broken, they are two bugs (e.g. the same mistake copied into two loops). If all places must change together, it is one bug with several lines. A broken function called from two places is one bug, on the function's line.
  Needs a dataset file where one bug really spans several lines that all run; the current dataset has 0 duplicates.

## Goal: v1.0 (agreed 2026-10-20, a few days of work)

The project can grow forever, so v1.0 is the finish line. It should show real, correct engineering to recruiters.

1. CI: GitHub Actions runs pytest on every push (Python 3.11 and 3.14). Badge in the README.
2. Fix loop in LangGraph (roadmap stage 6, simple version): issues that were not proven (`not_reproduced`, `line_not_reached`, `test_error`, ...) go back to the reviewer with the result, so it fixes the test or drops the claim. At most 2 rounds.
3. Stay with Sonnet for now and keep improving with it. Trying a cheaper model comes at the end, with other methods.
   Haiku run on max_area.py (2026-10-20): 77-192s per run, 9-64 run_python calls, up to 1.25M input tokens. Found the line 31 bug in 2/3 runs and reported correct line 25 as a bug in 2/3. One of those was `confirmed` only because its input also hit the line 31 bug: the line ran, so `line_not_reached` cannot catch it; testing against the fix would. Likely cause of the many calls: the prompt allows run_python "to explore" with no limit. Any cheaper-model attempt needs a cap on tool calls. Missing for a fair comparison: Sonnet time and tokens on the same file.
   Loop design (item 2): Assaf designs it next session.
4. README with the results.

Out of scope for v1.0 (list it in the README as possible next steps): parallel reviewers and routing (stages 4-5), posting to GitHub (stage 7), the `lines` experiment, dead code as a capability, a Docker sandbox, more dataset files.

## Eval

- `evals/labels.json`: `{"file.py": [{"category": "bug", "lines": [N, ...], "description": "..."}], "clean.py": []}`. A line belongs to a label if a reviewer pointing at it would be describing the same bug. Unreachable code gets a `readability` label, so a bug report on it counts as miscategorized. The other direction does not count: a readability or security note next to a bug label is counted as `other`, because every such case so far was a separate real issue (utcnow, a typo).
- Each dataset file must import without crashing and must have docstrings that state the contract.
- Each file is reviewed 3 times; recall and precision at three levels: all reports, `confirmed`, `confirmed` + `crashed`.
- `evals/results/baseline.json` is the reference run (Sonnet, prompt with "the docstring is the contract"). `--rescore` and `--reverify` work on saved runs without calling the model.

## Dataset notes

- `user_utils.py` tests false positives. Traps (correct code that looks wrong, not labeled): the shared mutable default `cache` on line 1 (the docstring makes it intentional and forbids modifying the result) and `for ... else` on lines 21-26. Line 32 has a readability label: `not (flags ^ flags)` is always True.
- `store.py` is the long file (~200 lines, 5 classes) with 3 bugs: wrong charged_amount, oversell with repeated items, ENABLE_DISCOUNTS ignored. Decided as not bugs through the docstrings: hash-based user ids (stable in one process, same username replaces the user), float money rounded to 2 decimals, deduct_stock doing nothing when stock is short. Still an easy hint: total_amount is computed and never used.
- The eval prints every false positive with its line, to see whether it landed on a trap.
- `rate_limiter.py` has no bugs. Trap: the failure branch of consume stores (current_tokens, now), which looks like it drops tokens but is correct (current_tokens already includes the refill; a 3000-sequence simulation matched a version without the update). Thread-safety claims were removed from the contract so a report about them is not a correct finding.
- `evals/questions.json`: ground truth for the future "ask the user" step, kept apart from labels so it does not affect scoring. Per file: lines, kind (`implied` = should infer without asking, `ambiguous` = should ask, `missing` = no contract), the question a good reviewer would ask, and the answer a simulated user would give. Needs both answers: some "bug", some "correct", so always guessing "bug" does not win.
- Labels may carry `"contract": "implied"` when the docstring gives only an indirect hint (rbac.py). Report those apart from files with an explicit contract; they are the test set for the future "ask the user" step.

## Roadmap (from README)

Stage 4: parallel specialist reviewers (LangGraph). Stage 5: routing by diff size. Stage 6: critic agent with loop. Stage 7: human approval before posting to GitHub.



### Eval rules
- Dataset file names must be neutral (what the code does, never what is wrong with it). The model sees the path.
- The reviewer must never be able to read `evals/labels.json`: run each case on a copy in a temp dir, with PROJECT_ROOT pointing there.
- Labels use `"lines": [...]`; a reported bug matches a label if its line is within ±1 of any listed line.