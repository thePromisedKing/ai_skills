---
name: java-engineering-standards
description: Apply the Java language and Spring Boot specialization on top of the engineering baseline — resource and exception safety, null and Optional discipline, immutability, records and sealed types, layering and dependency direction, dependency injection, transactions, web and validation boundaries, persistence, caching, messaging, scheduling, resilience, and observability. Use when engineering-standards aggregates a java target, or when a review, architecture comparison, or gate remediation needs the framework-specific rules rather than the cross-cutting baseline.
---

# Java engineering standards
Never assume a material input or interpretation; return `NEEDS_INPUT` and request explicit confirmation.

Own the Java and Spring Boot rules. Invoked by `engineering-standards`; callers
reach it through that aggregator rather than directly. Remain read-only.

## Invocation

Accept:

```yaml
caller: engineering-standards | direct
purpose: implementation | review-generation | review-classification | gate-remediation
paths: [java source, test, build, or migration paths]
baseline_reference: fingerprint of the resolved shared baseline
project_config_reference: fingerprint of the PROJECT_CONFIG_RESULT
```

## Apply

1. Read `references/java-language-standards.md` for language-level rules.
2. Read `references/spring-boot-standards.md` when any path is inside a Spring
   application, which is the normal case. Skip it only for a pure library module
   with no Spring dependency, and say so in `limitations`.
3. Read the repository's own instructions inside the declared paths and the
   nearest maintained analogous code. Local convention wins over a generic
   preference in these references; a local convention never wins over a
   correctness, security, or compatibility rule.
4. Use `project.base_package`, `project.modules`, and `build.java_release` from
   `project-config` to distinguish first-party code, validate module targeting,
   and gate language-feature guidance. Never infer a package root from a file
   path when the configuration states it.
5. Produce the applicable rules and concrete violations. Do not edit files.

## Result

Return:

```yaml
JAVA_ENGINEERING_STANDARDS_RESULT:
  status: PASS | NEEDS_INPUT | BLOCKED
  applicable_rules: [concise rule and its reference section]
  violations: [path, line, rule, evidence]
  constraints: [implementation constraints the caller must honor]
  conflicts: [local convention versus reference rule, both cited]
  limitations: [unread reference and why, unverified evidence]
```

Report a violation only with a file anchor and the observed evidence. A rule
that *might* be violated somewhere unexamined is a limitation, not a violation.

## Example

The aggregator resolving the specialization for a service change:

```text
Claude Code: /java-engineering-standards purpose: review-generation,
paths: [src/main/java/com/example/orders/pricing/PriceCalculator.java]

Codex: Use $java-engineering-standards for review-generation on
src/main/java/com/example/orders/pricing/PriceCalculator.java.
```

Returns `JAVA_ENGINEERING_STANDARDS_RESULT` with `status: PASS` and a violation
for a `BigDecimal` monetary field compared with `equals` rather than
`compareTo`, anchored at its line. A module path absent from
`project.modules` returns `NEEDS_INPUT` naming the configured list instead of
assuming the module is new.

## Guardrails

- Remain read-only; never edit, stage, or commit.
- Never restate the shared baseline. Reference it; add only what is
  Java- or Spring-specific.
- Never apply a rule from a Spring version the project does not use; check
  `build.java_release` and the declared framework version before citing a
  version-gated feature.
- Never treat a local convention as authority over a correctness, security, or
  contract-compatibility rule — report the conflict.
- Never invent a repository convention or a violation without a file anchor.
