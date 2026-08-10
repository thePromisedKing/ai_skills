#!/usr/bin/env bash
# suite-contract-test.sh — structural and contract-text regression checks for
# the ai-skills suite.
#
# WHAT THIS PROVES: that the suite is internally consistent — frontmatter is
# valid, every referenced file exists, the gate roster agrees across the four
# places that name it, terminology has not drifted, and no skill inlines a rule
# another owns.
#
# WHAT THIS DOES NOT PROVE: that any skill behaves correctly. This is not a
# behavioral evaluation and must never be reported as one. See
# skills-manager/references/skill-authoring-standards.md § Eval.
#
# Usage:
#   tests/suite-contract-test.sh            run every check
#   tests/suite-contract-test.sh -v         also print each passing check
#
# Exit status: 0 all checks passed, 1 one or more failed.
set -uo pipefail

SUITE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERBOSE=false
[ "${1:-}" = "-v" ] && VERBOSE=true

PASS=0
FAIL=0
CURRENT_SECTION=""

section() { CURRENT_SECTION="$1"; printf '\n== %s ==\n' "$1"; }
ok()   { PASS=$((PASS+1)); $VERBOSE && printf '  ok    %s\n' "$1"; return 0; }
bad()  { FAIL=$((FAIL+1)); printf '  FAIL  %s\n' "$1"; return 0; }

# Skills exempt from the progress-checklist requirement, per the authoring
# standards: read-only single-evaluation skills and pure reference material.
CHECKLIST_EXEMPT="engineering-standards java-engineering-standards test-engineering-standards workflow-contracts"

# workflow-contracts is reference material with no invocation of its own, so it
# carries no worked example. Every other skill must show both vendor forms.
EXAMPLE_EXEMPT="workflow-contracts"

# The closed gate roster. Every place that names a gate must name exactly these.
GATES="format checkstyle pmd spotbugs errorprone coverage archunit sonar semgrep trivy dependency_check"

skill_dirs=()
while IFS= read -r d; do skill_dirs+=("$d"); done < <(
  find "$SUITE" -mindepth 2 -maxdepth 2 -name SKILL.md -exec dirname {} \; | sort
)

if [ "${#skill_dirs[@]}" -eq 0 ]; then
  echo "FAIL: no skills found under ${SUITE}" >&2
  exit 1
fi

frontmatter() { sed -n '/^---$/,/^---$/p' "$1"; }
field() { frontmatter "$1" | grep -m1 "^$2:" | sed "s/^$2:[[:space:]]*//"; }

# --------------------------------------------------------------------------
section "Frontmatter"
# --------------------------------------------------------------------------
for dir in "${skill_dirs[@]}"; do
  name="$(basename "$dir")"
  skill="${dir}/SKILL.md"

  [ "$(head -1 "$skill")" = "---" ] \
    && ok "${name}: frontmatter opens the file" \
    || bad "${name}: SKILL.md must start with '---'"

  declared="$(field "$skill" name)"
  [ "$declared" = "$name" ] \
    && ok "${name}: name matches directory" \
    || bad "${name}: frontmatter name is '${declared}', expected '${name}'"

  case "$name" in
    *claude*|*anthropic*) bad "${name}: 'claude' and 'anthropic' are reserved in a skill name" ;;
    *) ok "${name}: name uses no reserved word" ;;
  esac

  desc="$(field "$skill" description)"
  if [ -z "$desc" ]; then
    bad "${name}: description is missing"
  else
    len=${#desc}
    [ "$len" -le 1024 ] \
      && ok "${name}: description is ${len} chars" \
      || bad "${name}: description is ${len} chars, over the 1024 limit"
    case "$desc" in
      *"<"*|*">"*) bad "${name}: description contains angle brackets" ;;
      *) ok "${name}: description has no angle brackets" ;;
    esac
    # Must say when to use it, not only what it does.
    if printf '%s' "$desc" | grep -qi 'use \(when\|whenever\|it\|this\|directly\|before\|for\)'; then
      ok "${name}: description states when to use the skill"
    else
      bad "${name}: description states capability but never when to use it"
    fi
  fi
done

# --------------------------------------------------------------------------
section "Structure"
# --------------------------------------------------------------------------
for dir in "${skill_dirs[@]}"; do
  name="$(basename "$dir")"
  skill="${dir}/SKILL.md"

  lines="$(wc -l < "$skill" | tr -d ' ')"
  [ "$lines" -le 500 ] \
    && ok "${name}: SKILL.md is ${lines} lines" \
    || bad "${name}: SKILL.md is ${lines} lines, over the ~500 guidance"

  grep -q '^## Guardrails' "$skill" \
    && ok "${name}: has a Guardrails section" \
    || bad "${name}: has no Guardrails section"

  case " ${EXAMPLE_EXEMPT} " in
    *" ${name} "*)
      ok "${name}: reference-only skill, worked example not required" ;;
    *)
      grep -q 'Claude Code: /' "$skill" && grep -q 'Codex: Use \$' "$skill" \
        && ok "${name}: example gives both vendor forms" \
        || bad "${name}: example must give both 'Claude Code: /' and 'Codex: Use \$' forms" ;;
  esac

  case " ${CHECKLIST_EXEMPT} " in
    *" ${name} "*)
      grep -q '^## Progress checklist' "$skill" \
        && bad "${name}: is checklist-exempt but carries one" \
        || ok "${name}: correctly exempt from the progress checklist" ;;
    *)
      grep -q '^## Progress checklist' "$skill" \
        && ok "${name}: carries a progress checklist" \
        || bad "${name}: multi-phase skill with no progress checklist" ;;
  esac

  # Empty reference/script directories are leftovers, not structure.
  for sub in references scripts; do
    if [ -d "${dir}/${sub}" ] && [ -z "$(ls -A "${dir}/${sub}" 2>/dev/null)" ]; then
      bad "${name}: ${sub}/ exists but is empty"
    fi
  done
done

# --------------------------------------------------------------------------
section "References resolve"
# --------------------------------------------------------------------------
for dir in "${skill_dirs[@]}"; do
  name="$(basename "$dir")"
  while IFS= read -r ref; do
    [ -n "$ref" ] || continue
    # A path with a slash before 'references' is owned by another skill.
    if [[ "$ref" == */references/* ]]; then
      target="${SUITE}/${ref}"
    else
      target="${dir}/${ref}"
    fi
    [ -f "$target" ] \
      && ok "${name}: ${ref} resolves" \
      || bad "${name}: references ${ref}, which does not exist"
  done < <(grep -ohE '[A-Za-z0-9_/-]*references/[a-z0-9-]+\.md' "${dir}/SKILL.md" | sort -u)

  while IFS= read -r scr; do
    [ -n "$scr" ] || continue
    # A path with a slash before 'scripts' is owned by another skill.
    if [[ "$scr" == */scripts/* ]]; then
      target="${SUITE}/${scr}"
    else
      target="${dir}/${scr}"
    fi
    if [ -f "$target" ]; then
      [ -x "$target" ] \
        && ok "${name}: ${scr} resolves and is executable" \
        || bad "${name}: ${scr} exists but is not executable"
    else
      bad "${name}: references ${scr}, which does not exist"
    fi
  done < <(grep -ohE '[A-Za-z0-9_/-]*scripts/[a-z0-9_.-]+\.(sh|py)' "${dir}/SKILL.md" | sort -u)
done

# --------------------------------------------------------------------------
section "Reference files"
# --------------------------------------------------------------------------
while IFS= read -r ref; do
  rel="${ref#"$SUITE"/}"
  lines="$(wc -l < "$ref" | tr -d ' ')"
  if [ "$lines" -gt 100 ]; then
    head -40 "$ref" | grep -q '^## Contents' \
      && ok "${rel}: ${lines} lines, opens with Contents" \
      || bad "${rel}: ${lines} lines but no '## Contents' in the first 40 lines"
  else
    ok "${rel}: ${lines} lines, Contents not required"
  fi
done < <(find "$SUITE" -path '*/references/*.md' | sort)

# --------------------------------------------------------------------------
section "Gate roster agrees everywhere"
# --------------------------------------------------------------------------
template="${SUITE}/config/ai-skills.example.yml"
schema="${SUITE}/project-config/references/config-schema.md"
resolution="${SUITE}/project-config/references/gate-resolution.md"
probe="${SUITE}/project-config/scripts/probe.sh"

for gate in $GATES; do
  grep -qE "^  ${gate}:" "$template" \
    && ok "template declares ${gate}" \
    || bad "config/ai-skills.example.yml does not declare gate '${gate}'"

  grep -q "\`${gate}\`" "$schema" \
    && ok "schema names ${gate}" \
    || bad "config-schema.md does not name gate '${gate}'"

  grep -q "\`${gate}\`" "$resolution" \
    && ok "gate-resolution names ${gate}" \
    || bad "gate-resolution.md does not name gate '${gate}'"

  grep -q "${gate}" "$probe" \
    && ok "probe.sh handles ${gate}" \
    || bad "probe.sh does not handle gate '${gate}'"
done

# The four effective modes must be spelled identically wherever they appear.
for mode in RUN SKIPPED_DISABLED SKIPPED_UNAVAILABLE BLOCKED_REQUIRED_MISSING; do
  count="$(grep -rl "$mode" "$SUITE" --include='*.md' | wc -l | tr -d ' ')"
  [ "$count" -ge 3 ] \
    && ok "effective mode ${mode} used in ${count} files" \
    || bad "effective mode ${mode} appears in only ${count} files; check for drift"
done

# --------------------------------------------------------------------------
section "Ownership: no skill inlines a rule another owns"
# --------------------------------------------------------------------------
# The lifecycle belongs to workflow-contracts. An engine references it.
for dir in "${skill_dirs[@]}"; do
  name="$(basename "$dir")"
  [ "$name" = "workflow-contracts" ] && continue
  skill="${dir}/SKILL.md"
  if grep -q '^## Phase 0 — Validate and preflight' "$skill"; then
    bad "${name}: inlines Phase 0, which workflow-contracts owns"
  else
    ok "${name}: does not inline the lifecycle phases"
  fi
done

# The authoring standards belong to skills-manager.
for dir in "${skill_dirs[@]}"; do
  name="$(basename "$dir")"
  [ "$name" = "skills-manager" ] && continue
  grep -q 'Trigger, Concise, Freedom, Disclosure, Eval' "${dir}/SKILL.md" \
    && bad "${name}: restates the authoring standards" \
    || ok "${name}: does not restate the authoring standards"
done

# --------------------------------------------------------------------------
section "Cross-references"
# --------------------------------------------------------------------------
readme="${SUITE}/README.md"
for dir in "${skill_dirs[@]}"; do
  name="$(basename "$dir")"
  grep -q "\`${name}\`" "$readme" \
    && ok "README names ${name}" \
    || bad "README.md does not mention skill '${name}'"
done

# Every backticked skill-shaped name in a SKILL.md must be a real skill.
for dir in "${skill_dirs[@]}"; do
  name="$(basename "$dir")"
  while IFS= read -r ref; do
    [ -n "$ref" ] || continue
    [ -d "${SUITE}/${ref}" ] \
      && ok "${name}: refers to existing skill ${ref}" \
      || bad "${name}: refers to '${ref}', which is not a skill in this suite"
  done < <(
    grep -ohE '`(project-config|engineering-standards|java-engineering-standards|test-engineering-standards|tracker-context|requirement-context|architecture-plan|workflow-contracts|spring-workflow|implement-task|quality-gate|security-scan|api-test-workflow|review-pr|fix-pr|skills-manager|quota-handoff)`' \
      "${dir}/SKILL.md" | tr -d '`' | sort -u
  )
done

# --------------------------------------------------------------------------
section "Installer"
# --------------------------------------------------------------------------
init="${SUITE}/init.sh"
[ -x "$init" ] && ok "init.sh is executable" || bad "init.sh is not executable"
grep -q 'RETIRED_SKILLS' "$init" \
  && ok "init.sh carries a RETIRED_SKILLS list" \
  || bad "init.sh has no RETIRED_SKILLS list"
grep -q 'refusing to install the suite into its own source directory' "$init" \
  && ok "init.sh guards against self-install" \
  || bad "init.sh has no self-install guard"

# --------------------------------------------------------------------------
section "Hygiene"
# --------------------------------------------------------------------------
while IFS= read -r md; do
  rel="${md#"$SUITE"/}"
  # Emoji are prohibited in skill text. Match common ranges.
  if LC_ALL=C grep -qP '[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}]' "$md" 2>/dev/null; then
    bad "${rel}: contains an emoji"
  else
    ok "${rel}: no emoji"
  fi
  if grep -qE '\\\\[a-zA-Z]|[A-Za-z]:\\' "$md"; then
    bad "${rel}: contains a backslash or platform-specific path"
  else
    ok "${rel}: uses forward slashes"
  fi
done < <(find "$SUITE" \( -name 'SKILL.md' -o -path '*/references/*.md' \) | sort)

# --------------------------------------------------------------------------
printf '\n----------------------------------------\n'
printf '%d passed, %d failed\n' "$PASS" "$FAIL"
if [ "$FAIL" -gt 0 ]; then
  printf 'This check pins structure and contract text. It is NOT a behavioral evaluation.\n'
  exit 1
fi
printf 'Structural and contract-text checks passed.\n'
printf 'This is NOT a behavioral evaluation; it proves internal consistency only.\n'
exit 0
