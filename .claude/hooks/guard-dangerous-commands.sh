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

# git clean (deletes untracked files permanently)
if echo "$STRIPPED" | grep -qE 'git\s+clean\s+-[a-zA-Z]*f'; then
  echo "BLOCKED: git clean -f permanently deletes untracked files. Review with git clean -n first." >&2
  exit 2
fi

# git checkout . / git restore . (discards all working tree changes)
if echo "$STRIPPED" | grep -qE 'git\s+(checkout|restore)\s+\.'; then
  echo "BLOCKED: git checkout/restore . discards all working tree changes. Use git stash instead." >&2
  exit 2
fi

# git branch -D (force-delete branch without merge check)
if echo "$STRIPPED" | grep -qE 'git\s+branch\s+-[a-zA-Z]*D'; then
  echo "BLOCKED: git branch -D force-deletes without checking merge status. Use -d for safe delete." >&2
  exit 2
fi

# git push --force on any branch (non-main already blocked above)
if echo "$STRIPPED" | grep -qE 'git\s+push\s+.*(-f|--force)'; then
  echo "BLOCKED: git push --force can overwrite remote history. Use --force-with-lease instead." >&2
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
