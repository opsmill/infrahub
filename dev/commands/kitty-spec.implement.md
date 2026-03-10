---
description: Implement a work package in an isolated git worktree.
handoffs:
  - label: Review Work Package
    agent: kitty-spec.review
    prompt: Review the completed work package
    send: true
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Outline

This command implements a single work package in an isolated git worktree, enabling parallel development across multiple WPs.

1. **Setup**: Run `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` from repo root and parse FEATURE_DIR and AVAILABLE_DOCS list. All paths must be absolute.

2. **Select work package**:
   - Parse `$ARGUMENTS` for an optional WP ID (e.g., `WP01`). If not provided:
   - Determine the current branch name from git
   - Scan `dev/spec-kitty/work-packages/<branch-name>/` for WP files
   - Auto-select the first WP with `lane: planned` (in numerical order)
   - If no planned WPs exist, report that all WPs are in progress or complete

3. **Validate dependencies**:
   - Read the selected WP file
   - Verify its `lane` is `planned`
   - Check the `Dependencies` section: all referenced WP IDs must have `lane: done`
   - If dependencies are not met, report which WPs are blocking and suggest waiting or working on a different WP

4. **Create worktree** (if not already created):
   ```bash
   dev/spec-kitty/kittify/scripts/manage-workpackages.sh create-worktree <branch> <WP_ID>
   ```

5. **Transition WP to doing**:
   ```bash
   dev/spec-kitty/kittify/scripts/manage-workpackages.sh transition <branch> <WP_ID> doing
   ```

6. **Load implementation context**:
   - Read the WP file: goal, tasks, implementation prompt, files to modify
   - Read `FEATURE_DIR/plan.md` for architecture context
   - Read `FEATURE_DIR/data-model.md` if referenced in the WP
   - Read `FEATURE_DIR/contracts/` if referenced in the WP
   - Read `.specify/memory/constitution.md` for project principles

7. **Display the implementation prompt** from the WP file to establish clear scope.

8. **Execute implementation** in the worktree:
   - Follow the WP's task list sequentially
   - For each task:
     - Implement the change in the worktree directory
     - Mark the task as `[X]` in `FEATURE_DIR/tasks.md`
     - Commit changes in the worktree branch with descriptive messages
   - Stay within the scope defined by "Files To Modify" in the WP
   - If you need to modify files not listed in the WP, note this for the review phase

9. **Post-implementation checks**:
   - Run linting on changed files (`uv run invoke lint` for Python, `cd frontend/app && npm run biome:fix` for frontend)
   - Run relevant unit tests if identifiable
   - Verify no unintended changes outside the WP scope

10. **Transition WP to for_review**:
    ```bash
    dev/spec-kitty/kittify/scripts/manage-workpackages.sh transition <branch> <WP_ID> for_review
    ```

11. **Report**:
    - WP ID and title
    - Worktree branch name (for review/merge)
    - Files changed (list)
    - Tasks completed vs total
    - Any out-of-scope changes made (flagged for review)
    - Suggest running `/kitty-spec.review <WP_ID>` next

## Implementation Rules

- **Scope discipline**: Only modify files listed in the WP's "Files To Modify" section unless absolutely necessary
- **Commit granularity**: One commit per logical change, not one giant commit
- **Test awareness**: If the WP includes test tasks, write tests before or alongside implementation
- **Constitution compliance**: Follow all project principles from the constitution
- **Error handling**: If a task cannot be completed, mark it with a note in tasks.md and continue with remaining tasks
