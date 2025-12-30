# Create Jira Tickets

Create Jira epics and tasks from product specifications.

**Important**: Read and follow the shared instructions in `_shared.md`.

## Step 1: Gather Information

Ask the user these questions **one at a time**, waiting for each answer:

1. **Feature name**: What is this feature called?
2. **Problem statement**: What problem does this solve? Who benefits?
3. **User story**: Describe the expected behavior from a user perspective
4. **Scope**: What's included? What's explicitly out of scope?
5. **Dependencies**: Are there any blockers or prerequisites?
6. **Additional context**: Any mockups, specs, or references to include?

## Step 2: Summarize and Confirm

Present a summary:

```markdown
## Feature: [Name]

### Problem
[Problem statement]

### Solution
[User story summarized]

### Scope
- In: [items]
- Out: [items]

### Dependencies
[List or "None"]
```

Ask: "Does this accurately capture the feature? Any adjustments needed?"

## Step 3: Break Down into Tasks

Analyze the feature and propose a task breakdown:

- Group tasks by area: Backend, Frontend, Docs, Testing
- Keep tasks small (1-3 days of work)
- Use actionable titles: "Add X", "Create Y", "Update Z"
- Identify the logical order and dependencies between tasks

Present the proposed tasks and ask for feedback before finalizing.

## Step 4: Generate Jira Output

For the epic:

```text
EPIC
Title: [Feature name]
Description: [Problem + solution summary]
Component: [Primary component]
Labels: product-spec
```

For each task:

```text
TASK
Title: [Actionable title]
Description:
  Context: [Brief context]
  Acceptance Criteria:
  - [Testable criterion 1]
  - [Testable criterion 2]
Parent: [Epic title]
Component: [backend|frontend|docs|infra]
Points: [1|2|3|5|8]
```

## Guidelines

- Story points: 1=trivial, 2=small, 3=medium, 5=large, 8=needs splitting
- Each task should have clear, verifiable acceptance criteria
- Frontend tasks should reference any mockups provided
- Backend tasks should note API changes if applicable
