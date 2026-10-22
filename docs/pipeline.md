# Pipeline

How a file goes from the command line to a verified review, and how the eval uses the same path.

## 1. Review

```mermaid
flowchart TD
    CLI["python -m code_reviewer file.py<br/>__main__.py"] --> CHECK{"resolve_repo_path:<br/>file inside the repo?"}
    CHECK -- no --> ERR["print error, exit 1"]
    CHECK -- yes --> RF["review_file()<br/>pipeline.py"]

    RF --> AGENT["Reviewer agent<br/>create_agent: Sonnet + system prompt"]

    subgraph LOOP["Agent loop: the model decides which tools to call"]
        AGENT <--> READ["read_file<br/>line-numbered, repo only"]
        AGENT <--> RUN["run_python<br/>file + model code, separate process,<br/>5s timeout, output cut to 2000 chars"]
    end

    AGENT --> OUT["ReviewResult<br/>list of Issue: line, category, severity,<br/>title, explanation, fix,<br/>test_code or untestable_reason"]
    OUT --> VERIFY["verify_issue() for each issue<br/>no model involved"]
    VERIFY --> RR["ReviewRun<br/>issues + statuses + tool calls + tokens"]
    RR --> PRINT["print_review<br/>summary line built in code,<br/>issues by severity,<br/>not_reproduced listed apart"]
```

## 2. Verifying one issue

The model only writes the test. This step runs it and decides the status.

```mermaid
flowchart TD
    I["Issue"] --> BUG{"category is bug?"}
    BUG -- no --> NT["not_tested"]
    BUG -- yes --> HAS{"has test_code?"}
    HAS -- no --> WHY{"has untestable_reason?"}
    WHY -- yes --> UV["unverified"]
    WHY -- no --> MT["missing_test"]

    HAS -- yes --> TMP["temp dir: target.py = the file,<br/>test_code.py, runner.py"]
    TMP --> RUNNER["python -I runner.py, 5s timeout<br/>runner records executed lines of target.py"]
    RUNNER --> LOAD{"import target ok?"}
    LOAD -- no --> E5["exit 5"]
    LOAD -- yes --> EXEC["run the test in a namespace<br/>with only the file's names"]
    EXEC --> WHERE{"what happened?"}
    WHERE -- "test passed" --> E0["exit 0"]
    WHERE -- "AssertionError in the test" --> E3["exit 3"]
    WHERE -- "AssertionError in the file" --> E4["exit 4"]
    WHERE -- "other exception in the test" --> E6["exit 6"]
    WHERE -- "other exception in the file" --> E7["exit 7"]

    E0 --> NR["not_reproduced"]
    E3 --> C["confirmed"]
    E4 --> INC["inconclusive"]
    E5 --> SE["source_error"]
    E6 --> TE["test_error"]
    E7 --> CR["crashed"]
    RUNNER -- "timeout" --> TE

    C --> LINE{"did the reported line run?<br/>code line: exactly<br/>line without code: a neighbor"}
    CR --> LINE
    LINE -- yes --> KEEP["keep confirmed / crashed"]
    LINE -- no --> LNR["line_not_reached"]
```

## 3. Eval

The eval runs the same `review_file()` as the CLI, on a copy of each dataset file.

```mermaid
flowchart TD
    START["python -m evals.run_eval<br/>optional --only files"] --> LABELS["load labels.json"]
    LABELS --> TRACE["one LangSmith trace: run_eval"]
    TRACE --> EACH["for each file, 3 runs"]
    EACH --> ISO["isolated_repo: copy the one file<br/>into an empty temp dir,<br/>point PROJECT_ROOT there"]
    ISO --> REV["review_file()<br/>same pipeline as the CLI"]
    REV --> REC["record: issues + statuses,<br/>seconds, tool calls, tokens,<br/>or the error if the run failed"]
    REC --> SAVE["save results JSON after every run"]
    SAVE --> EACH
    SAVE --> SCORE["score_file: match issues to labels<br/>same category, line within 1"]
    SCORE --> TABLE["table: recall and precision at 3 levels<br/>all / confirmed / confirmed + crashed<br/>+ duplicates, miscategorized, failed runs"]

    OLD["saved results JSON"] --> RESCORE["--rescore: score again with current labels"]
    OLD --> REVERIFY["--reverify: rerun the saved tests<br/>with current verification"]
    RESCORE --> TABLE
    REVERIFY --> TABLE
```
