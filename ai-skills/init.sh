#!/usr/bin/env bash
# init.sh — install/refresh the ai-skills suite into a target repository.
#
# This script lives in the ai-skills source directory but operates on the
# repository you run it from, so one checkout of the suite can equip many
# projects. It installs into BOTH .claude/skills (Claude Code) and
# .agents/skills (OpenAI Codex CLI) so either vendor can be used
# interchangeably — e.g. when one vendor's quota is exhausted.
#
# Usage, from the root of the target repository:
#   /path/to/ai-skills/init.sh                 install or refresh
#   /path/to/ai-skills/init.sh --check         report drift, change nothing
#   /path/to/ai-skills/init.sh --write-config  create .ai-skills/config.yml
#   /path/to/ai-skills/init.sh --install-hooks enable the post-merge notice
#   /path/to/ai-skills/init.sh --target DIR    install into DIR instead of cwd
#
# It configures no git hooks and runs no quality gate unless asked. The
# installed skills invoke their gates explicitly.
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_ROOT=""
MODE="install"
INSTALL_HOOKS=false
WRITE_CONFIG=false

while [ "$#" -gt 0 ]; do
  case "$1" in
    --check)         MODE="check" ;;
    --write-config)  WRITE_CONFIG=true ;;
    --install-hooks) INSTALL_HOOKS=true ;;
    --target)
      shift
      [ "$#" -gt 0 ] || { echo "error: --target needs a directory." >&2; exit 2; }
      TARGET_ROOT="$1"
      ;;
    -h|--help)
      sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "error: unknown argument '$1'. See --help." >&2
      exit 2
      ;;
  esac
  shift
done

if [ -z "$TARGET_ROOT" ]; then
  if TARGET_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
    :
  else
    TARGET_ROOT="$PWD"
    echo "note: not inside a git repository; installing into ${TARGET_ROOT}" >&2
  fi
fi

if [ ! -d "$TARGET_ROOT" ]; then
  echo "error: target '${TARGET_ROOT}' is not a directory." >&2
  exit 2
fi
TARGET_ROOT="$(cd "$TARGET_ROOT" && pwd)"

if [ "$SRC_DIR" = "$TARGET_ROOT" ]; then
  echo "error: refusing to install the suite into its own source directory." >&2
  exit 2
fi

# --- Collect the tracked skills -------------------------------------------
shopt -s nullglob
skill_dirs=()
for candidate in "$SRC_DIR"/*/; do
  [ -f "${candidate}SKILL.md" ] && skill_dirs+=("$candidate")
done
shopt -u nullglob

if [ "${#skill_dirs[@]}" -eq 0 ]; then
  echo "error: no skill folders found under '${SRC_DIR}/'." >&2
  exit 1
fi

TARGETS=(".claude" ".agents")
# Skills removed from the suite. Listed so a stale local install cannot shadow
# the current owner of a lifecycle. Append here when retiring a skill.
RETIRED_SKILLS=(jira-ticket react-testing)

target_is_current() {
  local dest_skills="${TARGET_ROOT}/$1/skills"
  local skill_path skill_name dest_path retired required_executable

  [ -d "$dest_skills" ] || return 1
  for skill_path in "${skill_dirs[@]}"; do
    skill_name="$(basename "$skill_path")"
    dest_path="${dest_skills}/${skill_name}"
    [ -d "$dest_path" ] || return 1
    diff -qr "$skill_path" "$dest_path" >/dev/null 2>&1 || return 1
    while IFS= read -r required_executable; do
      [ -x "$required_executable" ] || return 1
    done < <(find "$dest_path" -type f \( -name "*.sh" -o -name "*.py" \))
  done
  for retired in "${RETIRED_SKILLS[@]:-}"; do
    [ -n "$retired" ] || continue
    [ ! -d "${dest_skills}/${retired}" ] || return 1
  done
  return 0
}

drift_report() {
  local dest_skills="${TARGET_ROOT}/$1/skills"
  local skill_path skill_name stale=()

  if [ ! -d "$dest_skills" ]; then
    echo "$1: not installed"
    return 1
  fi
  for skill_path in "${skill_dirs[@]}"; do
    skill_name="$(basename "$skill_path")"
    if ! diff -qr "$skill_path" "${dest_skills}/${skill_name}" >/dev/null 2>&1; then
      stale+=("$skill_name")
    fi
  done
  if [ "${#stale[@]}" -eq 0 ]; then
    echo "$1: in sync"
    return 0
  fi
  echo "$1: stale -> ${stale[*]}"
  return 1
}

if [ "$MODE" = "check" ]; then
  status=0
  for target in "${TARGETS[@]}"; do
    drift_report "$target" || status=1
  done
  [ "$status" -eq 0 ] || echo "Run this script without --check to refresh, then restart the agent."
  exit "$status"
fi

# --- Serialize concurrent installs into the same target --------------------
repo_key="$(printf '%s' "$TARGET_ROOT" | cksum | awk '{print $1}')"
lock_dir="${TMPDIR:-/tmp}/ai-skills-init-${repo_key}.lock"
if ! mkdir "$lock_dir" 2>/dev/null; then
  echo "error: another init.sh is already running for ${TARGET_ROOT}." >&2
  exit 1
fi
printf '%s\n' "$$" > "${lock_dir}/pid"
trap 'rm -f "${lock_dir}/pid"; rmdir "$lock_dir" 2>/dev/null || true' EXIT

backup_target() {
  local dest_root="$1" backup_dir="$1.backup" staging_root staging_copy
  case "$(basename "$dest_root")" in
    .claude|.agents) ;;
    *) echo "error: refusing to back up unexpected target '${dest_root}'." >&2; exit 1 ;;
  esac
  staging_root="$(mktemp -d "${TMPDIR:-/tmp}/ai-skills-backup.XXXXXX")"
  staging_copy="${staging_root}/snapshot"
  cp -R "$dest_root" "$staging_copy"
  rm -rf "$backup_dir"
  mv "$staging_copy" "$backup_dir"
  rmdir "$staging_root"
  echo "  Backed up ${dest_root}/ -> ${backup_dir}/"
}

install_into() {
  local name="$1"
  local dest_root="${TARGET_ROOT}/${name}"
  local dest_skills="${dest_root}/skills"
  local skill_path skill_name dest_path retired retired_path

  if target_is_current "$name"; then
    echo "  already current; skipping."
    return
  fi

  [ -d "$dest_root" ] && backup_target "$dest_root"
  mkdir -p "$dest_skills"

  for skill_path in "${skill_dirs[@]}"; do
    skill_name="$(basename "$skill_path")"
    dest_path="${dest_skills}/${skill_name}"
    if [ -d "$dest_path" ]; then
      rm -rf "$dest_path"
      echo "  replaced: ${skill_name}"
    else
      echo "  installed: ${skill_name}"
    fi
    cp -R "$skill_path" "$dest_path"
    find "$dest_path" -type f \( -name "*.sh" -o -name "*.py" \) -exec chmod +x {} \;
  done

  for retired in "${RETIRED_SKILLS[@]:-}"; do
    [ -n "$retired" ] || continue
    retired_path="${dest_skills}/${retired}"
    if [ -d "$retired_path" ]; then
      rm -rf "$retired_path"
      echo "  removed retired: ${retired}"
    fi
  done
}

echo "Source: ${SRC_DIR}"
echo "Target: ${TARGET_ROOT}"
echo
for target in "${TARGETS[@]}"; do
  echo "== ${target} =="
  install_into "$target"
  echo
done

# --- Project configuration -------------------------------------------------
config_path="${TARGET_ROOT}/.ai-skills/config.yml"
if [ "$WRITE_CONFIG" = true ]; then
  if [ -f "$config_path" ]; then
    echo "config: ${config_path} already exists; left unchanged."
  else
    mkdir -p "$(dirname "$config_path")"
    cp "${SRC_DIR}/config/ai-skills.example.yml" "$config_path"
    echo "config: wrote ${config_path} from the template — edit it before the first task."
  fi
elif [ ! -f "$config_path" ]; then
  echo "config: ${config_path} is absent."
  echo "        Run with --write-config to create it from the annotated template."
  echo "        Skills return NEEDS_INPUT until it exists and validates."
fi

# --- Optional drift hook ---------------------------------------------------
if [ "$INSTALL_HOOKS" = true ]; then
  hooks_dir="${TARGET_ROOT}/.githooks"
  mkdir -p "$hooks_dir"
  cat > "${hooks_dir}/post-merge" <<HOOK
#!/usr/bin/env bash
# Reports when the installed ai-skills differ from their source.
set -euo pipefail
SUITE="${SRC_DIR}"
[ -x "\${SUITE}/init.sh" ] || exit 0
"\${SUITE}/init.sh" --check >/dev/null 2>&1 && exit 0
echo "ai-skills: installed copies are stale. Refresh with:"
echo "  \${SUITE}/init.sh"
echo "Then restart Claude Code / Codex CLI."
HOOK
  chmod +x "${hooks_dir}/post-merge"
  git -C "$TARGET_ROOT" config core.hooksPath .githooks
  echo "hooks: core.hooksPath=.githooks; post-merge now reports ai-skills drift."
fi

echo
echo "Installed ${#skill_dirs[@]} skills:"
for skill_path in "${skill_dirs[@]}"; do
  echo "  - $(basename "$skill_path")"
done
echo
echo "Restart Claude Code / Codex CLI in ${TARGET_ROOT} for the skills to load."
