"""Repo Guardian CLI — review a diff and print the verdict.

Usage:
    uv run python review.py path/to/change.diff      # review a .diff / .patch file
    git diff | uv run python review.py               # review piped stdin
    uv run python review.py --git                     # review THIS repo's uncommitted changes
    uv run python review.py --git --gate             # ...and exit non-zero on a blocking verdict

With --gate the process exits 1 when the verdict is REQUEST_CHANGES or
NEEDS_HUMAN_REVIEW, so it can drive a pre-push hook or a CI step.

The deployed cloud version is the same agent; this is the local demo surface.
"""

import asyncio
import subprocess
import sys

# Verdicts that should fail a gated run (pre-push / CI).
_BLOCKING = {"REQUEST_CHANGES", "NEEDS_HUMAN_REVIEW"}

# Render box-drawing / em dashes cleanly on Windows terminals.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agent import root_agent


def _read_diff() -> str:
    args = [a for a in sys.argv[1:] if a and a != "--gate"]
    if args and args[0] == "--git":
        return subprocess.run(
            ["git", "diff"], capture_output=True, text=True
        ).stdout
    if args:
        with open(args[0], encoding="utf-8") as fh:
            return fh.read()
    if not sys.stdin.isatty():
        return sys.stdin.read()
    print("No diff given. Pass a file, pipe `git diff`, or use --git.")
    sys.exit(1)


async def review(diff: str) -> tuple[str, str]:
    """Run the agent. Returns (formatted_report, verdict)."""
    ss = InMemorySessionService()
    await ss.create_session(
        app_name="app", user_id="cli", session_id="s", state={"diff": diff}
    )
    runner = Runner(agent=root_agent, app_name="app", session_service=ss)
    out = ""
    async for ev in runner.run_async(
        user_id="cli",
        session_id="s",
        new_message=types.Content(
            role="user", parts=[types.Part.from_text(text="review")]
        ),
    ):
        if ev.content and ev.content.parts:
            for p in ev.content.parts:
                if p.text:
                    out = p.text
    session = await ss.get_session(app_name="app", user_id="cli", session_id="s")
    verdict = (session.state.get("review_report") or {}).get("verdict", "")
    return out, verdict


def main() -> None:
    gate = "--gate" in sys.argv[1:]
    diff = _read_diff()
    if not diff.strip():
        print("Empty diff — nothing to review.")
        return
    report, verdict = asyncio.run(review(diff))
    print(report)
    if gate and verdict in _BLOCKING:
        sys.exit(1)


if __name__ == "__main__":
    main()
