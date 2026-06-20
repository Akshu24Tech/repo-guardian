# Repo Guardian — Agent Router

Thin, always-loaded index (Day-3 pattern: a passive router that points to skills
on demand, rather than inlining all instructions). Load the linked skill only when
its trigger matches.

## Skills

- **`skills/repo-guardian-review/SKILL.md`** — review a git diff / patch / PR
  against `specs/review.feature` before merge. Triggers: "review this diff",
  "check this PR", "is this safe to merge", "scan this patch for secrets".
  Runs the security screen before the LLM; returns a verdict + Vibe Diff.

## Source of truth

- `specs/review.feature` — the review contract. Change the spec first; code follows.

## Build / verify

- `uv run pytest tests/unit tests/integration` — tests
- `agents-cli eval generate && agents-cli eval grade --config tests/eval/eval_config.yaml` — eval scorecard
