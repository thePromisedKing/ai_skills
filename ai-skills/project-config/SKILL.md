---
name: project-config
description: Resolve, validate, and publish the project's ai-skills configuration — tracker adapter, requirement sources, branch and commit rules, build tool, and the quality-gate roster with each gate's effective mode. Use whenever a skill needs a build command, a protected-branch list, a commit subject, a tracker adapter, a requirement source path, or the answer to whether a specific gate must run, may run, or is disabled. Every other skill in this suite reads project settings through this owner and never hard-codes them.
---

# Project config
Never assume a material input or interpretation; return `NEEDS_INPUT` and request explicit confirmation.

Own every project-specific value in the suite. Read `.ai-skills/config.yml`,
validate it, probe the environment for the tools it names, and return one
resolved contract. Remain read-only: never create, edit, or repair the
configuration file.

## Progress checklist

Copy this checklist and check off each item as it completes:

```text
- [ ] 1 Configuration located and schema-validated
- [ ] 2 Build tool and commands resolved
- [ ] 3 Gate roster resolved against probed tool availability
- [ ] 4 Code graph resolved, or recorded absent
- [ ] 5 PROJECT_CONFIG_RESULT returned with limitations recorded
```

## Invocation

Accept:

```yaml
caller: <invoking skill> | direct
need: [full | build | gates | tracker | requirements | branches | commit]
gate_ids: [optional subset when need includes gates]
repo_root: absolute path; defaults to the git top level
```

`need: [full]` is the default. A caller that needs only one section requests it
so the result stays small.

## Resolve

1. Locate `<repo_root>/.ai-skills/config.yml`. If it is absent, return
   `NEEDS_INPUT` naming the exact path and the command that creates it from the
   template (`<suite>/init.sh --write-config`). Never synthesize a default
   configuration and never proceed from the example file in the suite source.
2. Read `references/config-schema.md` and validate every requested section.
   Report each violation as `[field, problem, accepted values]`. A placeholder
   left from the template — `example.com` hosts, `project_id: 0`, an unedited
   `project.name` — is a validation failure, not a value.
3. Resolve the build tool. When `build.tool` is `auto`, detect it from the
   repository: `mvnw`/`pom.xml` means maven, `gradlew`/`build.gradle[.kts]`
   means gradle. Both present or neither present is `NEEDS_INPUT`; never pick.
   Derive the command set from the detected tool, then apply any non-null
   override in `build.commands` verbatim.
4. Read `references/gate-resolution.md` and resolve each requested gate to an
   effective mode, using `scripts/probe.sh` for availability. Never claim a tool
   is present without a successful probe, and never mark a gate `RUN` on the
   strength of a build-file mention alone.
5. Resolve the tracker adapter. Validate only the block the selected adapter
   names; ignore the others. Confirm each credential environment variable in
   `credentials_env` is set — report presence as a boolean and never print,
   echo, or log a value.
6. Resolve requirement sources. Record which configured paths exist and which
   are populated. When `requirements.require_sources_populated` is true, an
   empty or missing configured source is `NEEDS_INPUT` naming that path.
7. Resolve `context.code_graph` when the block is present. Probe the tool on
   `PATH` and check the artifact at `code_graph.path`; both must hold for
   `usable: true`. Under `auto`, either one absent is a limitation and the
   result still returns `PASS`. Under `enabled`, it is `BLOCKED`. Never report
   a graph usable without probing it, and never rebuild one — regenerating a
   cache is the caller's decision, not a side effect of reading configuration.

## Result

Return:

```yaml
PROJECT_CONFIG_RESULT:
  status: PASS | NEEDS_INPUT | BLOCKED
  config_path: path
  schema_version: integer
  violations: [field, problem, accepted]
  build:
    tool: maven | gradle
    detected_from: [evidence paths]
    commands: {compile, unit_test, focused_test, verify, full_build}
    java_release: integer
  branches: {default_base, protected, feature_pattern}
  commit: {subject_template, require_stable_subject, trailer}
  tracker:
    adapter: jira | odoo | github | file | none
    settings: <only the selected adapter's block, credentials redacted>
    credentials_present: true | false | not_applicable
  requirements:
    sources: [id, path, exists, populated]
    allow_prompt_only: true | false
  gates:
    - id: <gate>
      configured: enabled | auto | disabled
      effective: RUN | SKIPPED_DISABLED | SKIPPED_UNAVAILABLE | BLOCKED_REQUIRED_MISSING
      tool: name or null
      probe: command and outcome
      settings: <gate-specific block>
  context:
    code_graph:
      mode: auto | enabled | disabled
      usable: true | false
      tool: name or null
      path: path or null
      query_command: template or null
      probe: command and outcome
  parallel: {max_concurrent_groups}
  approvals: {required: [...]}
  limitations: [skipped gate and reason, unpopulated source, unverified probe]
```

Return `NEEDS_INPUT` for a missing file, a failed validation, an ambiguous build
tool, or an unpopulated required source. Return `BLOCKED` only when a gate
configured `enabled` has no available tool — that is a deliberate project
requirement the environment cannot satisfy.

Callers cache this result by config-file fingerprint and repository head, and
reuse it until either changes.

## Example

An engine resolving what it needs before a final gate:

```text
Claude Code: /project-config need: [build, gates]

Codex: Use $project-config with need: [build, gates].
```

Returns `PROJECT_CONFIG_RESULT` with `status: PASS`, the resolved Gradle command
set, and a gate roster in which `sonar` is `SKIPPED_UNAVAILABLE` because the
`sonar` CLI is not on `PATH` — recorded in `limitations`, not treated as a pass.
A project that configured `coverage: {mode: enabled}` with no JaCoCo plugin
returns `BLOCKED` instead, naming the gate and the missing tool.

## Guardrails

- Remain read-only. Never write, repair, migrate, or reformat the configuration.
- Never infer a value the file does not state; an absent required field is
  `NEEDS_INPUT`, not a default.
- Never print, log, echo, or place a credential value in a result, an error, or
  a command line. Report only whether the named variable is set.
- Never mark an unprobed tool available, and never downgrade a gate configured
  `enabled` to a skip.
- Never let a caller's request override a configured mode. A caller may narrow
  which gates it asks about; it may not change their modes.
- Never resolve a tracker block other than the selected adapter's.
