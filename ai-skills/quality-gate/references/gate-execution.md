# Gate execution

What each gate is asked to prove, how to read its output, and the findings worth
acting on. `project-config/references/gate-resolution.md` owns the probes and
the mode arithmetic; this document owns what happens once a gate is `RUN`.

## Contents

- Ordering
- format
- checkstyle
- pmd
- spotbugs
- errorprone
- coverage
- archunit
- sonar
- Reading a report
- What a finding is worth

## Ordering

Run in this order when the roster permits, because each stage makes the next
cheaper to interpret:

1. `format` — a formatting difference otherwise shows up as noise in every
   other gate's line numbers.
2. compile-time gates — `errorprone`, then `checkstyle`, `pmd`, `spotbugs`.
3. `coverage` and `archunit` — both need the tests to run.
4. `sonar` — last, so it analyzes what the others have already cleaned.

`format` is also the only gate whose fix is mechanical and safe to apply
without discussion. Everything below it produces findings a human should see.

## format

**Proves** the change matches the project's formatting rules.

Run the check variant first. On failure, apply the formatter, and stage only the
files the change already owns — a formatter run across an untouched file
produces a diff nobody asked for and buries the real change.

A formatting-only failure is not a finding worth reporting to a reviewer; fix it
and note that it was fixed. A formatter that reformats a file the change did not
touch means the repository was not formatted before, which is a `PRE_EXISTING`
observation for the user, not this change's problem to absorb.

## checkstyle

**Proves** the change follows the project's declared style and structural rules.

Read the XML report. Findings are anchored to a file and line, so classification
against the diff is exact.

Worth acting on: unused imports, missing braces, magic numbers, method and
parameter counts, naming conventions, missing final on parameters where the
project requires it, and import order.

Not worth arguing with: a rule the project chose is a rule. When a Checkstyle
rule genuinely does not apply to a case, that is a suppression with a
justification and an approval — not a reason to edit the rule set inside an
unrelated change.

## pmd

**Proves** the change avoids the project's declared code smells and bug
patterns.

PMD's default rule sets are noisy; a project that runs this gate has a curated
rule set, and that curation is the point. Read the findings against the diff and
treat `INTRODUCED` ones as real.

Highest-value PMD categories for a Spring service: unused private members,
empty catch blocks, `String` concatenation in loops, over-complex methods
(cyclomatic and NPath), missed `equals`/`hashCode` pairs, and closed-resource
violations.

## spotbugs

**Proves** the change does not contain a known bug pattern in the bytecode.

Because it analyzes bytecode, it catches things source-level tools miss:
null-dereference paths the compiler proved reachable, ignored return values,
inconsistent synchronization, and resource leaks on exception paths.

When `include_findsecbugs` is on, it also reports injection, weak-crypto,
and unsafe-deserialization patterns. Those overlap with `security-scan`;
report them once, in whichever gate found them, and cross-reference rather than
duplicating.

SpotBugs has a real false-positive rate on framework-generated and
Lombok-generated code. A false positive needs the concrete contradictory
evidence recorded — not a suppression added quietly because it looked wrong.

## errorprone

**Proves** the change avoids compile-time bug patterns, at build time.

Its findings arrive as compiler errors or warnings, so they are unavoidable
rather than reported. Treat an Error Prone error as a build failure, because
that is what it is.

When `nullaway` is enabled, it enforces nullability annotations across the
configured packages. A NullAway error means the annotation and the code disagree
— fix whichever is wrong. Never silence it by widening a `@Nullable`.

## coverage

**Proves** the tests execute the lines the change added or modified.

Read the JaCoCo XML report and compute coverage for the changed lines only. That
is the number that matters; the project total moves too slowly to say anything
about one change.

- Below `min_changed_line_coverage` is a finding: name the uncovered lines, not
  just the percentage. "Line 88's null branch is uncovered" is actionable;
  "72% versus 80%" is not.
- With `ratchet: true`, a drop in the project total is a finding too.
- Coverage is necessary, not sufficient. Lines executed by a test with no
  meaningful assertion count toward the number and prove nothing — the
  `test-engineering-standards` judgment applies alongside this gate, not
  instead of it.
- Never raise coverage by adding an assertion-free test, and never lower a
  threshold or add an exclusion to pass.

## archunit

**Proves** the change respects the project's architectural boundaries.

These are tests, so they run through the test command with the configured
pattern and report as test failures.

An ArchUnit failure is a design finding, not a style one. The change either
respects the boundary or the boundary needs to change — and changing it is an
explicit decision with an approval, made visible in the diff, not a rule quietly
deleted to get a green build.

When the project has ArchUnit on the classpath but no rules, the gate probes as
missing. That is worth reporting once as an observation: the dependency is doing
nothing.

## sonar

**Proves** the change does not introduce issues the project's Sonar quality
profile flags.

Two rules govern this gate:

- **Staged scope only.** Analyze the exact staged blobs — never the whole
  project. A whole-project scan attributes years of accumulated debt to one
  change and drowns the findings that belong to it.
- **The CLI, not a build-plugin scanner.** The developer CLI analyzes a file set
  without a full build and without publishing to the server.

Read the findings, classify them against the diff, and route `INTRODUCED` ones
to remediation. `NOSONAR` is never used to close a finding.

When the server has no analysis for this branch, some issue metadata is
unavailable. Record that as a `NO_BRANCH_ANALYSIS` limitation; it does not by
itself block the gate.

## Reading a report

- Prefer the machine-readable report — XML, JSON, SARIF — over parsing console
  output. Console formats change between tool versions; report schemas are
  stable.
- Anchor every finding to a file and line, so classification against the diff is
  mechanical rather than a judgment.
- Never read a full report into the transcript. Extract the findings and quote
  the lines that matter.
- A tool that exits non-zero with no parseable report is an `ERROR`, not a set
  of zero findings. Report the exit status and the output.

## What a finding is worth

Rank by what the finding would cost in production, not by the tool's own
severity label:

1. a correctness or security defect on a reachable path;
2. a resource or concurrency problem that appears under load;
3. a contract or compatibility break;
4. a maintainability problem in code that will be read again;
5. a style deviation.

A tool that ranks a naming convention as `MAJOR` and a resource leak as `MINOR`
is describing its own rule weights, not the risk. Report the risk.
