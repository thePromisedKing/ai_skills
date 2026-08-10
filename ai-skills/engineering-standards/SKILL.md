---
name: engineering-standards
description: Apply the canonical engineering baseline for a Java Spring Boot project, aggregate the applicable Java and testing specializations, and provide shared workflow-ledger and agent-routing services. Use when implementation, architecture comparison, pull-request review, gate remediation, skill authoring, or a direct repository task needs consistent design, reuse, boundary-validation, resource-safety, security, observability, performance, testing, code-hygiene, and commit decisions without copying those rules into the caller.
---

# Engineering standards
Never assume a material input or interpretation; return `NEEDS_INPUT` and request explicit confirmation.

Own the read-only policy layer. Callers apply the returned rules inside their own
mutation boundaries; this skill never edits a file.

## Scope

The baseline applies to every target in a Spring Boot repository: production
Java, test code, build configuration, database migrations, and skill authoring
under the suite's own directory. `java` and `test` each have a maintained
specialization. Never apply one specialization's rules as a substitute for
another's.

## Invocation

Accept:

```yaml
caller: spring-workflow | implement-task | architecture-plan | review-pr | fix-pr | quality-gate | security-scan | api-test-workflow | skills-manager | direct
purpose: implementation | review-generation | review-classification | gate-remediation | authoring | routing
target: java | test | build | migration | skills | mixed
paths: [relevant repository paths]
sources:
  authority_order: [highest to lowest]
  locations: [accepted source and repository-instruction paths]
agent_route:
  required: true | false
  role: coordinator | helper | reviewer | file-worker
  preferred_vendor: claude | codex
  fallback_vendor: claude | codex | none
```

`target`, `paths`, and `sources` are required except for `purpose: routing`,
which is routing-only and skips baseline evaluation.

## Apply the baseline

1. Invoke `project-config` for the sections the caller's purpose needs. Its
   resolved values — protected branches, commit subject, build commands, gate
   roster — are authoritative over anything this skill would otherwise infer.
2. Read `references/generic-engineering-standards.md` completely. For a
   stateful multi-phase workflow, also read
   `references/workflow-context-ledger.md` and require its session-isolated
   ledger before any material decision.
3. Read the repository's own instruction files inside the declared scope —
   `CLAUDE.md`, `AGENTS.md`, and any path-scoped component guide. Discover an
   applicable one the caller omitted.
4. Resolve rules in this order:
   - explicit user decisions and caller source authority;
   - `.ai-skills/config.yml` as resolved by `project-config`;
   - repository and path-scoped instructions;
   - this skill's engineering baseline;
   - the nearest maintained code and tests in the repository;
   - generic language or framework guidance.
5. Return same-authority conflicts as unresolved. Never silently choose.
6. Determine the applicable specializations for the declared paths and invoke
   `java-engineering-standards` and `test-engineering-standards` through the
   runtime's skill mechanism. Collect independent read-only specializations
   concurrently when their paths do not overlap. Pass a compact reference to the
   resolved baseline rather than re-embedding it.
7. Produce the applicable checklist, controlling source paths, conflicts,
   limitations, and concrete violations. Do not edit files.

The aggregated result is canonical. A caller invokes this skill rather than
reading, copying, or separately reinvoking a sibling specialization.

## Agent routing

When `agent_route.required` is true, read `references/agent-routing.md` and
execute its authentication, availability, and fallback procedure. Routing
selects a vendor for one bounded role; it never transfers an active workflow.
That is `quota-handoff`, and it is never launched from here.

## Result

Return:

```yaml
ENGINEERING_STANDARDS_RESULT:
  status: PASS | NEEDS_INPUT | BLOCKED
  baseline:
    controlling_sources: [paths]
    applicable_rules: [concise rule and source]
    conflicts: [unresolved same-authority conflicts]
    violations: [path, line, rule, evidence]
  specializations:
    java: <JAVA_ENGINEERING_STANDARDS_RESULT | not_applicable>
    test: <TEST_ENGINEERING_STANDARDS_RESULT | not_applicable>
  project_config_reference: fingerprint of the PROJECT_CONFIG_RESULT used
  workflow_context:
    required: true | false
    ledger_reference: private scratch reference or null
    fingerprint: content fingerprint or null
  agent_route:
    requested: true | false
    vendor: claude | codex | null
    authenticated: true | false
    fallback_reason: concrete signal or null
  limitations: [missing specialization, unverified evidence, disabled approval]
```

Use `NEEDS_INPUT` for an authentication action, an unresolved controlling
choice, or a required specialization that cannot be invoked. Use `BLOCKED` only
when a required route has no authenticated vendor. Never report `PASS` with an
unresolved same-authority conflict.

## Example

A workflow resolving the baseline plus the Java specialization:

```text
Claude Code: /engineering-standards purpose: implementation, target: java,
paths: [src/main/java/com/example/orders/pricing]

Codex: Use $engineering-standards with purpose implementation, target java, and
paths src/main/java/com/example/orders/pricing.
```

Returns `ENGINEERING_STANDARDS_RESULT` with `status: PASS`, the applicable rules,
and `specializations.java` holding the aggregated result; `test` is
`not_applicable`. A repository whose `CLAUDE.md` contradicts
`.ai-skills/config.yml` on the protected-branch list returns `NEEDS_INPUT` with
both locations rather than preferring one.

## Guardrails

- Remain read-only. Never edit, stage, commit, merge, push, or write externally.
- Never invent a repository convention, a configured value, an authentication
  state, or a source rule.
- Never let a generic review lens override a higher-authority contract.
- Never apply one specialization's rules to another target.
- Never duplicate gate execution, quota handoff, implementation, or pull-request
  behavior owned by another skill.
- Never resolve a value `project-config` owns by reading the configuration file
  directly.
