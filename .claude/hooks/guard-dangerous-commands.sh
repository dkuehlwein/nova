#!/usr/bin/env bash
# PreToolUse hook: Block dangerous bash commands
# Reads tool_input.command from stdin JSON, exits 2 to block

set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [[ -z "$COMMAND" ]]; then
  exit 0
fi

# Strip quoted strings and heredocs to avoid false positives on commit messages, echo, etc.
# This removes single-quoted, double-quoted strings and heredoc bodies
STRIPPED=$(echo "$COMMAND" | sed -E "s/'[^']*'//g; s/\"[^\"]*\"//g" | sed '/<<.*EOF/,/^EOF/d')

# rm -rf targeting root, home, or current directory
if echo "$STRIPPED" | grep -qE 'rm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+(/\s|/\*|~/|\./?$|\.\*$)'; then
  echo "BLOCKED: Destructive rm -rf targeting root, home, or current directory" >&2
  exit 2
fi

# Force push to main/master
if echo "$STRIPPED" | grep -qE 'git\s+push\s+.*(-f|--force)' && echo "$STRIPPED" | grep -qE '(main|master)'; then
  echo "BLOCKED: Force push to main/master is not allowed" >&2
  exit 2
fi

# git reset --hard
if echo "$STRIPPED" | grep -qE 'git\s+reset\s+--hard'; then
  echo "BLOCKED: git reset --hard discards all local changes. Use git stash instead." >&2
  exit 2
fi

# DROP TABLE / DROP DATABASE
if echo "$STRIPPED" | grep -qiE 'DROP\s+(TABLE|DATABASE)'; then
  echo "BLOCKED: DROP TABLE/DATABASE detected. This is destructive and irreversible." >&2
  exit 2
fi

# chmod 777
if echo "$STRIPPED" | grep -qE 'chmod\s+777'; then
  echo "BLOCKED: chmod 777 makes files world-writable. Use more restrictive permissions." >&2
  exit 2
fi

# Pipe-to-shell (curl|sh, curl|bash, wget|sh, etc.)
if echo "$STRIPPED" | grep -qE '(curl|wget)\s+.*\|\s*(sh|bash|zsh)'; then
  echo "BLOCKED: Piping remote content to shell is dangerous. Download and inspect first." >&2
  exit 2
fi

exit 0
