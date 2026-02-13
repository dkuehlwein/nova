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
- Slugify: lowercase, replace spaces/special chars with hyphens, trim to ~50 chars
- Example: `fix/NOV-123-login-crash-on-empty-email`

**Create the worktree**:
1. Make sure we're in the main repo directory
2. Fetch latest from remote: `git fetch origin`
3. Create the branch and worktree in one command:
   ```
   git worktree add ../nova-{TICKET-ID} -b {branch-name} origin/main
   ```
   - Worktree goes in a sibling directory named `nova-{TICKET-ID}` (e.g., `../nova-NOV-123`)
   - Branch is based off `origin/main`
4. If the worktree or branch already exists, inform the user and ask how to proceed (reuse existing, or pick a different name)

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
You are working on Linear ticket {TICKET-ID}: "{title}"

## Ticket Details
{full description}

## Acceptance Criteria
{criteria from ticket}

## Working Directory
Work in: {absolute path to worktree}
Branch: {branch-name}

## Workflow
Start by invoking the {recommended skill} skill to guide your approach.
{Brief explanation of why this skill fits}

When implementation is complete, run all relevant tests to verify.
Do NOT commit or push - leave that for the user to review.
```

Launch the subagent and let it work. Report back the results when it finishes.

## Important Notes

- **Always confirm before launching.** Show the summary and get user approval before spawning the subagent.
- **Don't modify the ticket.** Don't change status, assignee, or add comments unless the user asks.
- **Respect existing worktrees.** If `../nova-{TICKET-ID}` already exists, ask before doing anything.
- **The subagent does the work.** This skill's job is setup and orchestration only.
- **No commits from subagent.** The subagent should write code and run tests, but leave committing to the user.
