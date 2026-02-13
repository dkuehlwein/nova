---
name: start-ticket
description: Use when the user wants to start working on a Linear ticket - fetches ticket details, creates a git worktree with a properly named branch, and launches a subagent in the worktree with full ticket context and the right workflow skill
---

# Start Ticket

## Overview

Take a Linear ticket, set up a git worktree for isolated development, and launch a subagent in the worktree that has full ticket context and uses the right workflow skills for the ticket type.

## Process

### Phase 1: Get the Ticket

Accept the ticket reference from the user. It can be:
- A ticket identifier like `NOV-123`
- A Linear URL like `https://linear.app/team/issue/NOV-123/...`
- Just a number if context is clear (e.g., "start 123")

Extract the ticket identifier and fetch details using the Linear MCP tools:
- Use `get_issue` to retrieve title, description, labels, priority, state, and any attachments
- If the input is a URL, extract the identifier from the path (the `NOV-123` part)
- Also fetch comments with `list_comments` if useful for context

If the ticket can't be found, tell the user and stop.

### Phase 2: Create the Worktree

**Determine the branch type** from ticket labels and content:

| Label / Signal | Branch Prefix |
|---|---|
| Bug | `fix/` |
| Feature | `feature/` |
| Improvement | `feature/` |
| Docs-only content | `docs/` |
| Test-only content | `test/` |
| Refactoring language | `refactor/` |
| Maintenance / deps | `chore/` |

If ambiguous, default to `feature/`.

**Build the branch name**: `{prefix}{TICKET-ID}-{slugified-title}`
- Slugify: lowercase, replace spaces and special chars with hyphens, collapse multiple hyphens, strip leading/trailing hyphens, trim to ~50 chars at a word boundary
- Only use characters valid in git branch names (alphanumeric, `-`, `/`, `.`)
- Example: `fix/NOV-123-login-crash-on-empty-email`

**Create the worktree**:
1. Verify we're in a git repo with a valid `origin/main` (or `origin/master`)
2. Check for uncommitted changes in the current worktree - warn the user if any exist
3. Fetch latest from remote: `git fetch origin`
4. Check if branch or worktree already exists:
   - `git worktree list` to check for existing `../nova-{TICKET-ID}`
   - `git branch --list {branch-name}` to check for existing branch
   - If either exists, ask the user: reuse existing, pick a different name, or abort
5. Create the branch and worktree:
   ```
   git worktree add ../nova-{TICKET-ID} -b {branch-name} origin/main
   ```
   - Worktree goes in a sibling directory named `nova-{TICKET-ID}` (e.g., `../nova-NOV-123`)
   - Branch is based off `origin/main`
6. If any git operation fails (network, auth, conflicts), report the error clearly and stop - don't retry blindly

**Set up dependencies** (immediately after creating the worktree):

Worktrees share source code via git but gitignored directories like `.venv` and `node_modules` are missing. Run the setup script to handle this:

```bash
scripts/setup-worktree-deps.sh ../nova-{TICKET-ID}
```

This script:
- Creates a proper Python venv via `uv sync` (fast with cached packages, avoids broken symlink paths)
- Symlinks `frontend/node_modules` from the main repo
- Skips anything that doesn't exist or is already set up

**When NOT to use the script**: If the ticket explicitly involves changing dependencies (e.g., adding/removing packages, upgrading versions, modifying `pyproject.toml` or `package.json`), warn the user that the shared `node_modules` symlink may cause conflicts and ask whether they'd prefer a fresh `npm install` instead.

### Phase 3: Choose the Workflow

Analyze the ticket to decide which superpowers skill(s) fit best. Pick from:

- **`/brainstorm`** - Socratic design exploration. Best for complex features, ambiguous problems, or when the approach isn't obvious.
- **`/systematic-debugging`** - 4-phase root cause analysis. Best for bugs, especially when the cause isn't obvious.
- **`/write-plan` + `/execute-plan`** - Structured planning then execution. Best for features and improvements that touch multiple files/systems.
- **`/tdd`** - Test-driven RED-GREEN-REFACTOR. Best for tickets with clear acceptance criteria, or any bug (write the failing test first).
- **`/code-review`** - To be used at the end, after implementation is done.

**Matching guidelines:**
- Bug with unclear cause → `/systematic-debugging`, then `/tdd` for the fix
- Bug with clear cause → `/tdd` directly (write failing test, fix, verify)
- New feature, complex → `/brainstorm` → `/write-plan` → `/execute-plan`
- New feature, straightforward → `/write-plan` → `/execute-plan`
- Small improvement with clear criteria → `/tdd`
- Large refactor → `/write-plan` → `/execute-plan`

### Phase 4: Launch the Subagent

**Before launching**, show the user a brief summary:
```
Ticket: NOV-123 - Fix login crash on empty email
Type: Bug | Priority: High
Branch: fix/NOV-123-login-crash-on-empty-email
Worktree: ../nova-NOV-123
Workflow: /systematic-debugging → /tdd
```

Ask the user to confirm or adjust the workflow choice.

**Then launch a subagent** using the Task tool with `subagent_type: "general-purpose"`. The subagent prompt must include:

1. **The full ticket context** - title, description, acceptance criteria, labels, priority, any comments
2. **The worktree path** - instruct the agent to work exclusively in this directory (use absolute paths)
3. **The recommended workflow** - tell it which skill to invoke first
4. **Project conventions** - remind it to follow CLAUDE.md (it will pick this up from the worktree, but emphasize key points like test-driven bugfix, conventional commits)

**Example subagent prompt structure:**
```
You are working on the Nova project - an AI-powered kanban task management system.
Your task is Linear ticket {TICKET-ID}: "{title}"

## Ticket Details
{full description}

## Acceptance Criteria
{criteria from ticket}

## Comments / Additional Context
{any relevant comments from the ticket}

## Working Directory
Work exclusively in: {absolute path to worktree}
Branch: {branch-name}
Read CLAUDE.md in the worktree root for architecture patterns, testing strategy, and conventions.

## Workflow
Start by invoking the {recommended skill} skill to guide your approach.
{Brief explanation of why this skill fits}

## When Done
1. Run all relevant tests to verify your changes (see CLAUDE.md for test commands)
2. Summarize what you changed: which files, what approach, any decisions made
3. List any open questions or follow-ups
4. Do NOT commit or push - the user will review first
```

Launch the subagent and let it work. Report back the results when it finishes.

## Important Notes

- **Always confirm before launching.** Show the summary and get user approval before spawning the subagent.
- **Don't modify the ticket.** Don't change status, assignee, or add comments unless the user asks.
- **Respect existing worktrees.** If `../nova-{TICKET-ID}` already exists, ask before doing anything.
- **The subagent does the work.** This skill's job is setup and orchestration only.
- **No commits from subagent.** The subagent should write code and run tests, but leave committing to the user.

## Common Mistakes

- **Launching without confirmation** - Always show the summary and get user approval before spawning the subagent
- **Wrong workflow for the ticket type** - Bugs almost always benefit from `/systematic-debugging` or `/tdd`. Don't use `/brainstorm` for a straightforward bug.
- **Not checking for existing worktrees** - If `../nova-{TICKET-ID}` exists, the user may already be working on it. Ask first.
- **Subagent modifying Linear** - The subagent should only write code and tests, not update ticket status or add comments
- **Forgetting to pass acceptance criteria** - If the ticket has acceptance criteria, they MUST be in the subagent prompt. They drive the test plan.
- **Skipping test verification** - The subagent must run tests before reporting completion. Untested changes are not done.
