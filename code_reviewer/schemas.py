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
        description="A concrete input that demonstrates the bug, required for bugs",
    )
    fix: str = Field(description="Short suggested fix")


class ReviewResult(BaseModel):
    summary: str = Field(description="Two-sentence overall assessment")
    issues: list[Issue]