"""Repo Guardian — fast pre-commit security screen (NO LLM, no cloud).

This is the "first line of defense" the way a pre-commit hook should be: it runs
ONLY the deterministic screen (`app.security.scan_diff`) over the staged diff.
No model call, no credentials, sub-second — so nobody is tempted to `--no-verify`.

Gating policy (intentionally conservative for a local commit):
    secret found    -> BLOCK   (exit 1)   never let a key reach history
    injection found -> BLOCK   (exit 1)   poisoned text shouldn't enter the repo
    high-stakes     -> WARN    (exit 0)   commit allowed; flagged for the deeper review

The deeper, LLM-based review (spec conformance + verdict) belongs at pre-push / CI,
where latency and cost are acceptable. See `review.py --gate`.
"""

from __future__ import annotations

import subprocess
import sys

# Render redaction markers / box chars cleanly on Windows terminals.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from app.schemas import FindingCategory
from app.security import scan_diff


def _staged_diff() -> str:
    """The diff of what is about to be committed (staged changes only)."""
    return subprocess.run(
        ["git", "diff", "--cached"], capture_output=True, text=True
    ).stdout


def main() -> int:
    diff = _staged_diff()
    if not diff.strip():
        return 0  # nothing staged to scan

    findings = scan_diff(diff)
    if not findings:
        print("Repo Guardian: clean — no secrets, injection, or high-stakes changes.")
        return 0

    blocking = [
        f
        for f in findings
        if f.category in (FindingCategory.SECRET, FindingCategory.INJECTION)
    ]
    warnings = [f for f in findings if f.category == FindingCategory.HIGH_STAKES]

    for f in warnings:
        loc = f.file if f.line == 0 else f"{f.file}:{f.line}"
        print(f"Repo Guardian [warn]  [{f.category.value}] {loc} — {f.detail}")

    if not blocking:
        print("Repo Guardian: commit allowed (warnings above are for the deeper review).")
        return 0

    print("\nRepo Guardian BLOCKED this commit:")
    for f in blocking:
        loc = f.file if f.line == 0 else f"{f.file}:{f.line}"
        print(f"  [{f.category.value}] {loc} — {f.detail}")
    print(
        "\nFix the finding above and re-commit. To bypass in a true emergency: "
        "git commit --no-verify  (don't make a habit of it)."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
