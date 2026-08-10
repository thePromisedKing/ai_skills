#!/usr/bin/env bash
# tracker.sh — entry point for every tracker adapter operation.
#
# A thin shim over tracker.py so callers have one stable command and a clear
# error when the Python interpreter the adapters need is absent.
#
#   tracker.sh probe
#   tracker.sh get <id>
#   tracker.sh graph <id>
#   tracker.sh comments <id>
#   tracker.sh attachments <id> <dest-dir>
#   tracker.sh comment <id> <body-file>
#   tracker.sh transitions <id>
#   tracker.sh transition <id> <target-name>
#
# Credentials are read from the environment variables named in
# .ai-skills/config.yml. Never pass one as an argument: arguments are visible in
# process listings and shell history.
#
# Exit status: 0 success, 3 UNSUPPORTED for this adapter, 4 credentials absent,
# 5 remote error, 2 usage error.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  cat >&2 <<'MSG'
error: python3 is required by the tracker adapters and was not found on PATH.
       Install Python 3.9 or newer, or set tracker.adapter to `file` or `none`
       in .ai-skills/config.yml, which need no interpreter.
MSG
  exit 5
fi

exec python3 "${HERE}/tracker.py" "$@"
