"""Deterministic security screen for Repo Guardian.

Day 4 rule: the security screen runs BEFORE the LLM, in plain Python, so it is
fully testable and cannot be talked out of a finding by injected text. Operates
on unified-diff text (the output of `git diff`).

Public surface:
    scan_diff(diff)   -> list[SecurityFinding]   (secrets, injection, high-stakes)
    mask_pii(diff)    -> (masked_text, count)     (email / phone / token -> [[PII]])
    decide_verdict(findings, conformance) -> (Verdict, rationale)
"""

from __future__ import annotations

import re

from app.schemas import (
    ConformanceReport,
    FindingCategory,
    SecurityFinding,
    Verdict,
)

# --- secret patterns ---------------------------------------------------------
# Each entry: (label, compiled regex). Kept conservative to limit false positives.
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWS access key id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub token", re.compile(r"ghp_[0-9A-Za-z]{36}")),
    ("OpenAI-style key", re.compile(r"sk-[0-9A-Za-z]{20,}")),
    ("Google API key", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("Slack token", re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}")),
    ("Private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----")),
    (
        "Hardcoded credential",
        re.compile(
            r"""(?ix)            # case-insensitive, verbose
            (?:password|passwd|secret|api[_-]?key|token)
            \s*[:=]\s*
            ['"][^'"\s]{6,}['"]   # a non-trivial quoted literal
            """
        ),
    ),
]

# --- PII patterns (masked, not blocked) --------------------------------------
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d \-]{8,}\d)(?!\d)")
_PII_MASK = "[[PII]]"

# --- prompt-injection phrases ------------------------------------------------
_INJECTION_PHRASES = [
    r"ignore (?:all |any )?(?:previous|prior|above) instructions",
    r"disregard (?:the |your )?(?:spec|instructions|rules)",
    r"approve this (?:pr|pull request|change|diff)",
    r"you are now",
    r"system prompt",
    r"act as (?:an? )?(?:admin|root|developer mode)",
    r"override (?:the )?(?:security|policy|guardrail)",
]
_INJECTION = re.compile("|".join(f"(?:{p})" for p in _INJECTION_PHRASES), re.IGNORECASE)

# --- high-stakes file paths --------------------------------------------------
_HIGH_STAKES = re.compile(
    r"(?ix)(auth|login|password|payment|billing|invoice|charge|"
    r"delete|drop|destroy|deploy|terraform|dockerfile|"
    r"\.github/workflows|secret|credential|iam|policy)"
)


def _iter_added_lines(diff: str):
    """Yield (file, line_no, text) for every ADDED line in a unified diff.

    Only added lines (`+`) are scanned — we review what the change introduces,
    not pre-existing code. line_no is the 1-based line number in the new file.
    """
    current_file = "(unknown)"
    new_line_no = 0
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            # "+++ b/path/to/file" -> "path/to/file"
            path = raw[4:].strip()
            current_file = path[2:] if path.startswith(("a/", "b/")) else path
            continue
        if raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            new_line_no = (int(m.group(1)) - 1) if m else 0
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            new_line_no += 1
            yield current_file, new_line_no, raw[1:]
        elif raw.startswith("-"):
            continue  # removed line: new file counter does not advance
        else:
            new_line_no += 1  # context line


def _changed_files(diff: str) -> list[str]:
    files = []
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            path = raw[4:].strip()
            files.append(path[2:] if path.startswith(("a/", "b/")) else path)
    return files


def scan_diff(diff: str) -> list[SecurityFinding]:
    """Run the deterministic screen. Returns findings; never raises."""
    findings: list[SecurityFinding] = []

    for file, line_no, text in _iter_added_lines(diff):
        for label, pattern in _SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(
                    SecurityFinding(
                        category=FindingCategory.SECRET,
                        file=file,
                        line=line_no,
                        detail=f"{label} detected on an added line (value redacted).",
                    )
                )
        if _INJECTION.search(text):
            findings.append(
                SecurityFinding(
                    category=FindingCategory.INJECTION,
                    file=file,
                    line=line_no,
                    detail="Possible prompt-injection text in the change. Not followed.",
                )
            )

    for file in _changed_files(diff):
        if _HIGH_STAKES.search(file):
            findings.append(
                SecurityFinding(
                    category=FindingCategory.HIGH_STAKES,
                    file=file,
                    line=0,
                    detail="Touches a high-stakes area (auth/payments/deletion/deploy).",
                )
            )

    return findings


def mask_pii(diff: str) -> tuple[str, int]:
    """Replace emails and phone numbers with [[PII]]. Returns (masked, count)."""
    count = 0

    def _sub(_match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return _PII_MASK

    masked = _EMAIL.sub(_sub, diff)
    masked = _PHONE.sub(_sub, masked)
    return masked, count


def decide_verdict(
    findings: list[SecurityFinding],
    conformance: ConformanceReport | None,
) -> tuple[Verdict, str]:
    """Apply the gating rules from specs/review.feature, deterministically.

    Security gates take precedence over the LLM's conformance judgment.
    """
    categories = {f.category for f in findings}

    if FindingCategory.SECRET in categories:
        return Verdict.REQUEST_CHANGES, "A hardcoded secret was introduced."
    if FindingCategory.INJECTION in categories:
        return (
            Verdict.NEEDS_HUMAN_REVIEW,
            "Prompt-injection text was detected; escalating to a human.",
        )
    if FindingCategory.HIGH_STAKES in categories:
        return (
            Verdict.NEEDS_HUMAN_REVIEW,
            "Change touches a high-stakes area; never auto-approved.",
        )

    if conformance is None:
        return Verdict.NEEDS_HUMAN_REVIEW, "No conformance judgment available."

    if conformance.matches_spec and conformance.is_low_risk:
        return (
            Verdict.LGTM,
            f"Matches spec scenario "
            f"'{conformance.satisfied_scenario or 'covered'}' and is low risk.",
        )
    if conformance.is_low_risk:
        return (
            Verdict.CONDITIONAL_LGTM,
            "Out of spec but low risk; merge after confirming the listed conditions.",
        )
    return Verdict.NEEDS_HUMAN_REVIEW, "Change is not low risk; a human should review."
