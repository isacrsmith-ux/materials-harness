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

echo "== 4b. emails and local paths in PUBLISHED HISTORY (every commit, not just HEAD) =="
# Section 4 checks the working tree at HEAD. That is not enough: a file can carry a personal
# address in an OLD commit and be cleaned up later, and `git grep` will never see it while the
# tip is clean. That is exactly how a personal email reached a published repository once.
#
# Scope: objects reachable from HEAD, local branches and tags -- i.e. what a push actually
# publishes. Deliberately NOT --all: refs/original/ and refs/backup-*/ are local rollback points
# that are never pushed and still hold pre-redaction content by design.
if [ "$STAGED" = 1 ]; then
  note "skipped in --staged mode (a commit in progress cannot change existing history); CI runs it"
else
  HIST_EMAIL='[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
  HIST_PATH='/Users/[A-Za-z0-9._-]+|/home/[A-Za-z0-9._-]+'
  # Addresses that are expected and must not trip the check.
  #   help@sti.nasa.gov is printed in the standard back matter of NASA/TM-2006-214482, the
  #   public-domain technical memorandum vendored verbatim at
  #   reference_data/raw/NASA-TM-2006-214482_MISSE2_PEACE.pdf. It is a published institutional
  #   help desk, not a personal address, and the file is stored byte-for-byte so that its
  #   recorded sha256 verifies -- editing it out is not an option and is not warranted.
  EMAIL_OK='noreply@anthropic\.com|users\.noreply\.github\.com|@example\.(com|org|net)|@(domain|host)\.|help@sti\.nasa\.gov'

  # Binary blobs are excluded from the TEXT scan below and checked by 4c instead.
  #
  # Why: scanning compressed binary for text patterns is both noisy and incomplete.
  #
  # Noisy, because a ReportLab PDF's ASCII85 streams throw up address-shaped runs by chance --
  # things of the form "aW_Fjs6+G6r(at)VT.gqUh", written with (at) here because a literal example
  # in this comment would trip the very check it documents.
  #
  # Incomplete, because a real address inside a Flate stream is invisible to the same scan.
  # Measured on this repo: the raw pass reported two chance runs from reports/test_results.pdf and
  # one from the vendored NASA memorandum, and MISSED that memorandum's genuine STI help-desk
  # address, which sits in a compressed stream. It raised false alarms and gave false assurance at
  # the same time, which is why the real check is 4c.
  # [.] rather than \. on purpose: awk -v processes escape sequences in the assigned value, so
  # a backslash here becomes "escape sequence `\.' treated as plain `.'" on every run. The
  # character class means the same thing and passes through untouched.
  BINARY_RE='[.](pdf|gz|zip|parquet|sqlite|model|png|jpe?g|gif|ico|woff2?|ttf|so|dylib|whl)$'

  hist_objs=$(git rev-list --objects HEAD --branches --tags 2>/dev/null \
                | awk -v re="$BINARY_RE" '$2 == "" || $2 !~ re {print $1}' | sort -u)
  n_objs=$(echo "$hist_objs" | grep -c . || true)
  n_skipped=$(git rev-list --objects HEAD --branches --tags 2>/dev/null \
                | awk -v re="$BINARY_RE" '$2 != "" && $2 ~ re' | wc -l | tr -d ' ')

  # One streamed pass over every non-binary object: blobs (file content) and commits
  # (author/committer and messages) both go through, so this covers metadata as well as files.
  bad_emails=$(echo "$hist_objs" | git cat-file --batch 2>/dev/null \
                 | grep -aoE "$HIST_EMAIL" 2>/dev/null \
                 | grep -avEi "$EMAIL_OK" 2>/dev/null | sort -u || true)
  bad_paths=$(echo "$hist_objs" | git cat-file --batch 2>/dev/null \
                 | grep -aoE "$HIST_PATH" 2>/dev/null | sort -u || true)

  if [ -n "$bad_emails" ]; then
    bad "email address in published history ($n_objs objects scanned):"
    echo "$bad_emails" | head -5 | sed 's/^/        /'
    note "locating the objects (slow path, only on failure):"
    git rev-list --objects HEAD --branches --tags 2>/dev/null | while read -r sha path; do
      [ -n "$path" ] || continue
      m=$(git cat-file blob "$sha" 2>/dev/null | grep -aoE "$HIST_EMAIL" 2>/dev/null \
            | grep -avEi "$EMAIL_OK" 2>/dev/null | sort -u | head -2)
      [ -n "$m" ] && printf '        %s  %s  ->  %s\n' "${sha:0:12}" "$path" "$(echo "$m" | tr '\n' ' ')"
    done
    note "to find which commits carry it: git log --all --oneline -- <path>"
  else
    note "no unexpected email addresses in published history ($n_objs objects: blobs, trees and commits; $n_skipped binary blobs excluded, see 4c)"
  fi

  if [ -n "$bad_paths" ]; then
    bad "absolute local path in published history:"
    echo "$bad_paths" | head -5 | sed 's/^/        /'
  else
    note "no absolute local paths in published history"
  fi
fi

echo "== 4c. tracked PDFs, by EXTRACTED TEXT (4b cannot see inside them) =="
# 4b excludes binary blobs, so a PDF is not text-scanned there. This closes that gap the only way
# that actually works: decode the document and scan what it really says -- the extracted text, the
# decompressed content streams, and the document metadata (which carries an /Author field).
pdfs=$(git ls-files -- '*.pdf' 2>/dev/null || true)
if [ -z "$pdfs" ]; then
  note "no tracked PDFs"
elif [ ! -x "./uvw" ] || [ ! -x "./.tools/bin/uv" ]; then
  # Test the BINARY, not just the wrapper. ./uvw is tracked and executable, but it execs
  # .tools/bin/uv, and .tools/ is gitignored -- so on a fresh clone the wrapper exists and the
  # tool behind it does not. Checking only the wrapper made this section fail with an empty
  # message in CI instead of saying it could not run. The workflow installs uv to that path.
  note "SKIPPED: .tools/bin/uv not available, so tracked PDFs were NOT checked. Do not publish on this run."
else
  if pdf_out=$(echo "$pdfs" | ./uvw run --with pypdf --no-project --quiet python -c '
import re, sys, pypdf
OK = re.compile(r"noreply@anthropic\.com|users\.noreply\.github\.com|@example\.(com|org|net)|help@sti\.nasa\.gov", re.I)
BAD = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|/Users/[A-Za-z0-9._-]+|/home/[A-Za-z0-9._-]+")
rc = 0
for path in (l.strip() for l in sys.stdin if l.strip()):
    try:
        r = pypdf.PdfReader(path)
        blob = "".join((p.extract_text() or "") for p in r.pages)
        for p in r.pages:
            try: blob += p.get_contents().get_data().decode("latin-1")
            except Exception: pass
        blob += " ".join(f"{k}={v}" for k, v in (r.metadata or {}).items())
    except Exception as exc:
        print(f"UNREADABLE {path}: {type(exc).__name__}"); rc = 1; continue
    hits = sorted({h for h in BAD.findall(blob) if not OK.search(h)})
    print(("FOUND " + path + ": " + ", ".join(hits[:4])) if hits else ("clean  " + path))
    if hits: rc = 1
sys.exit(rc)
' 2>&1); then
    echo "$pdf_out" | sed 's/^/  /'
    note "tracked PDFs carry no unexpected address or local path in their real content"
  else
    bad "a tracked PDF contains an unexpected address or local path, or could not be read:"
    echo "$pdf_out" | sed 's/^/        /'
  fi
fi

echo "== 5. directories that must never be published =="
# results/ is a deliberate exception: exactly four files there are published (the exported table, its
# data dictionary, and the database schema/summary that `python -m harness checkpoint` writes). Anything
# else appearing under results/ is a mistake -- most of the directory is ~1 GB of SQLite job stores.
RESULTS_ALLOWED="results/README.md results/results.parquet results/schema.sql results/summary.json"
for d in models cache logs config/launchd .envs .venv; do
  n=$(git ls-files "$d" | wc -l | tr -d ' ')
  if [ "$n" != 0 ]; then bad "$d has $n tracked file(s)"; else note "$d: not tracked"; fi
done
# $RESULTS_ALLOWED is the single source of truth: unquoted on purpose, so each path becomes its own -F pattern.
unexpected=$(git ls-files results | grep -vxF "$(printf '%s\n' $RESULTS_ALLOWED)")
if [ -n "$unexpected" ]; then
  bad "results/ has tracked file(s) beyond the published ones ($RESULTS_ALLOWED):"
  echo "$unexpected" | sed 's/^/        /'
else
  note "results/: only the published files are tracked ($RESULTS_ALLOWED)"
fi

echo "== 6. gitleaks (full history) =="
if [ "$STAGED" = 1 ]; then
  # A pre-commit hook must stay fast. The full-history scan belongs in CI and in the manual run,
  # not in front of every commit -- the staged patterns above already cover what is being added.
  note "skipped in --staged mode (kept fast for the pre-commit hook); CI runs the full scan"
elif command -v gitleaks >/dev/null 2>&1; then
  if gitleaks git --log-opts="--all --full-history" --redact --no-banner >/dev/null 2>&1; then
    note "gitleaks: no findings across all commits on all branches"
  else
    note "gitleaks reported findings — review them. The one known false positive"
    note "  ('MP2020Compatibility', rule generic-api-key) is allowlisted in .gitleaks.toml,"
    note "  so anything reported here is something new."
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
