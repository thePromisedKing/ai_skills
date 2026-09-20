# Gate resolution

How a configured gate mode becomes an effective mode, and what each outcome
obliges a caller to do. This is the mechanism that lets one suite serve projects
with very different tooling without ever reporting a pass it did not earn.

## Contents

- The three configured modes
- The four effective modes
- Probing for availability
- Per-gate probes and commands
- What a caller must do with each outcome
- Reporting rules

## The three configured modes

Declared per gate in `.ai-skills/config.yml`:

| Configured | Meaning |
| --- | --- |
| `enabled` | The project requires this gate. A missing tool is a project defect. |
| `auto` | Run it when the tool is present. Its absence is a known, accepted limitation. |
| `disabled` | Never run it. The project has decided this gate does not apply. |

`auto` is the right default for a portable suite: a project that has Sonar gets
the Sonar gate, and one that does not is neither blocked nor silently told its
code passed a scan that never ran.

## The four effective modes

| Effective | Produced when | Blocks? |
| --- | --- | --- |
| `RUN` | configured `enabled` or `auto`, and the probe succeeded | — |
| `SKIPPED_DISABLED` | configured `disabled` | no |
| `SKIPPED_UNAVAILABLE` | configured `auto`, probe failed | no — recorded as a limitation |
| `BLOCKED_REQUIRED_MISSING` | configured `enabled`, probe failed | yes |

There is no fifth outcome. A gate that errored while running is a gate result,
not a mode: it reports `FAIL` with its output through the owning gate skill.

## Probing for availability

A probe answers one question: can this gate actually execute in this
environment, right now. Two things must hold, and both are checked.

1. **The tool is reachable.** For a standalone binary, the executable resolves
   on `PATH`. For a build-integrated analyzer, the build tool exposes the task
   or goal.
2. **Its required configuration exists.** A gate that names a config file —
   Checkstyle, PMD, Semgrep — needs that file present at the configured path.

Both are probed without side effects: no analysis, no network fetch, no cache
population. `scripts/probe.sh` implements the checks below and prints one line
per gate as `<gate>\t<available|missing>\t<evidence>`.

A probe that cannot run at all — the build tool itself is absent — is not a
missing gate. It is `NEEDS_INPUT` from `project-config`, because nothing else in
the workflow can proceed either.

## Per-gate probes and commands

Commands are shown for both build tools. `project-config` substitutes the
detected tool; a non-null override in `build.commands` always wins.

| Gate | Probe | Maven | Gradle |
| --- | --- | --- | --- |
| `format` | spotless plugin declared | `./mvnw spotless:check` / `spotless:apply` | `./gradlew spotlessCheck` / `spotlessApply` |
| `checkstyle` | plugin declared **and** `gates.checkstyle.config` exists | `./mvnw checkstyle:check` | `./gradlew checkstyleMain` |
| `pmd` | plugin declared **and** `gates.pmd.ruleset` exists | `./mvnw pmd:check` | `./gradlew pmdMain` |
| `spotbugs` | plugin declared | `./mvnw spotbugs:check` | `./gradlew spotbugsMain` |
| `errorprone` | compiler plugin configured | part of `compile` | part of `compileJava` |
| `coverage` | jacoco plugin declared | `./mvnw verify` then read `jacoco.xml` | `./gradlew test jacocoTestReport` |
| `archunit` | a test matches `gates.archunit.test_pattern` | `./mvnw test -Dtest=<pattern>` | `./gradlew test --tests <pattern>` |
| `sonar` | `gates.sonar.cli` resolves on `PATH` | CLI, staged scope | CLI, staged scope |
| `semgrep` | `semgrep` on `PATH` | `semgrep --config <config>` | same |
| `trivy` | `trivy` on `PATH` | `trivy fs --scanners <list>` | same |
| `dependency_check` | plugin declared | `./mvnw dependency-check:check` | `./gradlew dependencyCheckAnalyze` |

"Plugin declared" is checked by grepping the build files for the plugin
coordinate — a cheap, side-effect-free signal. It is deliberately weaker than
running the task: a declared plugin that fails on first invocation reports a
gate `FAIL`, which is the correct and visible outcome.

### Front-end gates

These four analyze the tree named by the gate's `root`, not the Java sources,
and run the gate's configured `command` from the repository root. The probe
reads `<root>/package.json` and `<root>/node_modules`; it never installs
anything, so a tree whose dependencies have not been installed probes
`missing` rather than triggering a download mid-workflow.

| Gate | Probe | Command |
| --- | --- | --- |
| `eslint` | `eslint` in `<root>` dependencies **and** `<root>/node_modules/.bin/eslint` present | `gates.eslint.command` |
| `tsc` | `typescript` in `<root>` dependencies **and** `<root>/node_modules/.bin/tsc` present | `gates.tsc.command` |
| `vitest` | `vitest` in `<root>` dependencies **and** `<root>/node_modules/.bin/vitest` present | `gates.vitest.command` |
| `playwright` | `@playwright/test` in `<root>` dependencies **and** `<root>/node_modules/.bin/playwright` present | `gates.playwright.command` |

A declared dependency whose binary is absent is `missing`, not available: an
uninstalled tree would otherwise report a gate that cannot execute as ready to
run.

Sonar is the one gate whose scope is fixed by contract rather than
configuration: it analyzes the staged index only, never the whole project. See
`quality-gate` for why.

## What a caller must do with each outcome

- `RUN` — execute it, capture the command and its result, and treat a failure
  per the owning gate skill's contract.
- `SKIPPED_DISABLED` — record it. No limitation: the project decided this.
- `SKIPPED_UNAVAILABLE` — record it in `limitations` with the gate id, the probe
  that failed, and the risk it leaves uncovered. The workflow continues.
- `BLOCKED_REQUIRED_MISSING` — stop. Report the gate, the probe, and the two
  ways forward: install the tool, or change its mode to `auto` in the project
  configuration. Never resolve this by editing the configuration.

## Reporting rules

- Report every gate in the roster, including the skipped ones. A result that
  lists only the gates that ran reads as full coverage.
- Never aggregate a skip into a pass. "Quality gate passed" is accurate only
  when it is qualified by which gates ran.
- Name the gate by its configured id, so a reader can find it in the project
  configuration without translation.
- A gate's *absence from the configuration* is not a skip — it is a schema
  violation, because the roster is closed.
