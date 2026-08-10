# Simplicity retrospective

One deliberate pass, after integration and before the final gate, asking whether
the thing that got built is bigger than the thing that was needed.

It runs at the end rather than during implementation because complexity
accumulates one defensible decision at a time. Each addition looked justified in
isolation; only the finished diff shows the total.

## The questions

Ask each against the integrated diff, not against the plan:

1. **Would a smaller change satisfy every requirement?** Name it concretely. If
   you cannot describe the smaller version, there probably is not one.
2. **Does every new type, layer, interface, and dependency have a second caller
   or a named concrete benefit?** An abstraction with one implementation and no
   second case in sight is speculation.
3. **Is there duplicated logic that arrived through separate slices?** Parallel
   groups produce this routinely: two groups solve the same sub-problem
   independently.
4. **Is there a configuration option, a flag, or a parameter nobody asked for?**
   Each one is a branch that must be tested in both states, forever.
5. **Did anything get more general than the requirement?** Generality that no
   requirement asked for is cost with no buyer.
6. **Is there code left from an approach that was superseded mid-workflow?**
7. **Does the change fit the surrounding code, or does it introduce a second way
   of doing something the repository already does one way?**

## What to do with an answer

- **No simplification warranted** — record that, with the reasoning. The
  retrospective ran and concluded; that is a real outcome, not a skipped step.
- **A bounded simplification** — one that removes code without changing
  behavior or the selected approach. Present the exact scope, obtain explicit
  approval, then run it as a REFACTOR cycle with the focused tests before and
  after. Rerun this retrospective afterward.
- **A material simplification** — one that changes the approach. That is an
  escalation to `architecture-plan` with the evidence, not a refactor.

## Bounds

- Never revert a workflow-owned commit or replace the chosen approach without
  showing the exact scope and receiving authorization.
- Never simplify by removing a quality control: a test, a validation, an error
  path, an audit record. That is not simplification, it is scope reduction.
- Never simplify unrelated code the change happens to sit near.
- Run it once. A retrospective that keeps finding another improvement has
  stopped being a gate and become a second implementation phase.
