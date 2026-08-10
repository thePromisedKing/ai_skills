---
name: test-engineering-standards
description: Apply the testing specialization for a Java Spring Boot project — test level selection, JUnit 5 and Mockito conventions, Spring slice and integration tests, Testcontainers, ArchUnit boundary rules, contract tests, coverage expectations, and determinism. Use when engineering-standards aggregates a test target, when a test inventory or coverage plan is being built, or when a review must judge whether the tests a change ships actually prove its behavior.
---

# Test engineering standards
Never assume a material input or interpretation; return `NEEDS_INPUT` and request explicit confirmation.

Own the testing rules. Invoked by `engineering-standards`; callers reach it
through that aggregator. Remain read-only — this skill judges and plans tests,
it never writes them.

## Invocation

Accept:

```yaml
caller: engineering-standards | direct
purpose: inventory | implementation | review-generation | review-classification | gate-remediation
paths: [production and test paths in scope]
changed_behavior: [what the change does, when known]
baseline_reference: fingerprint of the resolved shared baseline
project_config_reference: fingerprint of the PROJECT_CONFIG_RESULT
```

## Apply

1. Read `references/test-standards.md` completely.
2. Take the permitted levels from `project-config` (`testing.levels`) and the
   coverage expectations from its `gates.coverage` block. A level the project
   does not list may not appear in an inventory; a coverage floor the project did
   not set is not invented here.
3. Read the nearest existing tests for the changed code. Their fixtures, naming,
   and harness are the convention to follow; a competing harness beside an
   established one is a finding.
4. For `purpose: inventory`, evaluate whether every requirement and material
   risk maps to a named test at the cheapest level that can actually prove it,
   and report what is unmapped.
5. For a review purpose, evaluate whether the tests present prove the changed
   behavior — not whether they exist, pass, or raise a coverage number.

## Result

Return:

```yaml
TEST_ENGINEERING_STANDARDS_RESULT:
  status: PASS | NEEDS_INPUT | BLOCKED
  applicable_rules: [concise rule and its reference section]
  level_assignments: [behavior, chosen level, why the cheaper level cannot prove it]
  gaps: [requirement or risk with no test, and the level it needs]
  violations: [path, line, rule, evidence]
  limitations: [behavior automation cannot prove, with the named manual scenario]
```

A behavior that automation genuinely cannot prove is recorded in `limitations`
with a concrete named scenario. It is never replaced by a test that asserts
nothing meaningful.

## Example

An engine building its test inventory:

```text
Claude Code: /test-engineering-standards purpose: inventory,
paths: [src/main/java/com/example/orders/checkout], changed_behavior:
["reject a checkout whose total exceeds the account limit"]

Codex: Use $test-engineering-standards for inventory on
src/main/java/com/example/orders/checkout.
```

Returns `TEST_ENGINEERING_STANDARDS_RESULT` with the limit-boundary cases
assigned to unit level, the persisted-limit lookup assigned to integration level
with the reason a mock cannot prove the query's tenant scoping, and a `gap` for
the concurrent-checkout race the requirements imply but no test covers. A
requested `e2e` level absent from `testing.levels` returns `NEEDS_INPUT`.

## Guardrails

- Remain read-only; never create, edit, or run a test.
- Never assign a level the project has not configured.
- Never accept a test that asserts nothing, asserts only that a mock was called,
  or passes equally with the change reverted.
- Never treat a coverage percentage as evidence of behavioral coverage.
- Never propose a mock where a real collaborator is cheap and deterministic.
- Never restate the shared baseline; add only what is test-specific.
