#!/bin/bash
# Launch the unattended runner, kept awake with `caffeinate -ims`, logging to logs/<timestamp>.log.
#
#   ./run_unattended.sh [polite|full] [runner options]    background (nohup): closing the terminal does not stop it
#   ./run_unattended.sh --foreground full --stop-at 07:00  foreground (used by the launchd agent)
#
# Runner options: --stop-at HH:MM, --max-jobs N, --queue-db PATH, --power-poll SECONDS, --workers N
# Status:  ./uvw run python -m harness status
# Stop:    ./uvw run python -m harness stop      (finishes running jobs, then exits)
set -eo pipefail
cd "$(dirname "$0")"

FOREGROUND=0
if [ "${1:-}" = "--foreground" ]; then FOREGROUND=1; shift; fi
MODE=polite
if [ "${1:-}" = "polite" ] || [ "${1:-}" = "full" ]; then MODE="$1"; shift; fi

mkdir -p logs
TS="$(date +%Y%m%d-%H%M%S)"
LOG="logs/${TS}.log"
CMD=(caffeinate -ims ./uvw run --quiet python -m harness unattended --mode "$MODE" "$@")

if [ "$FOREGROUND" = 1 ]; then
  echo "[$TS] foreground unattended run, mode=$MODE, log $LOG"
  exec "${CMD[@]}" >>"$LOG" 2>&1 </dev/null
fi

nohup "${CMD[@]}" >>"$LOG" 2>&1 </dev/null &
PID=$!
echo "$PID" > logs/unattended.pid
echo "Started unattended runner (mode=$MODE; caffeinate pid $PID)."
echo "  log:    $LOG"
echo "  status: ./uvw run python -m harness status"
echo "  stop:   ./uvw run python -m harness stop   (finishes running jobs first)"
