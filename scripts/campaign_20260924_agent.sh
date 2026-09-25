#!/bin/bash
# The 2026-09-24 campaign's launchd agent (option (a) of the campaign brief).
#
#   scripts/campaign_20260924_agent.sh install          unload the nightly agent, install + load the campaign agent
#   scripts/campaign_20260924_agent.sh undo             ONE-COMMAND UNDO: restore nightly, remove campaign agent
#   scripts/campaign_20260924_agent.sh restore-nightly  (driver, at finish) reload the nightly agent only
#   scripts/campaign_20260924_agent.sh unload-campaign  (driver, at finish) remove the campaign agent only
#
# Why: com.materials-harness.nightly runs run_unattended.sh with NO HARNESS_MODEL (the second engine) on
# results/queue.sqlite at 23:00. With production-engine campaign jobs pending, that is the SettingsMismatch
# incident again. The campaign agent instead re-invokes scripts/campaign_20260924.py at load and every
# 30 minutes; the driver exits at once if a runner is alive or everything is done.
#
# The nightly plist in ~/Library/LaunchAgents is NEVER edited or deleted: it is booted out and booted back
# in. A byte copy is kept in logs/ and compared at restore.
set -eo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
UID_="$(id -u)"
AGENTS="$HOME/Library/LaunchAgents"
NIGHTLY="com.materials-harness.nightly"
CAMPAIGN="com.materials-harness.campaign"
NPLIST="$AGENTS/$NIGHTLY.plist"
CPLIST="$AGENTS/$CAMPAIGN.plist"
BACKUP="logs/$NIGHTLY.plist.before-campaign-20260924"

write_campaign_plist() {
  cat >"$CPLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key>
	<string>$CAMPAIGN</string>
	<key>EnvironmentVariables</key>
	<dict>
		<key>PATH</key>
		<string>/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin</string>
	</dict>
	<key>ProgramArguments</key>
	<array>
		<string>$ROOT/.venv/bin/python</string>
		<string>$ROOT/scripts/campaign_20260924.py</string>
	</array>
	<key>WorkingDirectory</key>
	<string>$ROOT</string>
	<key>RunAtLoad</key>
	<true/>
	<key>StartInterval</key>
	<integer>1800</integer>
	<key>AbandonProcessGroup</key>
	<true/>
	<key>ProcessType</key>
	<string>Standard</string>
	<key>StandardOutPath</key>
	<string>$ROOT/logs/campaign_20260924.log</string>
	<key>StandardErrorPath</key>
	<string>$ROOT/logs/campaign_20260924.log</string>
</dict>
</plist>
EOF
}

restore_nightly() {
  if [ -f "$BACKUP" ] && ! cmp -s "$BACKUP" "$NPLIST"; then
    echo "nightly plist differs from the pre-campaign copy; restoring the copy" >&2
    cp "$BACKUP" "$NPLIST"
  fi
  launchctl print "gui/$UID_/$NIGHTLY" >/dev/null 2>&1 || launchctl bootstrap "gui/$UID_" "$NPLIST"
  echo "nightly agent loaded: $(launchctl print "gui/$UID_/$NIGHTLY" | grep -m1 'state =' | xargs)"
}

unload_campaign() {
  rm -f "$CPLIST"
  echo "campaign agent removed"
  launchctl bootout "gui/$UID_/$CAMPAIGN" 2>/dev/null || true   # last: this may terminate our caller
}

case "${1:-}" in
  install)
    mkdir -p logs
    [ -f "$BACKUP" ] || cp "$NPLIST" "$BACKUP"
    launchctl bootout "gui/$UID_/$NIGHTLY" 2>/dev/null || true
    echo "nightly agent unloaded (plist kept at $NPLIST)"
    write_campaign_plist
    plutil -lint "$CPLIST"
    launchctl bootout "gui/$UID_/$CAMPAIGN" 2>/dev/null || true
    launchctl bootstrap "gui/$UID_" "$CPLIST"
    echo "campaign agent loaded; it runs the driver now and every 30 minutes"
    ;;
  undo) restore_nightly; unload_campaign ;;
  restore-nightly) restore_nightly ;;
  unload-campaign) unload_campaign ;;
  *) sed -n '2,8p' "$0"; exit 2 ;;
esac
