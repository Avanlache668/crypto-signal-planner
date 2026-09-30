#!/usr/bin/env bash
# Local-only portable skill installer. Run at repository root.
set -euo pipefail
MODE="${1:-shared}"
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case "$MODE" in
  shared|codex) TARGET="${HOME}/.agents/skills/crypto-signal-planner" ;;
  openclaw) TARGET="${OPENCLAW_STATE_DIR:-${HOME}/.openclaw}/skills/crypto-signal-planner" ;;
  openclaw-workspace) TARGET="${OPENCLAW_WORKSPACE:-${HOME}/.openclaw/workspace}/skills/crypto-signal-planner" ;;
  *) echo "Usage: bash install.sh [shared|codex|openclaw|openclaw-workspace]" >&2; exit 2 ;;
esac
if [[ -e "$TARGET" ]]; then
  echo "Target already exists: $TARGET" >&2
  echo "No overwrite. Review/backup it before reinstalling." >&2
  exit 3
fi
mkdir -p "$TARGET"
# Copy only skill files; NEVER include repository metadata, publication scripts, or secrets.
cp -R "$SKILL_DIR/SKILL.md" "$SKILL_DIR/references" "$SKILL_DIR/assets" "$SKILL_DIR/scripts" "$SKILL_DIR/examples" "$TARGET/"
[[ -f "$TARGET/SKILL.md" ]] || { echo "Install integrity check failed" >&2; exit 4; }
echo "Skill copied locally: $TARGET"
case "$MODE" in
  openclaw|openclaw-workspace) echo "Check: openclaw skills info crypto-signal-planner && openclaw skills check" ;;
  shared) echo "Visible to Codex and default-state local OpenClaw; custom OpenClaw Gateway may need explicit installation." ;;
  codex) echo "Start/restart Codex, then invoke: \$crypto-signal-planner" ;;
esac
