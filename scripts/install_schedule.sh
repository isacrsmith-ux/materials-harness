#!/bin/bash
# Install the optional nightly launchd agent (user agent; no sudo). Times: config/unattended.json.
set -eo pipefail
cd "$(dirname "$0")/.."
LABEL=com.materials-harness.nightly
./uvw run --quiet python -m harness schedule --write
mkdir -p "$HOME/Library/LaunchAgents"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
cp "config/launchd/$LABEL.plist" "$HOME/Library/LaunchAgents/$LABEL.plist"
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/$LABEL.plist"
echo "Installed $LABEL. Inspect with: launchctl print gui/$(id -u)/$LABEL"
