# End-Ticket Skill Design

## Summary

A skill that wraps up Linear ticket work: tests, commit, PR, code review, merge, ticket update, and worktree cleanup. The mirror of `start-ticket`.

## Decisions

- **Fixed pipeline** (not flexible options): always takes the PR path
- **Builds on** `finishing-a-development-branch` concepts but implements inline (since we hardcode to PR path)
- **Invokes** `code-review:code-review` for PR review
- **Fix-review loop**: if issues found and user agrees, fix and re-review (max 3 iterations)
- **Merge method**: GitHub squash merge (`gh pr merge --squash`)
- **Linear status flow**: current status -> "In Review" (on PR creation) -> "Done" (on merge)
- **Test skip**: user can opt to skip tests if they were just run

## Pipeline

### Phase 1: Identify the Ticket

- Extract ticket ID from branch name (pattern: `{prefix}/{TICKET-ID}-{slug}`)
- If no ticket ID found, ask the user
- Fetch ticket details via Linear MCP (`get_issue`)
- Show summary: ticket title, current status, branch name
- If on `main`/`master`, stop with error

### Phase 2: Verify Tests

- Ask user: "Skip tests? (if recently run)" or run `cd backend && uv run pytest ../tests`
- If tests fail: stop, show failures, do not proceed
- If tests pass: continue

### Phase 3: Commit Uncommitted Work

- Run `git status` to check for uncommitted changes
- If changes exist: stage them, create a commit (conventional commit format)
- If no changes: skip

### Phase 4: Create PR

- Check if PR already exists (`gh pr list --head <branch>`)
- If exists: use existing PR
- If not: push branch (`git push -u origin <branch>`), create PR via `gh pr create`
- Link PR to Linear ticket (add PR URL as link attachment)
- Update Linear ticket status to "In Review"

### Phase 5: Code Review

- Invoke `/code-review:code-review` on the PR
- If no issues (all scores < 80): proceed to Phase 6
- If issues found:
  - Present findings to user
  - Ask: agree with findings or dismiss?
  - If agree: fix issues, commit, push, re-run code review (loop, max 3 iterations)
  - If dismiss: proceed to Phase 6

### Phase 6: Merge

- Squash merge via `gh pr merge --squash`
- If merge fails (conflicts): stop, tell user to resolve manually

### Phase 7: Update Ticket and Cleanup

- Update Linear ticket status to "Done"
- Check if in a worktree (`git worktree list`)
- If in worktree: navigate out, remove worktree
- If not in worktree: skip cleanup
- Report completion: ticket, PR number, merge status

## Edge Cases

- **Not on a feature branch**: stop with error
- **No ticket ID in branch name**: ask user for ticket identifier
- **PR already exists**: reuse it
- **Merge conflicts**: stop, tell user to resolve manually
- **Code review loop limit**: 3 iterations max, then tell user to continue manually
- **Not in a worktree**: skip worktree cleanup gracefully

## Skill Relationships

- `start-ticket` -> work -> `end-ticket` (mirror skills)
- Borrows test verification and worktree cleanup patterns from `finishing-a-development-branch`
- Invokes `code-review:code-review` as a sub-step
- Does NOT call `finishing-a-development-branch` directly (fixed PR path)

## File Location

`.claude/skills/end-ticket/SKILL.md`
