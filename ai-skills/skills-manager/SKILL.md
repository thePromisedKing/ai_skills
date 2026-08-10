---
name: skills-manager
description: Govern every change to this skill suite — creating, splitting, merging, retiring, or materially changing a skill, adding a tracker adapter or a quality gate, or capturing a convention so an agent repeats it. Perform suite-fit analysis for collisions, duplication, contradictions, and reuse, obtain human approval at the decision points, plan validation, and sweep the consumers a contract change affects. Use whenever someone asks to add a command, build a reusable workflow, teach a convention permanently, automate something for next time, or edit any file in the suite — even when they do not say the word "skill".
---

# Skills manager
Never assume a material input or interpretation; return `NEEDS_INPUT` and request explicit confirmation.

Own changes to this suite. A skill is not a prompt someone writes once: it is
selected by a model from many candidates, loaded progressively, and depended on
by siblings that will not be re-read when it changes. Authoring one from a fresh
prompt produces overlap, contradiction, and silent drift.

The most common correct outcome of this skill is **extend an existing owner
rather than create a new skill.** Let the analysis reach that conclusion; do not
pre-empt it in either direction.

## Progress checklist

Copy this checklist and check off each item as it completes:

```text
- [ ] 1 Request classified and the real need stated
- [ ] 2 Suite-fit analysis complete: collisions, duplication, reuse
- [ ] 3 Recommendation presented; user chose the shape
- [ ] 4 Change authored against the authoring standards
- [ ] 5 Consumer sweep complete; every affected sibling updated
- [ ] 6 Validation planned and run; contract test passing
```

## Recognize the request

Route here even when the word "skill" never appears. All of these are suite
changes:

- add a command or a slash command;
- build a reusable prompt or workflow;
- capture a procedure so it can be repeated;
- teach the agent a convention permanently;
- automate something "for next time";
- add a tracker adapter, a quality gate, or a configuration field;
- change anything under the suite directory.

Propose it explicitly — "this belongs in `skills-manager`, shall I start there?"
— rather than writing a `SKILL.md` first and governing it afterward.

## Phase 1 — Classify the need

State what the request actually needs, separately from the form it arrived in.
"Add a command that runs the tests and posts the results" may be a new skill, a
mode on an existing one, a reference section, or nothing at all because the
agent already does it well without instruction.

Ask what the model cannot infer. A skill's whole value is the project's
contracts, ownership, gates, and conventions; instructions restating general
knowledge are noise that costs context on every load.

## Phase 2 — Suite-fit analysis

Mandatory, and reported in full. Read every existing `SKILL.md` description —
that is what the model selects on — and answer:

| Dimension | Question |
| --- | --- |
| **Collision** | Would this description compete with a sibling's for selection? Which one wins, and is that right? |
| **Duplication** | Does an existing skill already own this? Naming a rule twice guarantees they diverge. |
| **Contradiction** | Does this contradict a rule a sibling states? Two contradicting contracts is worse than one imperfect one. |
| **Reuse** | Can an existing owner be extended — a new mode, a new reference, a new section? |
| **Splitting** | Is an existing skill doing two jobs, so this belongs in a split rather than a third skill? |
| **Ownership** | Who owns the new rule, and which skills must reference rather than restate it? |

A change that adds a rule already owned elsewhere is rejected with the owner
named, not accepted with a note.

## Phase 3 — Recommend and stop

Present the analysis and a recommendation:

- extend an existing skill;
- add a reference to an existing skill;
- create a new skill;
- split an existing skill;
- merge two;
- retire one;
- do nothing, because the model already handles this.

The last is a real recommendation and should be given when it is true. An
instruction that changes no outcome is cost with no benefit.

Stop for the user's choice. The shape of the change is theirs.

## Phase 4 — Author

Read `references/skill-authoring-standards.md` completely and hold the change to
it: the trigger description, conciseness, freedom matched to fragility,
progressive disclosure, evaluations, output contracts, checklists, terminology,
and the anti-patterns.

Never copy that document's prose into a skill. Duplicated authoring text is
itself a violation.

## Phase 5 — Sweep the consumers

A contract change is not done when its owner is edited. Find every skill that
references the changed contract and update it in the same change:

- skills that invoke the changed skill and depend on its result shape;
- skills that name it in a guardrail or a routing table;
- the suite `README.md` routing table;
- `config/ai-skills.example.yml` and
  `project-config/references/config-schema.md`, when a configuration field
  changed;
- `project-config/scripts/probe.sh`, when a gate changed;
- `tests/suite-contract-test.sh` pins.

Retiring a skill also adds its name to `RETIRED_SKILLS` in `init.sh`, so a stale
installed copy cannot shadow its replacement.

A partial sweep leaves the suite internally inconsistent, which is the failure
mode that is hardest to notice and most expensive to debug.

## Phase 6 — Validate

Run `tests/suite-contract-test.sh`. It pins structure and contract text.

State plainly what that proves and what it does not: it is a structural
regression layer, not a behavioral evaluation. Where the change alters a
governance contract, also run a representative prompt through the changed skill
and judge it against its result contract, and record that forward test with its
outcome.

Do not claim evaluations the suite does not have. Recording an absent baseline
as a limitation is correct; implying coverage is not.

## Result

```yaml
SKILLS_MANAGER_RESULT:
  status: PASS | NEEDS_INPUT | BLOCKED
  request: what was asked, and the need behind it
  suite_fit: {collisions, duplication, contradictions, reuse, splitting, ownership}
  recommendation: {shape, reasoning}
  chosen: {shape, approver}
  changes: [path, what changed]
  consumer_sweep: [path, why it was affected, what changed]
  validation: {contract_test, forward_test, what each proved}
  limitations: [absent baseline, untested model class]
```

## Example

A request that turns out not to need a new skill:

```text
Claude Code: /skills-manager add a command that checks migrations are
re-executable before I commit

Codex: Use $skills-manager to add a command checking migration
re-executability before commit.
```

The analysis finds `java-engineering-standards` already owns the re-executable
migration rule and `spring-workflow` already checks version collisions at
Phase 3. The recommendation is to extend the engine's Phase 3 check rather than
add a skill that would compete with `quality-gate` for selection. Returns
`NEEDS_INPUT` awaiting the user's choice of shape.

## Guardrails

- Never author a skill directly from a fresh prompt; the analysis comes first.
- Never create a new skill when extending an existing owner would do.
- Never state a rule a sibling already owns; reference it.
- Never edit a skill without sweeping its consumers in the same change.
- Never use `claude` or `anthropic` in a skill name; both are reserved.
- Never claim an evaluation the suite did not run.
- Never leave a retired skill out of `init.sh`'s `RETIRED_SKILLS`.
- Never change a contract and its test pin in a way that makes the test agree
  with a change it was meant to check.
