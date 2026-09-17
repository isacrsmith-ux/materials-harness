#!/bin/bash
# Remove a launchd agent installed by install_schedule.sh.
#   ./scripts/uninstall_schedule.sh           the nightly run (a run in progress keeps going; stop it with
#                                             ./uvw run python -m harness stop)
#   ./scripts/uninstall_schedule.sh backup    the nightly backup (existing archives are kept)
set -eo pipefail
case "${1:-nightly}" in
  nightly|backup) LABEL="com.materials-harness.${1:-nightly}" ;;
  *) echo "usage: $0 [nightly|backup]" >&2; exit 2 ;;
esac
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
echo "Uninstalled $LABEL."
