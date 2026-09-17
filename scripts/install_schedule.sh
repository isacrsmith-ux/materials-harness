#!/bin/bash
# Install an optional launchd user agent (no sudo). Times: config/unattended.json (schedule).
#   ./scripts/install_schedule.sh           the nightly unattended run (schedule.start / schedule.stop)
#   ./scripts/install_schedule.sh backup    the nightly backup, scripts/backup.sh (schedule.backup)
set -eo pipefail
cd "$(dirname "$0")/.."
case "${1:-nightly}" in
  nightly|backup) LABEL="com.materials-harness.${1:-nightly}" ;;
  *) echo "usage: $0 [nightly|backup]" >&2; exit 2 ;;
esac
./uvw run --quiet python -m harness schedule --write
mkdir -p "$HOME/Library/LaunchAgents"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
cp "config/launchd/$LABEL.plist" "$HOME/Library/LaunchAgents/$LABEL.plist"
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/$LABEL.plist"
echo "Installed $LABEL. Inspect with: launchctl print gui/$(id -u)/$LABEL"
