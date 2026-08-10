#!/usr/bin/env bash
# probe.sh — report which build tool and which quality-gate tools are actually
# available in this repository. Side-effect free: no analysis is run, no cache
# is populated, and nothing is downloaded.
#
# Usage, from the repository root (or with --root):
#   probe.sh                 probe the build tool and every known gate
#   probe.sh --root DIR      probe DIR instead of the current directory
#   probe.sh --gate ID ...   probe only the named gates
#   probe.sh --json          emit JSON instead of TSV
#
# Output, one line per probe:
#   <id>\t<available|missing>\t<evidence>
#
# Exit status is 0 whenever the probes themselves ran. A missing tool is data,
# not an error — the caller decides whether it blocks, per the gate's configured
# mode. Exit 2 means the probe could not run (bad arguments, unreadable root).
set -euo pipefail

ROOT="$PWD"
FORMAT="tsv"
REQUESTED=()

while [ "$#" -gt 0 ]; do
  case "$1" in
    --root) shift; [ "$#" -gt 0 ] || { echo "error: --root needs a directory" >&2; exit 2; }; ROOT="$1" ;;
    --gate) shift; [ "$#" -gt 0 ] || { echo "error: --gate needs an id" >&2; exit 2; }; REQUESTED+=("$1") ;;
    --json) FORMAT="json" ;;
    -h|--help) sed -n '2,16p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "error: unknown argument '$1'" >&2; exit 2 ;;
  esac
  shift
done

[ -d "$ROOT" ] || { echo "error: root '${ROOT}' is not a directory" >&2; exit 2; }
ROOT="$(cd "$ROOT" && pwd)"

RESULTS=()

emit() { RESULTS+=("$1"$'\t'"$2"$'\t'"$3"); }

wanted() {
  [ "${#REQUESTED[@]}" -eq 0 ] && return 0
  local id
  for id in "${REQUESTED[@]}"; do [ "$id" = "$1" ] && return 0; done
  return 1
}

# --- Build files, read once ------------------------------------------------
BUILD_FILES=()
for f in pom.xml build.gradle build.gradle.kts settings.gradle settings.gradle.kts; do
  [ -f "${ROOT}/${f}" ] && BUILD_FILES+=("${ROOT}/${f}")
done
# Multi-module: include one level of child build files so a plugin declared in a
# submodule is still found. Bounded to depth 2 to keep the probe cheap.
while IFS= read -r f; do BUILD_FILES+=("$f"); done < <(
  find "$ROOT" -mindepth 2 -maxdepth 2 \
    \( -name pom.xml -o -name 'build.gradle' -o -name 'build.gradle.kts' \) \
    -not -path '*/build/*' -not -path '*/target/*' 2>/dev/null | head -50
)

build_declares() {
  [ "${#BUILD_FILES[@]}" -gt 0 ] || return 1
  grep -qsE "$1" "${BUILD_FILES[@]}"
}

# --- Build tool ------------------------------------------------------------
maven=false; gradle=false
{ [ -f "${ROOT}/pom.xml" ] || [ -f "${ROOT}/mvnw" ]; } && maven=true
{ [ -f "${ROOT}/build.gradle" ] || [ -f "${ROOT}/build.gradle.kts" ] || [ -f "${ROOT}/gradlew" ]; } && gradle=true

if $maven && $gradle; then
  emit "build" "ambiguous" "both maven and gradle markers present"
  BUILD_TOOL=""
elif $maven; then
  emit "build" "maven" "$( [ -f "${ROOT}/mvnw" ] && echo mvnw || echo pom.xml )"
  BUILD_TOOL="maven"
elif $gradle; then
  emit "build" "gradle" "$( [ -f "${ROOT}/gradlew" ] && echo gradlew || echo build.gradle )"
  BUILD_TOOL="gradle"
else
  emit "build" "missing" "no pom.xml, build.gradle, mvnw, or gradlew"
  BUILD_TOOL=""
fi

# --- Plugin-backed gates ---------------------------------------------------
probe_plugin() {
  local id="$1" pattern="$2" label="$3"
  wanted "$id" || return 0
  if build_declares "$pattern"; then
    emit "$id" "available" "${label} declared in build files"
  else
    emit "$id" "missing" "${label} not declared in build files"
  fi
}

probe_plugin format        'spotless'                                   'spotless plugin'
probe_plugin checkstyle    'checkstyle'                                 'checkstyle plugin'
probe_plugin pmd           '(maven-pmd-plugin|[^a-z]pmd[^a-z]|id .pmd.)' 'pmd plugin'
probe_plugin spotbugs      'spotbugs'                                   'spotbugs plugin'
probe_plugin errorprone    '(errorprone|error_prone)'                   'error-prone compiler plugin'
probe_plugin coverage      'jacoco'                                     'jacoco plugin'
probe_plugin dependency_check 'dependency-check'                        'owasp dependency-check plugin'

# --- ArchUnit: a test must exist, not merely the library -------------------
if wanted archunit; then
  archtests="$(find "$ROOT" -path '*/src/test/*' -name '*ArchTest.java' \
      -not -path '*/build/*' -not -path '*/target/*' 2>/dev/null | head -5)"
  if [ -n "$archtests" ]; then
    emit "archunit" "available" "$(printf '%s' "$archtests" | head -1 | sed "s|^${ROOT}/||")"
  elif build_declares 'archunit'; then
    emit "archunit" "missing" "archunit dependency present but no *ArchTest.java found"
  else
    emit "archunit" "missing" "no archunit dependency and no *ArchTest.java"
  fi
fi

# --- Standalone binaries ---------------------------------------------------
probe_binary() {
  local id="$1" bin="$2"
  wanted "$id" || return 0
  if command -v "$bin" >/dev/null 2>&1; then
    emit "$id" "available" "$(command -v "$bin")"
  else
    emit "$id" "missing" "${bin} not on PATH"
  fi
}

probe_binary sonar   "${SONAR_CLI:-sonar}"
probe_binary semgrep semgrep
probe_binary trivy   trivy

# --- Config files the gates require ---------------------------------------
probe_config() {
  local id="$1" path="$2"
  wanted "$id" || return 0
  [ -n "$path" ] || return 0
  if [ -f "${ROOT}/${path}" ]; then
    emit "${id}_config" "available" "$path"
  else
    emit "${id}_config" "missing" "$path"
  fi
}

probe_config checkstyle "${CHECKSTYLE_CONFIG:-}"
probe_config pmd        "${PMD_RULESET:-}"
probe_config semgrep    "${SEMGREP_CONFIG:-}"

# --- Emit ------------------------------------------------------------------
if [ "$FORMAT" = "json" ]; then
  printf '{"root":"%s","build_tool":"%s","probes":[' "$ROOT" "$BUILD_TOOL"
  first=true
  for line in "${RESULTS[@]}"; do
    IFS=$'\t' read -r id state evidence <<< "$line"
    $first || printf ','
    first=false
    printf '{"id":"%s","state":"%s","evidence":"%s"}' \
      "$id" "$state" "$(printf '%s' "$evidence" | sed 's/\\/\\\\/g; s/"/\\"/g')"
  done
  printf ']}\n'
else
  printf '%s\n' "${RESULTS[@]}"
fi
