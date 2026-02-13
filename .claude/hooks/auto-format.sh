#!/usr/bin/env bash
# PostToolUse hook: Auto-format files after Edit/Write
# Reads tool_input.file_path from stdin JSON, runs appropriate formatter

set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ -z "$FILE_PATH" || ! -f "$FILE_PATH" ]]; then
  exit 0
fi

case "$FILE_PATH" in
  *.py)
    # Format with ruff (silently ignore failures)
    ruff format "$FILE_PATH" 2>/dev/null || true
    ruff check --fix "$FILE_PATH" 2>/dev/null || true
    ;;
  *.ts|*.tsx|*.js|*.jsx|*.json|*.css)
    # Format with prettier (silently ignore failures)
    npx --yes prettier --write "$FILE_PATH" 2>/dev/null || true
    ;;
esac

exit 0
