#!/usr/bin/env bash
# Publish reviewed skill files to an EXISTING GitHub repository; no forced pushes.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
REPO="${GH_REPO:-Avanlache668/crypto-signal-planner}"
[[ "${CONFIRM_PUBLIC:-}" == 1 ]] || { echo 'Explicit opt-in needed: CONFIRM_PUBLIC=1' >&2; exit 2; }
command -v git >/dev/null || { echo 'git required' >&2; exit 2; }
command -v gh >/dev/null || { echo 'gh required' >&2; exit 2; }
gh auth status >/dev/null || { echo 'Run gh auth login' >&2; exit 2; }
python3 scripts/smoke_test.py
python3 scripts/validate_plan.py examples/hypothetical-plan.json --allow-fixture
[[ $(gh repo view "$REPO" --json visibility --jq '.visibility') == PUBLIC ]] || { echo "Refusing to publish: $REPO is not PUBLIC or not accessible" >&2; exit 3; }
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
# Clone remote HEAD; preserve existing history, no force push.
gh repo clone "$REPO" "$TMP/repo"
# Only allowlist reviewed sources; do not upload any secrets, runtime files or .git objects.
for item in README.md SKILL.md INSTALL.zh-CN.md PUBLISH.md .gitignore .github assets examples references scripts/position_size.py scripts/smoke_test.py scripts/validate_plan.py install.sh publish_github.sh push_existing_github.sh; do
  mkdir -p "$TMP/repo/$(dirname "$item")"
  if [[ -d "$item" ]]; then cp -R "$item" "$TMP/repo/$(dirname "$item")/"; else cp "$item" "$TMP/repo/$item"; fi
done
cd "$TMP/repo"
git add README.md SKILL.md INSTALL.zh-CN.md PUBLISH.md .gitignore .github assets examples references scripts/position_size.py scripts/smoke_test.py scripts/validate_plan.py install.sh publish_github.sh push_existing_github.sh
if git diff --staged --quiet; then echo 'Already up to date'; exit 0; fi
git -c user.name="${GIT_AUTHOR_NAME:-Skill Publisher}" -c user.email="${GIT_AUTHOR_EMAIL:-noreply@users.noreply.github.com}" commit -m 'Publish portable Crypto Signal Planner skill'
git push origin HEAD
printf 'Published: https://github.com/%s\n' "$REPO"
