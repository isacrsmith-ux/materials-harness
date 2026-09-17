#!/bin/bash
# Timestamped, compressed, verified backup of results/ (every database, copied with SQLite's online backup,
# so it is safe while a run is writing), reports/ and config/. Not models/ or cache/: both re-downloadable.
# .env is not included either — it holds the API key, and a backup may live in a cloud folder.
#
#   ./scripts/backup.sh                    destination: HARNESS_BACKUP_DIR in .env, else backups/ (gitignored)
#   ./scripts/backup.sh --dest /Volumes/External/materials-harness
#
# Each archive gets a .sha256 next to it and a SHA256SUMS manifest inside it, and is re-read after writing.
# Keeps the newest archive of each of the last 7 days and of the last 4 weeks; prunes the rest (only when
# the new archive verified). Warns when the destination is on the project's physical disk.
# Restore: ./scripts/restore.sh <archive> <empty dir>
set -eo pipefail
cd "$(dirname "$0")/.."
echo "[$(date '+%Y-%m-%d %H:%M:%S')] backup"
exec ./uvw run --quiet python -m harness backup "$@"
