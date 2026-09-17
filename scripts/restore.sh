#!/bin/bash
# Restore a backup made by scripts/backup.sh into an EMPTY directory, and prove it is intact.
#
#   ./scripts/restore.sh backups/harness-20260914-073000.tar.gz ~/restore-test
#
# Uses only macOS built-ins (shasum, tar, sqlite3) — no venv — so it works on a machine that has nothing
# but a fresh clone. Checks the archive against its .sha256, every file against the SHA256SUMS manifest
# inside it, and every database with PRAGMA integrity_check. It never writes into a non-empty directory.
#
# To put a restore live: ./uvw run python -m harness stop, move the project's results/ reports/ config/
# aside (don't delete them until the restored copy has been used), then move the restored ones in.
set -euo pipefail
die() { echo "RESTORE FAILED: $*" >&2; exit 1; }
[ $# -eq 2 ] || { echo "usage: $0 <archive.tar.gz> <empty-target-dir>" >&2; exit 2; }
ARCHIVE="$1"
TARGET="$2"
[ -f "$ARCHIVE" ] || die "no archive at $ARCHIVE"
if [ -e "$TARGET" ] && [ -n "$(ls -A "$TARGET")" ]; then die "$TARGET is not empty"; fi

if [ -f "$ARCHIVE.sha256" ]; then
  want=$(awk '{print $1}' "$ARCHIVE.sha256")
  got=$(shasum -a 256 "$ARCHIVE" | awk '{print $1}')
  [ "$want" = "$got" ] || die "archive checksum mismatch: $got, expected $want"
  echo "archive  sha256 matches $ARCHIVE.sha256"
else
  echo "archive  no .sha256 next to it; relying on the manifest inside"
fi

mkdir -p "$TARGET"
tar -xzf "$ARCHIVE" -C "$TARGET" || die "could not extract $ARCHIVE"
[ -f "$TARGET/SHA256SUMS" ] || die "archive has no SHA256SUMS manifest"
(cd "$TARGET" && shasum -a 256 -c --quiet SHA256SUMS) || die "restored files do not match the manifest"
echo "files    $(wc -l < "$TARGET/SHA256SUMS" | tr -d ' ') restored, every one matches SHA256SUMS"

while IFS= read -r db; do
  r=$(sqlite3 "$db" "PRAGMA integrity_check;" 2>&1) || die "cannot open ${db#"$TARGET"/}: $r"
  [ "$r" = ok ] || die "${db#"$TARGET"/} integrity_check: $(echo "$r" | head -3)"
  echo "database ${db#"$TARGET"/}: integrity_check ok"
done < <(find "$TARGET" -name '*.sqlite' -type f | sort)

R="$TARGET/results/results.sqlite"
Q="$TARGET/results/queue.sqlite"
[ -f "$R" ] && echo "results  $(sqlite3 "$R" 'SELECT COUNT(*) FROM jobs') job rows, $(sqlite3 "$R" 'SELECT COUNT(*) FROM results') result rows"
[ -f "$Q" ] && echo "queue    $(sqlite3 "$Q" "SELECT group_concat(status || ' ' || n, ', ') FROM (SELECT status, COUNT(*) AS n FROM queue GROUP BY status)")"
echo "RESTORE OK -> $TARGET"
