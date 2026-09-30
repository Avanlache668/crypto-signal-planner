#!/usr/bin/env bash
# Explicit owner-run publishing script. Never reads or prints credentials.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
REPO_NAME="crypto-signal-planner"
if [[ "${CONFIRM_PUBLIC:-}" != "1" ]]; then
  echo "Refusing public publication. Re-run: CONFIRM_PUBLIC=1 bash publish_github.sh" >&2
  exit 2
fi
command -v git >/dev/null || { echo 'git is required' >&2; exit 2; }
command -v gh >/dev/null || { echo 'GitHub CLI (gh) is required' >&2; exit 2; }
gh auth status >/dev/null || { echo 'Run gh auth login first' >&2; exit 2; }
python3 scripts/smoke_test.py
if ! git config user.name >/dev/null || ! git config user.email >/dev/null; then
  echo 'Set git config user.name and user.email before publishing.' >&2; exit 2
fi
if [[ ! -d .git ]]; then
  git init -b main
fi
if [[ -n "$(git remote 2>/dev/null)" ]]; then
  echo 'Existing Git remote detected. Refusing to create/push a new repository.' >&2; exit 3
fi
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo 'Working tree contains uncommitted modifications; review before publication.' >&2; exit 3
fi
if [[ -z "$(git log -1 --format=%H 2>/dev/null || true)" ]]; then
  git add README.md SKILL.md INSTALL.zh-CN.md PUBLISH.md install.sh publish_github.sh .gitignore .github references assets scripts examples
  git commit -m 'Initial public crypto-signal-planner skill'
else
  [[ -z "$(git status --porcelain)" ]] || { echo 'Working tree not clean' >&2; exit 3; }
fi
OWNER="${GH_OWNER:-$(gh api user --jq .login)}"
FULL="$OWNER/$REPO_NAME"
if gh repo view "$FULL" >/dev/null 2>&1; then
  echo "Refusing: repository already exists: $FULL" >&2; exit 3
fi
printf 'Publishing PUBLIC repository %s\n' "$FULL"
gh repo create "$FULL" --public --source=. --remote=origin --push
printf 'Created: https://github.com/%s\n' "$FULL"
