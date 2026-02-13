#!/usr/bin/env bash
set -euo pipefail

# Setup dependencies in a git worktree.
# - backend/: runs `uv sync` (fast with cached packages, correct venv paths)
# - frontend/: symlinks node_modules from the main repo
#
# Usage: setup-worktree-deps.sh <worktree-path>

if [ $# -ne 1 ]; then
    echo "Usage: $0 <worktree-path>"
    exit 1
fi

WORKTREE="$(cd "$1" && pwd)"
MAIN_REPO="$(cd "$(dirname "$0")/.." && pwd)"

if [ ! -d "$WORKTREE/.git" ] && [ ! -f "$WORKTREE/.git" ]; then
    echo "Error: $WORKTREE is not a git worktree"
    exit 1
fi

# Backend: run uv sync for a correct venv with proper paths
if [ -f "$WORKTREE/backend/pyproject.toml" ]; then
    echo "Setting up Python venv in $WORKTREE/backend..."
    (cd "$WORKTREE/backend" && uv sync)
    echo "Python venv ready."
else
    echo "Skipping backend (no pyproject.toml found)."
fi

# Frontend: symlink node_modules from main repo
if [ -d "$MAIN_REPO/frontend/node_modules" ]; then
    if [ -e "$WORKTREE/frontend/node_modules" ]; then
        echo "Skipping frontend (node_modules already exists)."
    else
        ln -s "$MAIN_REPO/frontend/node_modules" "$WORKTREE/frontend/node_modules"
        echo "Symlinked frontend/node_modules from main repo."
    fi
else
    echo "Skipping frontend (no node_modules in main repo)."
fi
