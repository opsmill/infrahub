---
id: "speckit.checkpoint.commit"
name: "Checkpoint Commit"
description: "Commit changes at meaningful checkpoints throughout the workflow"
---

# /speckit.checkpoint.commit

## Description

Stages all current changes and creates a commit with a descriptive message reflecting the work just completed. This command should be called by the agent at two points during the spec-kit workflow:

1. **After each pre-implementation step** (constitution, specify, clarify, plan, analyze, tasks) — to capture the spec artifacts produced by that step.
2. **During implementation** — at natural checkpoints, such as after completing a task or a logical group of related tasks from the task list.

## When to Commit

### Pre-Implementation Steps

Commit immediately after each of these steps completes:

- After **constitution** — commit the project principles and guidelines
- After **specify** — commit the requirements and user stories
- After **clarify** — commit the resolved clarifications
- After **plan** — commit the technical implementation plan
- After **analyze** — commit the consistency and coverage analysis
- After **tasks** — commit the task breakdown

### During Implementation

Use the task list generated during the tasks step as a reference for when to commit. Good checkpoints include:

- Completing a single task from the task list
- Completing a logical group of closely related tasks
- Finishing a self-contained unit of work (e.g., a new component, a service layer, a set of tests)

The agent should use judgment — the goal is to produce commits that are meaningful and reviewable, not to commit after every single file change.

## Workflow

1. Determine a clear, concise commit message based on the work just completed
2. Stage all current changes (`git add -A`)
3. Commit with the message (`git commit -m "<message>"`)

## Commit Message Guidelines

- For pre-implementation steps, use the step name as a prefix (e.g., `constitution: establish project principles`, `tasks: break down implementation into actionable items`)
- For implementation commits, describe what was built (e.g., `implement user authentication service`, `add product listing page and API routes`)
- Keep messages concise but descriptive enough to understand the scope of the commit

## Exit Criteria

- All current changes are staged and committed
- The commit message accurately reflects the work completed
- The working tree is clean after the commit
