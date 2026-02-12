---
name: create-ticket
description: Use when the user wants to create a Linear ticket, issue, user story, or task - interviews the user adaptively, formats as a user story with test plan, and creates it via Linear MCP after confirmation
---

# Create Linear Ticket

## Overview

Interview the user to understand their request, then create a well-structured Linear ticket as a user story with acceptance criteria and a test plan. Tickets follow TDD: they're only Done when all tests pass.

**Key principle:** A ticket documents the **what** (the problem) and **how to verify** (the test plan), never the **how to fix**. Root cause analysis, code investigation, and solution design belong to the implementation phase when someone picks up the ticket. Code changes between ticket creation and implementation, so any fix proposed at creation time risks being stale or misleading. Do NOT explore the codebase, search for root causes, or propose solutions during ticket creation.

## Process

### Phase 1: Understand the Request

Start by asking what the user wants to build or fix. Use AskUserQuestion to gather information adaptively:

**Always ask first:**
- What's the problem or request? (open-ended, let them describe it)

**Then adapt based on complexity:**

For simple/clear requests, propose sensible defaults and move to confirmation.

For complex/ambiguous requests, follow up with:
- Who is affected? (user role for the story)
- What's the expected behavior vs current behavior?
- Any technical constraints or preferences?
- Priority: Urgent, High, Normal, or Low?
- Area labels: Bug, Feature, Improvement + component labels (Agent, Frontend, Tools)

**Guidelines:**
- Ask 1-3 questions at a time, not a wall of questions
- If the user gave a detailed description upfront, don't re-ask what they already told you
- Infer what you can (e.g., if they say "the button doesn't work", it's a Bug + Frontend)
- Default priority to Normal unless the user signals urgency
- Default team to "Nova-Development"
- Auto-assign to "me"

### Phase 1.5: Complexity Check

Before drafting, assess whether the request is a single ticket or needs to be split. A good ticket should be completable in one focused effort.

**Signs a ticket is too big:**
- More than 5-6 acceptance criteria
- Touches multiple unrelated areas (e.g., "redesign the frontend and refactor the API")
- Contains multiple independent deliverables (e.g., "add search, filtering, and sorting")
- The user story has multiple distinct goals joined by "and"

**If it's too big**, propose splitting it. Present the breakdown to the user as a set of smaller tickets, each with its own user story. Ask which ones to create. Each sub-ticket should be independently valuable and testable - not just arbitrary slices.

**If it's borderline**, ask the user: "This could be one ticket or split into N. Preference?"

### Phase 2: Draft the Ticket

Format the ticket as a user story with this structure:

```markdown
## User Story

As a [role], I want [goal], so that [benefit].

## Context

[Brief problem description or background - what's happening now and why it needs to change]

## Acceptance Criteria

- [ ] [Specific, testable criterion 1]
- [ ] [Specific, testable criterion 2]
- [ ] [...]

## Test Plan

### Unit Tests
- [ ] [Test case 1: what to test and expected outcome]
- [ ] [Test case 2: ...]

### Integration Tests (if applicable)
- [ ] [Test case: ...]

### Manual Verification (if applicable)
- [ ] [Step to verify: ...]

## Definition of Done

- [ ] All acceptance criteria met
- [ ] All test cases implemented and passing
- [ ] Code reviewed
```

**Writing guidelines:**
- Acceptance criteria must be specific and testable - no vague "works correctly"
- Test cases should map to acceptance criteria
- Include edge cases in the test plan
- Keep it concise - no fluff
- Describe the **observable problem and expected behavior** - never propose root causes, code changes, or implementation approaches
- Test cases describe **what to verify**, not how to implement the fix

### Phase 3: Confirm and Create

Present the full draft to the user in a formatted message. Ask for approval or changes.

**On approval**, create the issue using the Linear MCP tools:
- Team: "Nova-Development" (unless overridden)
- Assignee: "me" (unless overridden)
- Title: concise, imperative (e.g., "Fix task card drag-and-drop on mobile")
- Description: the full user story markdown from Phase 2
- Labels: inferred from the conversation (Bug/Feature/Improvement + component labels)
- Priority: as discussed (1=Urgent, 2=High, 3=Normal, 4=Low)
- State: "Backlog" (default)

**On changes**, revise and re-present.

**When creating multiple tickets** (from a split), create them all after approval. If there's a natural ordering, set up blocking relationships between them.

After creation, show the user the issue identifier(s) (e.g., NOV-123) so they can find them in Linear.

## Label Reference

| Label | Use When |
|-------|----------|
| Bug | Something is broken or behaving incorrectly |
| Feature | Net-new functionality |
| Improvement | Enhancing existing functionality |
| Agent | Related to the AI agent system (backend/agent/) |
| Frontend | Related to the Next.js frontend |
| Tools | Related to MCP tools or LangChain tools |

## Common Mistakes

- **Investigating root causes or proposing fixes** - this is the #1 mistake. Do NOT read source code, search for bugs, or suggest implementation approaches. That work belongs to whoever picks up the ticket.
- Writing vague acceptance criteria like "the feature works" - be specific
- Forgetting edge cases in the test plan
- Over-engineering the ticket for simple tasks - a one-line bug doesn't need 20 test cases
- Not inferring obvious labels from context (if they mention a UI issue, add Frontend)
- Creating a mega-ticket that covers multiple independent concerns - split it up
