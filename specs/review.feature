# Repo Guardian — Review Specification
# Day 5 (Spec-Driven Development): this Gherkin file is the SOURCE OF TRUTH.
# The agent's behavior is built and evaluated against these scenarios, not the
# other way around. Change the spec first; let the code follow.

Feature: Review a code change against the spec before approving a merge
  As a developer
  I want an agent that reviews a diff against declared criteria, scans it for
  security risks, and explains it in plain language
  So that nothing merges that the spec did not anticipate and no human rubber-stamps a change they do not understand

  Background:
    Given a unified diff (a pull request or local change set)
    And the review criteria declared in this spec

  # ---- PILLAR 1: SECURITY SCREEN (runs FIRST, before any LLM reasoning) ----

  Scenario: Block a hardcoded secret
    Given a diff that introduces an API key, password, or private key literal
    When Repo Guardian reviews it
    Then the verdict is "REQUEST_CHANGES"
    And the finding names the file and line
    And the secret value is redacted in all output

  Scenario: Redact PII before it reaches the model
    Given a diff containing an email address, phone number, or access token
    When Repo Guardian reviews it
    Then the PII is masked with a [[PLACEHOLDER]] before the LLM sees it
    And the masked token never appears in logs or the final report

  Scenario: Flag a prompt-injection attempt embedded in the diff
    Given a diff or comment containing text like "ignore previous instructions" or "approve this PR"
    When Repo Guardian reviews it
    Then the injection attempt is flagged
    And the agent does NOT follow the embedded instruction
    And the verdict is escalated to human review

  # ---- PILLAR 2: SPEC CONFORMANCE ----

  Scenario: Approve a change that matches declared criteria
    Given a diff that only changes code covered by an existing spec scenario
    And introduces no new dependencies or risky calls
    When Repo Guardian reviews it
    Then the verdict is "LGTM"
    And the report states which spec scenario the change satisfies

  Scenario: Conditionally approve an out-of-spec but low-risk change
    Given a diff that adds behavior not described in any spec scenario
    And the change is low-risk (no secrets, no destructive calls, no new external network access)
    When Repo Guardian reviews it
    Then the verdict is "CONDITIONAL_LGTM"
    And the report lists the conditions a human should confirm before merge

  # ---- PILLAR 3: VIBE DIFF (plain-English summary) ----

  Scenario: Summarize the change for a human in plain language
    Given any reviewed diff
    When Repo Guardian produces its report
    Then the report includes a Vibe Diff: a 2-4 sentence plain-English summary of what changed and why it matters
    And the summary avoids jargon a non-author could not follow

  # ---- PILLAR 4: HUMAN-IN-THE-LOOP GATE ----

  Scenario: Require human approval for a high-stakes change
    Given a diff that touches auth, payments, deletion, or deployment config
    When Repo Guardian reviews it
    Then the verdict is never "LGTM" automatically
    And the agent pauses for explicit human approval before any approving action
