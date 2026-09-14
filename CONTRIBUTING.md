# Contributing

## Setup

Follow [the README](README.md#setup). A fresh clone needs no Materials Project key and no model
weights to run the fast tests:

```bash
python3 -m venv .tools && .tools/bin/pip install uv
./uvw python install 3.12 && ./uvw sync
./uvw run pytest -m "not slow"
```

Tests that need the API key or the weights skip themselves with a message naming the README step
that is missing, so a fresh clone reports skips rather than errors.

## Install the git hooks

Git hooks live in `.git/hooks/`, which is **not** cloned. Install them once:

```bash
./scripts/install_hooks.sh
```

That installs a **pre-commit** hook running `scripts/preflight_publish.sh --staged` over the staged
changes: credential patterns, the live `MP_API_KEY` value, secret-shaped filenames, absolute local
paths, email addresses, and directories that must never be published. It takes about **0.7 s**; the
full-history `gitleaks` scan is deliberately left out so that committing stays fast.

### Bypassing the hook

```bash
git commit --no-verify
```

Use it when the scan is wrong — it is a narrow pattern matcher and it can be. Do **not** use it to
push past a finding you have not read. The same checks run in CI on every push and pull request
(`.github/workflows/secret-scan.yml`), where `--no-verify` does not exist, so a bypassed commit is
caught on the server instead of in private.

To remove the hook entirely:

```bash
rm .git/hooks/pre-commit
```

## Before opening a pull request

```bash
./uvw run pytest -m "not slow"     # fast suite; no key, no weights
./scripts/preflight_publish.sh     # the full scan, including git history
```

Install [gitleaks](https://github.com/gitleaks/gitleaks/releases) if you want the preflight's
history scan to run locally rather than report itself skipped. CI installs it either way.

## What CI checks

`.github/workflows/secret-scan.yml`, on push and on pull request:

| job | what it does |
|:--|:--|
| `preflight` | `scripts/preflight_publish.sh` over a full-depth checkout — including §4b, which scans **every object in the history that would be published**, not just the working tree |
| `gitleaks-history` | `gitleaks` across all commits on all branches, `--redact` so a finding never prints a secret into a public log |

**Why §4b exists.** `git grep` only sees the tip. A personal email address once reached a published
repository because it sat in an *older* version of a report and had been edited out by the time of
the push — every HEAD-based check was clean and the address was still there in history. §4b streams
every blob, tree and commit reachable from `HEAD`, the local branches and the tags, so file content
*and* commit metadata are both covered. It deliberately does not scan `--all`: `refs/original/` and
`refs/backup-*/` are local rollback points that are never pushed.

It adds about two seconds, and it is skipped in `--staged` mode because a commit in progress cannot
change history that already exists.

**Neither job needs a secret**, an API key or model weights — every check reads only the repository,
so CI runs on forks and on pull requests from forks.

## Things that will fail review

- **Committing anything under `results/` other than `results.parquet` and `results/README.md`.**
  The rest of that directory is ~1 GB of SQLite job stores. The preflight enforces this.
- **Regenerating `results.parquet` and committing it again.** New versions go out as GitHub Release
  assets, so history does not grow by ~7 MB per run.
- **Relicensing third-party data.** Three files in `data/` are not ours to license; see
  [data/README.md](data/README.md). Adding a third-party dataset means adding its real terms to
  [NOTICE](NOTICE), not folding it into ours.
- **Quoting a report number without a link to the report section it comes from.** Every figure in
  the README is a pessimistic bound with a link; keep it that way.
