---
description: Structured code review for a completed work package with quality gates.
handoffs:
  - label: Merge Work Package
    agent: kitty-spec.merge
    prompt: Merge the approved work package
    send: true
  - label: Fix Issues
    agent: kitty-spec.implement
    prompt: Fix the review issues found in the work package
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Outline

This command performs a structured code review on a completed work package, checking acceptance criteria and quality gates before approving for merge.

1. **Select work package**:
   - Parse `$ARGUMENTS` for a WP ID (e.g., `WP01`). If not provided:
   - Determine the current branch name from git
   - Scan `dev/spec-kitty/work-packages/<branch-name>/` for WP files
   - Auto-select the first WP with `lane: for_review` (in numerical order)
   - If no WPs are in `for_review`, report current status

2. **Validate state**:
   - Read the selected WP file
   - Verify its `lane` is `for_review`
   - If not, report the current lane and suggest the appropriate action

3. **Load review context**:
   - Read the WP file: acceptance criteria, tasks, files to modify
   - Read `FEATURE_DIR/plan.md` for architecture expectations
   - Read `.specify/memory/constitution.md` for quality principles
   - Get the worktree branch name: `kitty/<branch>-<WP_ID>`

4. **Gather changes**:
   - Run `git diff main...<worktree-branch>` to see all changes (or diff against the feature branch)
   - List all files modified in the worktree branch
   - Count lines added/removed

5. **Quality Gates** - check each and report pass/fail:

   | Gate | Check | Pass Criteria |
   |------|-------|--------------|
   | Acceptance Criteria | Compare WP acceptance_criteria against implementation | All criteria demonstrably met |
   | Scope Compliance | Compare changed files against WP "Files To Modify" | No unintended file changes outside WP scope |
   | Constitution | Review against project principles | Code follows all applicable principles |
   | Tests | Check for new/updated tests | Tests exist for new functionality |
   | Security | Scan for secrets/credentials | No sensitive data committed |
   | Linting | Run linters on changed files | `uv run invoke lint` (Python) or `npm run biome:fix` (frontend) passes |
   | Task Completion | Check tasks marked [X] in tasks.md | All WP tasks completed |

6. **Decision**:

   - **APPROVE** (all gates pass):
     1. Transition WP to `done`:
        ```bash
        dev/spec-kitty/kittify/scripts/manage-workpackages.sh transition <branch> <WP_ID> done
        ```
     2. Report: WP approved, ready for `/kitty-spec.merge <WP_ID>`

   - **REQUEST CHANGES** (any gate fails):
     1. Transition WP back to `planned`:
        ```bash
        dev/spec-kitty/kittify/scripts/manage-workpackages.sh transition <branch> <WP_ID> planned
        ```
     2. Append failure details to the WP activity log
     3. Report: which gates failed, specific issues to fix, suggest `/kitty-spec.implement <WP_ID>` to address

7. **Present results** with a clear pass/fail table:

   ```markdown
   ## Review Results: WP##

   | Gate | Status | Notes |
   |------|--------|-------|
   | Acceptance Criteria | PASS/FAIL | details |
   | Scope Compliance | PASS/FAIL | details |
   | Constitution | PASS/FAIL | details |
   | Tests | PASS/FAIL | details |
   | Security | PASS/FAIL | details |
   | Linting | PASS/FAIL | details |
   | Task Completion | PASS/FAIL | details |

   **Decision**: APPROVED / CHANGES REQUESTED
   ```

## Review Principles

- Be thorough but pragmatic -- minor style issues don't warrant rejection if linting passes
- Focus on correctness, security, and adherence to the plan
- Flag architectural concerns even if not strictly a gate failure
- Out-of-scope changes are a warning, not automatic rejection (sometimes necessary)
