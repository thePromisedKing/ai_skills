---
name: web-engineering-standards
description: Apply the web specialization for a React and TypeScript front end assembled from headless libraries rather than a framework — the thin-client boundary, schema-validated API edges, tenant-scoped caching, cookie-session auth, the shared table and form kits, and the behavioural tests that stand in for a code reviewer. Use when engineering-standards aggregates a web target, when a change touches the front-end tree, or when a review must judge whether a component's tests prove what it does.
---

# Web engineering standards
Never assume a material input or interpretation; return `NEEDS_INPUT` and request explicit confirmation.

Own the front-end rules. Invoked by `engineering-standards`; callers reach it
through that aggregator. Remain read-only — this skill judges and plans, it
never writes code.

This specialization exists because the front end is the part of a repository
most likely to carry business logic it should not, and least likely to be read
by a human before it ships. Its rules are therefore about where logic lives and
what proves it works, not about how a component is written.

## Invocation

Accept:

```yaml
caller: engineering-standards | direct
purpose: implementation | review-generation | review-classification | gate-remediation
paths: [front-end paths in scope]
changed_behavior: [what the change does, when known]
baseline_reference: fingerprint of the resolved shared baseline
project_config_reference: fingerprint of the PROJECT_CONFIG_RESULT
```

## Apply

1. Read `references/web-standards.md` completely.
2. Resolve the front-end tree and its gate commands from `project-config`
   (`gates.eslint`, `gates.tsc`, `gates.vitest`, `gates.playwright` and their
   `root`). A tree this skill was not pointed at is out of scope; never infer
   one from a directory name.
3. Read the project's own front-end instructions — the repository's agent
   instruction files name the chosen libraries, the auth model, and the
   tenancy rule. Where they and this skill disagree on a project decision, the
   project's file governs and the disagreement is reported, not reconciled
   silently.
4. Read the nearest existing resource directory before judging a new one. The
   first fully-built resource is the exemplar; a second pattern beside an
   established one is a finding, even when the second is defensible in
   isolation.
5. Evaluate against the boundary rules in the reference: where logic lives,
   whether every response is schema-parsed, whether cache keys carry the tenant,
   and whether the tests prove the behaviour rather than assert its shape.

## Result

```yaml
WEB_STANDARDS_RESULT:
  status: PASS | NEEDS_INPUT | BLOCKED
  scope: {paths, tree_root}
  rules_applied: [rule id, where it bore on the change]
  findings:
    - rule: <id>
      severity: blocking | material | minor
      evidence: file:line and what is there
      remedy: the smallest change that satisfies the rule
  logic_in_client: [behaviour that belongs behind an endpoint, with the endpoint proposed]
  test_verdict: {proves_behavior: true | false, gaps: [...]}
  limitations: [unread instruction file, unresolved gate command, unexercised path]
```

Use `BLOCKED` when the project's front-end instructions cannot be read or
contradict each other on a point the change depends on. Use `NEEDS_INPUT` when
the tree, the gate commands, or the exemplar cannot be resolved.

## Example

A review asking whether a new list screen honours the tenancy rule:

```text
Claude Code: /web-engineering-standards purpose: review-generation, paths:
[web/src/pages/credit-notes], changed_behavior: list and filter credit notes

Codex: Use $web-engineering-standards with purpose review-generation, paths
web/src/pages/credit-notes, and changed behavior list and filter credit notes.
```

Returns `WEB_STANDARDS_RESULT` with a blocking finding when a query key omits
the tenant id, because that is a cross-tenant cache leak rather than a style
preference, and a material finding when the response is rendered without being
parsed. A screen that recomputes a total the backend already returns is
reported under `logic_in_client` with the endpoint that should own it.

## Guardrails

- Never approve business logic in the client. Tax, totals, numbering, state
  machines, and tenant isolation belong behind an endpoint; propose the endpoint
  instead of reviewing the implementation.
- Never accept a tenant-scoped query key that does not start with the tenant id.
- Never accept an API response rendered without schema parsing.
- Never propose a dependency. Naming one is a request for the owner, not a
  decision this skill makes.
- Never hand-roll focus management, keyboard navigation, or positioning where
  the project's primitive library provides it.
- Never count a feature as covered because a component test exists; a flow
  without an end-to-end test, including a negative permission or tenancy case,
  is an uncovered flow.
- Never judge a front end against a framework the project deliberately did not
  adopt.
- Never write or modify code, and never run a gate; report and return.
