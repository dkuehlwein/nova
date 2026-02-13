---
name: end-ticket
description: Use when the user is done working on a Linear ticket and wants to wrap up - creates PR, runs code review, merges, updates the ticket status, and cleans up the worktree
---

# End Ticket

## Overview

Wrap up work on a Linear ticket through a fixed pipeline: verify tests, commit, create PR, run code review, merge, update the ticket, and clean up the worktree. The mirror of `start-ticket`.

## Process

### Phase 1: Identify the Ticket

Accept an optional ticket reference from the user. It can be:
- A ticket identifier like `NOV-123`
- A Linear URL like `https://linear.app/team/issue/NOV-123/...`
- Just a number if context is clear (e.g., "end 123")

If not provided, extract the ticket ID from the current branch name. The expected pattern is `{prefix}/{TICKET-ID}-{slug}` (e.g., `fix/NOV-123-login-crash` yields `NOV-123`).

**Before anything else**, check the current branch:
- If on `main` or `master`, stop with error: "end-ticket is for feature branches, not main/master."
- If no ticket ID can be extracted from the branch name and the user didn't provide one, ask the user for the ticket identifier.

Fetch ticket details using the Linear MCP `get_issue` tool. If the ticket can't be found, tell the user and stop.

Show a summary before proceeding:
```
Ticket: NOV-123 - Fix login crash on empty email
Status: In Progress
Branch: fix/NOV-123-login-crash-on-empty-email
```

### Phase 2: Verify Tests

Ask the user: "Tests were run recently -- skip or re-run?"

- If re-run: execute `cd backend && uv run pytest ../tests`
  - If tests fail: stop, show the failures. Do NOT proceed.
  - If tests pass: continue.
- If skip: continue.

### Phase 3: Commit Uncommitted Work

Run `git status` to check for uncommitted changes.

- If changes exist: stage the relevant files and create a commit using conventional commit format. Reference the ticket ID in the commit message (e.g., `fix: Resolve login crash on empty email (NOV-123)`). Follow the standard commit process from CLAUDE.md -- show the diff, draft a message, and commit.
- If no changes: skip. Everything is already committed.

### Phase 4: Create PR

Check if a PR already exists for this branch:
```
gh pr list --head <branch-name> --json number,url
```

- If a PR exists: use it. Show the URL to the user.
- If no PR exists:
  1. Push the branch: `git push -u origin <branch-name>`
  2. Create the PR via `gh pr create`:
     - Title: the Linear ticket title
     - Body: summary of changes + link to the Linear ticket

After the PR exists (whether new or existing):
- Add the PR URL as a link attachment on the Linear ticket using `update_issue` with the `links` parameter.
- Update the Linear ticket status to "In Review" using `update_issue`.

### Phase 5: Code Review

Invoke the `code-review:code-review` skill on the PR using the Skill tool.

Evaluate the results:
- **No issues found** (all scores below 80): proceed to Phase 6.
- **Issues found**:
  1. Present the findings to the user.
  2. Ask: "Agree with findings (fix them) or dismiss (proceed anyway)?"
  3. If **agree**: fix the issues, commit the fixes, push, and re-invoke the code review skill.
  4. If **dismiss**: proceed to Phase 6.
  5. Loop a maximum of 3 iterations. After 3 rounds with issues still present, tell the user: "Code review loop limit reached. Please continue manually." Stop here.

### Phase 6: Merge

Squash merge the PR:
```
gh pr merge --squash --delete-branch
```

If the merge fails (e.g., conflicts or failing checks): stop and tell the user to resolve the issue manually. Do NOT force merge.

### Phase 7: Update Ticket and Cleanup

**Update the ticket**: set the Linear ticket status to "Done" using `update_issue`.

**Check for worktree**: run `git worktree list` and check whether the current working directory is inside a git worktree (not the main repo).

- If in a worktree:
  1. Tell the user to `cd` back to the main repo directory first.
  2. Then remove the worktree: `git worktree remove <worktree-path>`
- If not in a worktree: skip cleanup.

**Report completion**:
```
Ticket NOV-123 done. PR #42 merged. Worktree cleaned up.
```

## Edge Cases

- **Not on a feature branch** (on `main` or `master`): stop immediately with an error message.
- **No ticket ID in branch name**: ask the user for the ticket identifier.
- **PR already exists**: reuse the existing PR instead of creating a new one.
- **Merge conflicts**: stop and tell the user to resolve manually. Never force merge.
- **Code review loop limit** (3 iterations): stop the loop and tell the user to continue manually.
- **Not in a worktree**: skip the worktree cleanup step gracefully.

## Common Mistakes

- **Proceeding with failing tests** - If tests fail in Phase 2, the pipeline stops. No exceptions.
- **Not checking for an existing PR** - Always check `gh pr list --head <branch>` before creating a new PR. Duplicate PRs cause confusion.
- **Skipping code review** - The code review step (Phase 5) is mandatory. Always invoke the skill.
- **Force merging with conflicts** - If `gh pr merge` fails, stop. Never use `--admin` or force flags.
- **Forgetting to update Linear ticket status** - Update to "In Review" after PR creation AND to "Done" after merge. Both updates matter.
- **Removing worktree while still in it** - The user must `cd` out of the worktree directory before it can be removed.

## Important Notes

- **Always show the summary before proceeding.** Phase 1 ends with a summary -- get user acknowledgment before continuing.
- **Never force-push or force-merge.** If something fails, stop and report.
- **The code review step is mandatory**, not optional. It cannot be skipped.
- **Respect the 3-iteration review loop limit.** After 3 rounds, hand control back to the user.
- **If not in a worktree, cleanup is gracefully skipped.** Not every branch lives in a worktree.
