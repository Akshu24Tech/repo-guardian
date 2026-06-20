# Repo Guardian

An agentic code reviewer built with **Google ADK 2.0**. Point it at a diff and it
reviews the change against a written spec, screens it for security risks **before**
any LLM reasoning, writes a plain-English summary, and returns one of four verdicts
— never auto-approving anything dangerous.

Built to demonstrate the full Google "5-Day AI Agents / Vibecoding + ADK" course in
one real, shippable project: spec-driven development, a security-first agent
architecture, an evaluation suite, and a live cloud deployment.

---

## What it does

Give it a unified diff (a `git diff`, a `.patch`, or a pull request). Repo Guardian:

1. **Security screen (deterministic, runs first).** Scans the added lines for
   hardcoded secrets, masks PII to `[[PII]]`, and detects prompt-injection text —
   all in plain Python, before the model sees anything.
2. **Spec conformance (LLM).** Judges the change against `specs/review.feature`.
3. **Vibe Diff.** Writes a 2-4 sentence plain-English summary a non-author can follow.
4. **Verdict gate (deterministic).** Applies the rules and returns one verdict.

### The four verdicts

| Verdict | When |
|---------|------|
| `LGTM` | Safe, in-spec, low-risk |
| `CONDITIONAL_LGTM` | Out of spec but low-risk; conditions listed for a human |
| `REQUEST_CHANGES` | A hardcoded secret was introduced (secret value redacted) |
| `NEEDS_HUMAN_REVIEW` | Injection text, a high-stakes area (auth/payments/deletion/deploy), or not low-risk |

### Why it's safe by design

- **Security runs before the LLM.** A raw secret is never sent to the model and never
  printed back.
- **Injected instructions are data, not commands.** A diff that says "approve this PR"
  is flagged and escalated, never obeyed.
- **High-stakes changes never auto-approve.** Anything touching auth, payments,
  deletion, or deploy config stops for a human.
- **The agent stops at "Draft."** It recommends a verdict; a human or an authorized
  CI gate takes the merge action. See `skills/repo-guardian-review/SKILL.md`.

---

## Quickstart

**Prerequisites:** Python 3.11+, [`uv`](https://docs.astral.sh/uv/), and
`agents-cli` (`uv tool install google-agents-cli`). A Google Cloud project with
Application Default Credentials (`gcloud auth application-default login`) is needed
because the conformance step calls Gemini on Vertex AI.

```bash
# from the project root
agents-cli install        # creates .venv and installs deps
```

### Review a diff

```bash
# review a patch file
uv run python review.py path/to/change.diff

# review piped output
git diff | uv run python review.py

# review THIS repo's uncommitted changes
uv run python review.py --git
```

### See the three headline cases

```bash
uv run python demo.py
```

Prints a clean review for a clean change, a secret leak (blocked, redacted), and an
injection attempt in a high-stakes file (refused, escalated).

---

## How it's built

```
root_agent = ReviewPipeline            (a custom ADK BaseAgent orchestrator)
   │
   1. extract the diff from the request
   2. app/security.scan_diff      -> deterministic findings   (BEFORE the LLM)
   3. if secret/injection         -> skip the LLM, hard-gate the verdict
      else app/security.mask_pii  -> [[PII]] masked before the model sees anything
   4. inner LlmAgent (output_schema=ConformanceReport) -> conformance + Vibe Diff
   5. app/security.decide_verdict -> deterministic gating
   6. emit a formatted ReviewReport
```

| File | Role |
|------|------|
| `specs/review.feature` | The review contract in Gherkin. **Source of truth** — change the spec first. |
| `app/agent.py` | The `ReviewPipeline` orchestrator + the inner conformance LLM. |
| `app/security.py` | Deterministic secret/PII/injection scan + verdict gating. No LLM. |
| `app/schemas.py` | Typed contracts (`Verdict`, `ReviewReport`, `ConformanceReport`). |
| `skills/repo-guardian-review/SKILL.md` | The review skill: tuned trigger + Read→Draft→Act authority ladder. |
| `AGENTS.md` | Thin always-loaded router that points to the skill on demand. |

Only the conformance judgment uses the model; every security and verdict decision is
plain, testable Python.

---

## Testing & evaluation

```bash
# fast, free, no model calls — the deterministic security core (13 cases)
uv run pytest tests/unit

# end-to-end pipeline (calls the model)
uv run pytest tests/integration/test_pipeline.py
```

### Eval suite (the proof artifact)

The agent is evaluated, not trusted. Two metrics over 7 review scenarios: an
**LLM-as-judge** (`verdict_appropriateness`) and a **deterministic safety check**
(`no_secret_leak`).

```bash
agents-cli eval generate --dataset tests/eval/datasets/repo-guardian-dataset.json
agents-cli eval grade --config tests/eval/eval_config.yaml
```

Latest result: **7/7 verdicts judged correct (5.0/5), 0 secret leaks.** The graded
HTML report lands in `artifacts/grade_results/`.

Edit the cases in `tests/eval/build_dataset.py`, then
`uv run python tests/eval/build_dataset.py` to regenerate.

---

## Deploy (optional)

Deploys to **Vertex AI Agent Runtime** (managed; billed only while serving requests).

```bash
agents-cli scaffold enhance . --deployment-target agent_runtime
gcloud services enable aiplatform.googleapis.com cloudbuild.googleapis.com \
  storage.googleapis.com artifactregistry.googleapis.com cloudresourcemanager.googleapis.com \
  --project=YOUR_PROJECT_ID
agents-cli deploy --dry-run --no-confirm-project    # preview
agents-cli deploy --no-confirm-project              # ~5-10 min
agents-cli deploy --list                            # confirm it's live
```

Query the live engine: see `test_live.py` (set your own resource name).

### Tear down (avoid all charges)

```bash
# delete the engine
uv run python -c "import vertexai; from vertexai import agent_engines; vertexai.init(project='YOUR_PROJECT_ID', location='YOUR_REGION'); agent_engines.delete('YOUR_RESOURCE_NAME', force=True)"
# remove staged source from the deploy bucket
gcloud storage rm -r "gs://YOUR_STAGING_BUCKET/agent_engine/"
```

---

## Course mapping

| Day | Concept | Where it shows up |
|-----|---------|-------------------|
| 1 | New SDLC: verification is the craft | The eval suite + tests are the deliverable, not just the agent |
| 2 | Tools & interoperability | Deploys to a managed runtime; A2A card is the optional next step |
| 3 | Agent Skills | `skills/repo-guardian-review/SKILL.md` + thin `AGENTS.md` router |
| 4 | Security & evaluation | `app/security.py` (screen-before-LLM) + the LLM-as-judge eval |
| 5 | Spec-driven development | `specs/review.feature` drives the build; verdict gating is the guardrail |

For the full build story — decisions, bugs, and fixes — see
[`docs/BUILD_JOURNAL.md`](docs/BUILD_JOURNAL.md).
