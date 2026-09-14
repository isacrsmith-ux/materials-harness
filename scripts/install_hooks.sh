#!/usr/bin/env bash
# Install this repository's git hooks.
#
# Hooks live in .git/hooks/, which is not cloned and not tracked, so every contributor has to
# install them once:
#
#   ./scripts/install_hooks.sh
#
# Installs a pre-commit hook that runs scripts/preflight_publish.sh --staged over the staged
# changes (about 0.7 s). Bypass a single commit with:  git commit --no-verify
#
# The same checks run in CI (.github/workflows/secret-scan.yml), so the hook is a convenience
# that catches mistakes before they reach a commit -- not the only line of defence.

set -euo pipefail
cd "$(dirname "$0")/.."

HOOK=".git/hooks/pre-commit"

if [ -e "$HOOK" ] && ! grep -q "scripts/preflight_publish.sh" "$HOOK" 2>/dev/null; then
  echo "A different pre-commit hook is already installed at $HOOK."
  echo "Move it aside and re-run, or merge the two by hand. Nothing was changed."
  exit 1
fi

cat > "$HOOK" <<'HOOK_BODY'
#!/usr/bin/env bash
# Pre-commit secret scan. Installed by scripts/install_hooks.sh.
#
# Runs scripts/preflight_publish.sh --staged, which checks only what is being committed:
# credential patterns, the live MP_API_KEY value, secret-shaped filenames, absolute local
# paths, email addresses, and directories that must never be published. It deliberately
# skips the full-history gitleaks scan so that committing stays fast; CI runs that.
#
# To bypass for one commit:   git commit --no-verify
# To remove entirely:         rm .git/hooks/pre-commit
#
# Hooks are not cloned. .github/workflows/secret-scan.yml runs the same checks on push and
# on pull requests, so a contributor without this hook is still covered.

set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"
SCRIPT="$ROOT/scripts/preflight_publish.sh"

if [ ! -x "$SCRIPT" ]; then
  echo "pre-commit: $SCRIPT is missing or not executable." >&2
  echo "pre-commit: refusing to pass a commit unchecked. Restore it, or use --no-verify." >&2
  exit 1
fi

if ! "$SCRIPT" --staged; then
  echo >&2
  echo "pre-commit: BLOCKED — the staged changes tripped the secret scan above." >&2
  echo "pre-commit: if it is a false positive, commit with --no-verify." >&2
  exit 1
fi
HOOK_BODY

chmod +x "$HOOK"
echo "Installed $HOOK"
echo "Bypass one commit with: git commit --no-verify"
