from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["critical", "major", "minor"]
Category = Literal["bug", "performance", "security", "readability"]


class Issue(BaseModel):
    line: int = Field(description="Line number where the issue occurs")
    category: Category
    severity: Severity
    title: str = Field(description="One-line summary of the issue")
    explanation: str = Field(description="Why this is a problem")
    example: str | None = Field(
        default=None,
        description="A concrete input that demonstrates the bug",
    )
    fix: str = Field(description="Short suggested fix")
    test_code: str | None = Field(
        default=None,
        description=(
            "For bugs only: Python statements with assert that describe the correct "
            "behavior. They must pass on correct code and fail because of this bug."
        ),
    )
    untestable_reason: str | None = Field(
        default=None,
        description=(
            "For bugs that cannot be shown with a simple assert (they need a network, "
            "a database, other project files, timing, or concurrency): explain why. "
            "Use this instead of writing a test that does not really test the bug."
        ),
    )


class ReviewResult(BaseModel):
    issues: list[Issue]

CriticAction = Literal["keep", "drop", "revise", "split"]


class CriticDecision(BaseModel):
    report: int = Field(description="The number of the report, as given")
    action: CriticAction = Field(
        description=(
            "keep: right as it is, even if its test cannot prove it. "
            "drop: wrong. "
            "revise: right, but needs a better test, line or explanation. "
            "split: it mixes separate bugs."
        )
    )
    reason: str = Field(description="One or two sentences on why")
    issues: list[Issue] = Field(
        default_factory=list,
        description="For revise: the corrected report. For split: one report per bug. Empty otherwise.",
    )


class CriticResult(BaseModel):
    decisions: list[CriticDecision]
