"""Typed contracts for Repo Guardian.

These mirror specs/review.feature. The LLM only produces ConformanceReport;
everything else (security findings, the final verdict) is decided deterministically
in Python so it is testable without a model call.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Verdict(str, Enum):
    """The four outcomes a review can produce (see specs/review.feature)."""

    LGTM = "LGTM"
    CONDITIONAL_LGTM = "CONDITIONAL_LGTM"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"


class FindingCategory(str, Enum):
    SECRET = "secret"
    PII = "pii"
    INJECTION = "injection"
    HIGH_STAKES = "high_stakes"


class SecurityFinding(BaseModel):
    """One deterministic security finding from the pre-LLM scan."""

    category: FindingCategory
    file: str = Field(description="File the finding occurs in, or '(unknown)'.")
    line: int = Field(default=0, description="1-based added-line number, 0 if N/A.")
    detail: str = Field(description="Human-readable explanation. Secrets are redacted.")


class ConformanceReport(BaseModel):
    """The ONLY part the LLM produces. Judgment about the change vs. the spec."""

    matches_spec: bool = Field(
        description="True if the change is covered by an existing spec scenario."
    )
    satisfied_scenario: str = Field(
        default="",
        description="Name of the spec scenario the change satisfies, if any.",
    )
    is_low_risk: bool = Field(
        description="True if no new deps, no destructive calls, no new external network access."
    )
    conditions: list[str] = Field(
        default_factory=list,
        description="Things a human should confirm before merging an out-of-spec change.",
    )
    vibe_diff: str = Field(
        description="2-4 sentence plain-English summary of what changed and why it matters."
    )


class ReviewReport(BaseModel):
    """The final artifact Repo Guardian emits. Assembled deterministically."""

    verdict: Verdict
    security_findings: list[SecurityFinding] = Field(default_factory=list)
    conformance: ConformanceReport | None = None
    vibe_diff: str = ""
    rationale: str = Field(
        default="",
        description="Why this verdict, in one or two sentences.",
    )
