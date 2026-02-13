# Claude Code Hooks Design

**Date:** 2026-02-13
**Approach:** B - Quality Gates (5 hooks)

## Problem

Two main workflow friction points:
1. Quality issues slipping through during development (caught too late)
2. Repetitive permission prompts for safe operations

Plus quality-of-life improvements: auto-formatting and desktop notifications.

## Hooks

### 1. Auto-format on edit (`PostToolUse`)
- Matcher: `Edit|Write`
- Script: `.claude/hooks/auto-format.sh`
- Runs ruff format + ruff check --fix on .py files
- Runs prettier --write on .ts/.tsx/.js/.jsx/.json/.css files
- Always exits 0 (formatting failures don't block Claude)

### 2. macOS desktop notification (`Notification`)
- Inline osascript command (no script file)
- Fires when Claude needs attention (permission prompt, idle)

### 3. Dangerous command guard (`PreToolUse`)
- Matcher: `Bash`
- Script: `.claude/hooks/guard-dangerous-commands.sh`
- Blocks: rm -rf /, force push to main, git reset --hard, DROP TABLE/DATABASE, chmod 777, pipe-to-shell
- Exit 2 to block, exit 0 to allow

### 4. Stop verification (`Stop`)
- Type: prompt (haiku model)
- Checks if Claude completed what was asked, flags loose ends
- Lightweight (~2-3s per stop)

### 5. Sensitive file guard (`PreToolUse`)
- Matcher: `Edit|Write`
- Script: `.claude/hooks/guard-sensitive-files.sh`
- Blocks edits to .env files, credential files, docker-compose.yml
- Exit 2 with explanation

## Setup Required

- Add `ruff` to backend dev dependencies
- Add `prettier` to frontend dev dependencies
- Add `.prettierrc` config to frontend
- Create `.claude/hooks/` directory with scripts
- Add hooks config to `.claude/settings.local.json`
