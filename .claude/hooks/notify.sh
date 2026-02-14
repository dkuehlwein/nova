#!/usr/bin/env bash
set -euo pipefail

INPUT=$(cat)

MESSAGE=$(echo "$INPUT" | jq -r '.message // "Needs your attention"')
TITLE=$(echo "$INPUT" | jq -r '.title // "Claude Code"')
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"')
CWD=$(echo "$INPUT" | jq -r '.cwd // "unknown"')

PROJECT=$(basename "$CWD")
BRANCH=$(git -C "$CWD" branch --show-current 2>/dev/null || echo "")
LABEL="${CC_NAME:-$BRANCH}"
SUBTITLE="${PROJECT} / ${LABEL:-unknown}"

/opt/homebrew/bin/terminal-notifier \
    -title "$TITLE" \
    -subtitle "$SUBTITLE" \
    -message "$MESSAGE" \
    -sound Ping \
    -activate com.googlecode.iterm2 \
    -group "claude-${SESSION_ID}"

exit 0
