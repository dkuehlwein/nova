#!/usr/bin/env bash
# PreToolUse hook: Block edits to sensitive files
# Reads tool_input.file_path from stdin JSON, exits 2 to block

set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

BASENAME=$(basename "$FILE_PATH")

# .env files
if [[ "$BASENAME" == .env* ]]; then
  echo "BLOCKED: Editing $BASENAME is not allowed via Claude. Edit manually to avoid leaking secrets." >&2
  exit 2
fi

# Files with sensitive keywords in the name
if echo "$BASENAME" | grep -qiE '(secret|credential|password|private.key|id_rsa|id_ed25519)'; then
  echo "BLOCKED: $BASENAME looks like a sensitive file. Edit manually." >&2
  exit 2
fi

# docker-compose.yml (infrastructure changes should be intentional)
if [[ "$BASENAME" == "docker-compose.yml" || "$BASENAME" == "docker-compose.yaml" ]]; then
  echo "BLOCKED: docker-compose.yml changes affect infrastructure. Edit manually to review carefully." >&2
  exit 2
fi

exit 0
