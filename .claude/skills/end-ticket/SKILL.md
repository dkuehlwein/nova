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

### Phase 6: Merge and Verify on Main

Unit tests ran on the branch (Phase 2). Now merge locally and run integration tests on main before pushing.

**Note the PR number** from Phase 4 -- you'll need it for the commit message.

1. **Switch to main and pull latest**:
   ```
   git checkout main
   git pull origin main
   ```

2. **Squash merge the branch**:
   ```
   git merge --squash <branch-name>
   ```
   If this fails (conflicts): `git merge --abort`, switch back to the branch, and tell the user to resolve manually. Stop here.

3. **Remove the implementation plan** (if one exists):
   ```
   git rm docs/plans/{TICKET-ID}-*.md
   ```
   Plan files are ephemeral — they served their purpose during development and should not land on main. If no plan file exists, skip this step (the glob will simply match nothing).

4. **Run integration tests on main**:
   ```
   cd backend && uv run pytest ../tests/integration -v
   ```
   - If tests **pass**: continue to step 5.
   - If tests **fail**: reset main and go back to the branch:
     ```
     git reset --hard origin/main
     git checkout <branch-name>
     ```
     Show the failures and tell the user to fix on the branch. Stop here.

5. **Commit the squash merge** with both the PR number and ticket ID:
   ```
   git commit -m "fix: Resolve login crash (NOV-123) (#42)"
   ```
   Use conventional commit format. The PR number goes at the end in parentheses.

6. **Push main**:
   ```
   git push origin main
   ```
   This automatically closes the PR on GitHub.

7. **Delete the remote branch**:
   ```
   git push origin --delete <branch-name>
   ```

### Phase 7: Update Ticket and Cleanup

**Update the ticket**: set the Linear ticket status to "Done" using `update_issue`.

**Clean up the local branch**:
```
git branch -d <branch-name>
```

**Check for worktree**: run `git worktree list` and check whether the original working directory was a git worktree.

- If in a worktree: remove it with `git worktree remove <worktree-path>`
- If not in a worktree: skip cleanup.

**Report completion**:
```
Ticket NOV-123 done. PR #42 merged to main. Worktree cleaned up.
```

## Edge Cases

- **Not on a feature branch** (on `main` or `master`): stop immediately with an error message.
- **No ticket ID in branch name**: ask the user for the ticket identifier.
- **PR already exists**: reuse the existing PR instead of creating a new one.
- **Merge conflicts on squash**: `git merge --abort`, switch back to the branch, tell user to resolve.
- **Integration tests fail on main**: `git reset --hard origin/main`, switch back to branch, show failures.
- **Code review loop limit** (3 iterations): stop the loop and tell the user to continue manually.
- **Not in a worktree**: skip the worktree cleanup step gracefully.

## Common Mistakes

- **Proceeding with failing tests** - If tests fail in Phase 2, the pipeline stops. No exceptions.
- **Not checking for an existing PR** - Always check `gh pr list --head <branch>` before creating a new PR. Duplicate PRs cause confusion.
- **Skipping code review** - The code review step (Phase 5) is mandatory. Always invoke the skill.
- **Pushing main with failing integration tests** - If integration tests fail on main, reset immediately. Never push broken main.
- **Forgetting to reset main on failure** - Always `git reset --hard origin/main` before switching back to the branch.
- **Forgetting to update Linear ticket status** - Update to "In Review" after PR creation AND to "Done" after merge. Both updates matter.
- **Removing worktree while still in it** - The user must `cd` out of the worktree directory before it can be removed.

## Important Notes

- **Always show the summary before proceeding.** Phase 1 ends with a summary -- get user acknowledgment before continuing.
- **Never force-push or force-merge.** If something fails, stop and report.
- **The code review step is mandatory**, not optional. It cannot be skipped.
- **Respect the 3-iteration review loop limit.** After 3 rounds, hand control back to the user.
- **If not in a worktree, cleanup is gracefully skipped.** Not every branch lives in a worktree.
