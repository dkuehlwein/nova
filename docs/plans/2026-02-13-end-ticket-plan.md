# End-Ticket Skill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create an `end-ticket` skill that wraps up Linear ticket work through a fixed pipeline: tests, commit, PR, code review, merge, ticket update, and worktree cleanup.

**Architecture:** Single SKILL.md file in `.claude/skills/end-ticket/`. Mirrors `start-ticket` structure and conventions. Orchestrates existing tools (git, gh, Linear MCP, code-review skill) in a fixed sequence.

**Tech Stack:** Claude Code skill (Markdown), Linear MCP, GitHub CLI, git

---

### Task 1: Write the SKILL.md

**Files:**
- Create: `.claude/skills/end-ticket/SKILL.md`

**Step 1: Create the skill directory**

Run: `mkdir -p .claude/skills/end-ticket`

**Step 2: Write the SKILL.md**

Write `.claude/skills/end-ticket/SKILL.md` with the following structure, using the design doc at `docs/plans/2026-02-13-end-ticket-design.md` as the source of truth:

```markdown
---
name: end-ticket
description: Use when the user is done working on a Linear ticket and wants to wrap up - creates PR, runs code review, merges, updates the ticket status, and cleans up the worktree
---

# End Ticket

## Overview

Wrap up a Linear ticket by running a fixed pipeline: verify tests, commit, create PR, run code review, merge, update ticket status, and clean up the worktree. The mirror of `start-ticket`.

## Process

### Phase 1: Identify the Ticket
[Extract ticket ID from branch, fetch from Linear, show summary, guard against main/master]

### Phase 2: Verify Tests
[Offer skip if recently run, otherwise run test suite, stop on failure]

### Phase 3: Commit Uncommitted Work
[git status, stage + commit if changes, skip if clean]

### Phase 4: Create PR
[Check for existing PR, push + create if needed, link to Linear, set ticket to In Review]

### Phase 5: Code Review
[Invoke code-review:code-review, present findings, fix-review loop max 3 iterations]

### Phase 6: Merge
[gh pr merge --squash, stop on conflict]

### Phase 7: Update Ticket and Cleanup
[Set ticket to Done, remove worktree if applicable, report completion]

## Edge Cases
[Branch guards, missing ticket ID, existing PR, merge conflicts, review loop limit, non-worktree]

## Common Mistakes
[List of things that can go wrong]
```

Use `start-ticket/SKILL.md` as the style reference for tone, formatting, section depth, and YAML frontmatter conventions.

**Step 3: Verify file exists and frontmatter is valid**

Run: `head -5 .claude/skills/end-ticket/SKILL.md`
Expected: YAML frontmatter with `name: end-ticket` and `description: Use when...`

**Step 4: Commit**

```bash
git add .claude/skills/end-ticket/SKILL.md
git commit -m "feat: Add end-ticket skill for wrapping up Linear tickets"
```

### Task 2: Test the Skill (RED phase)

**Purpose:** Verify the skill is discoverable and that an agent can follow it correctly.

**Step 1: Check skill appears in the skill list**

Start a new conversation and check if `end-ticket` appears in the available skills list. If it doesn't, check the frontmatter format.

**Step 2: Dry-run the skill mentally**

Walk through each phase with a realistic scenario (e.g., branch `fix/NOV-100-test-ticket`, some uncommitted changes, no existing PR). Verify:
- Every phase has clear instructions an agent can follow without ambiguity
- Edge case handling is explicit (what to do when X happens)
- The code-review invocation syntax is correct (`code-review:code-review`)
- Linear MCP tool names are correct (`get_issue`, `update_issue`, `list_issue_statuses`)

**Step 3: Fix any gaps found**

Edit SKILL.md to address any ambiguities or missing instructions.

**Step 4: Commit fixes if any**

```bash
git add .claude/skills/end-ticket/SKILL.md
git commit -m "fix: Address gaps in end-ticket skill from dry-run testing"
```

### Task 3: Update design doc as complete

**Files:**
- Modify: `docs/plans/2026-02-13-end-ticket-design.md`

**Step 1: Add completion note to design doc**

Add a line at the top: `Status: Implemented`

**Step 2: Commit**

```bash
git add docs/plans/2026-02-13-end-ticket-design.md
git commit -m "docs: Mark end-ticket design as implemented"
```
