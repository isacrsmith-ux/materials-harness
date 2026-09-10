#!/bin/bash
# Remove the nightly launchd agent. A run already in progress keeps going; stop it with
#   ./uvw run python -m harness stop
set -eo pipefail
LABEL=com.materials-harness.nightly
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
echo "Uninstalled $LABEL."
