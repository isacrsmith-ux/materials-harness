#!/usr/bin/env bash
# Pre-publication check: re-runs the scans from reports/publish_audit.md.
#
# Everything this checks was clean at the time of the audit; the point of the script is that it stays
# clean as commits are added. Exits non-zero on the first real finding, so it can be a CI step or a
# pre-commit hook.
#
#   ./scripts/preflight_publish.sh            # scan the working tree and the full history
#   ./scripts/preflight_publish.sh --staged   # scan only what is staged (for a pre-commit hook)
#
# gitleaks, if installed, is used for the history scan as well; without it the built-in patterns run
# alone and the script says so rather than pretending to have covered more than it did.

set -uo pipefail
cd "$(dirname "$0")/.." || exit 2

STAGED=0
[ "${1:-}" = "--staged" ] && STAGED=1
fail=0
note() { printf '  %s\n' "$*"; }
bad()  { printf '  FAIL: %s\n' "$*"; fail=1; }

echo "== 1. secrets in tracked content =="
if [ "$STAGED" = 1 ]; then
  FILES=$(git diff --cached --name-only --diff-filter=ACM)
else
  FILES=$(git ls-files)
fi

# Patterns that indicate a real credential. Kept deliberately narrow: a scanner that cries wolf gets
# switched off. The generic high-entropy rules live in gitleaks, below.
PATTERNS='sk-ant-[A-Za-z0-9_-]{20,}|sk-(proj-)?[A-Za-z0-9_-]{32,}|AIza[0-9A-Za-z_-]{35}|\bhf_[A-Za-z0-9]{30,}|\b(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})|\b(AKIA|ASIA)[0-9A-Z]{16}\b|-----BEGIN [A-Z ]*PRIVATE KEY-----|xox[baprs]-[A-Za-z0-9-]{10,}|(sk|rk)_live_[A-Za-z0-9]{20,}|SG\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}|"type"[[:space:]]*:[[:space:]]*"service_account"|(postgres(ql)?|mysql|mongodb(\+srv)?|redis|amqp)://[^[:space:]'"'"'"]+:[^[:space:]'"'"'"@]+@|https?://[^/[:space:]:@'"'"'"]+:[^/[:space:]:@'"'"'"]+@|MP_API_KEY[[:space:]]*[:=][[:space:]]*['"'"'"]?[A-Za-z0-9]{8,}'

hits=0
for f in $FILES; do
  [ -f "$f" ] || continue
  if grep -nEI "$PATTERNS" "$f" >/dev/null 2>&1; then
    bad "credential pattern in $f"
    grep -nEI "$PATTERNS" "$f" | sed 's/\(.\{100\}\).*/\1…/' | head -3 | sed 's/^/        /'
    hits=$((hits + 1))
  fi
done
[ "$hits" = 0 ] && note "no credential patterns in tracked content ($(echo "$FILES" | wc -w | tr -d ' ') files)"

echo "== 2. the real .env value must never be tracked =="
if [ -f .env ]; then
  KEY=$(awk -F= '/^MP_API_KEY=/{sub(/^MP_API_KEY=/,""); gsub(/["'"'"']/,""); print; exit}' .env)
  if [ -n "$KEY" ]; then
    if git grep -qF -- "$KEY" -- . 2>/dev/null; then bad "the MP_API_KEY value appears in tracked content"
    else note "MP_API_KEY value not in tracked content"; fi
    if [ "$STAGED" = 0 ] && git rev-list --all >/dev/null 2>&1; then
      found=0
      for sha in $(git rev-list --objects --all | awk '{print $1}'); do
        [ "$(git cat-file -t "$sha" 2>/dev/null)" = blob ] || continue
        git cat-file blob "$sha" 2>/dev/null | grep -qF -- "$KEY" && { bad "MP_API_KEY value in history blob $sha"; found=1; }
      done
      [ "$found" = 0 ] && note "MP_API_KEY value not in any history blob"
    fi
  fi
else
  note ".env absent (nothing to compare against)"
fi
git ls-files --error-unmatch .env >/dev/null 2>&1 && bad ".env is TRACKED" || note ".env is not tracked"

echo "== 3. secret-shaped filenames =="
SUSPECT='(^|/)(\.env($|\.)|id_rsa|id_ed25519|id_ecdsa|.*\.pem|.*\.p12|.*\.pfx|.*\.keystore|.*\.jks|service[-_]account.*\.json|terraform\.tfvars|kubeconfig|\.npmrc|\.pypirc|\.netrc)$'
if echo "$FILES" | tr ' ' '\n' | grep -vE '^\.env\.example$' | grep -qE "$SUSPECT"; then
  bad "secret-shaped filename is tracked:"; echo "$FILES" | tr ' ' '\n' | grep -vE '^\.env\.example$' | grep -E "$SUSPECT" | sed 's/^/        /'
else
  note "no secret-shaped filenames tracked (.env.example is the only match and holds empty placeholders)"
fi

echo "== 4. absolute local paths and personal identifiers in tracked files =="
if git grep -nE '/Users/[A-Za-z0-9._-]+|/home/[A-Za-z0-9._-]+|C:\\\\Users\\\\' -- . ':!.gitignore' ':!scripts/preflight_publish.sh' >/dev/null 2>&1; then
  bad "absolute local path in tracked content:"
  git grep -nE '/Users/[A-Za-z0-9._-]+|/home/[A-Za-z0-9._-]+' -- . ':!.gitignore' ':!scripts/preflight_publish.sh' | head -5 | sed 's/^/        /'
else
  note "no absolute local paths"
fi
if git grep -nEI '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' -- . ':!scripts/preflight_publish.sh' 2>/dev/null \
   | grep -viE 'noreply@anthropic|@example\.|users\.noreply\.github' | grep -qE '@'; then
  bad "email address in tracked content:"
  git grep -nEI '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' -- . ':!scripts/preflight_publish.sh' \
    | grep -viE 'noreply@anthropic|@example\.|users\.noreply\.github' | head -5 | sed 's/^/        /'
else
  note "no email addresses (the Co-Authored-By trailer lives in commit messages, not files)"
fi

echo "== 5. directories that must never be published =="
for d in results models cache logs config/launchd .envs .venv; do
  n=$(git ls-files "$d" | wc -l | tr -d ' ')
  if [ "$n" != 0 ]; then bad "$d has $n tracked file(s)"; else note "$d: not tracked"; fi
done

echo "== 6. gitleaks (full history) =="
if command -v gitleaks >/dev/null 2>&1; then
  if gitleaks git --log-opts="--all --full-history" --redact --no-banner >/dev/null 2>&1; then
    note "gitleaks: no findings across all commits on all branches"
  else
    note "gitleaks reported findings — review them; the audit's one known false positive is"
    note "  'MP2020Compatibility' in tests/test_mp_data.py (rule generic-api-key)"
    gitleaks git --log-opts="--all --full-history" --redact --no-banner 2>&1 | grep -E '^(Finding|File|RuleID|Commit)' | head -20 | sed 's/^/        /'
    fail=1
  fi
else
  note "gitleaks NOT INSTALLED — history was checked by the built-in patterns above only."
  note "  install: https://github.com/gitleaks/gitleaks/releases  (then re-run this script)"
fi

echo
if [ "$fail" = 0 ]; then echo "PREFLIGHT OK — nothing blocking publication was found."; else echo "PREFLIGHT FAILED — see FAIL lines above."; fi
exit "$fail"
