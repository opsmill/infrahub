---
description: Merge completed work packages and clean up worktrees.
handoffs:
  - label: View Dashboard
    agent: kitty-spec.dashboard
    prompt: Show the current work package status
  - label: Create PR
    agent: git-commit
    prompt: Commit and push changes for PR creation
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Outline

This command merges approved work packages back into the feature branch and cleans up worktrees.

1. **Parse arguments**:
   - `$ARGUMENTS` may contain:
     - A specific WP ID (e.g., `WP01`) -- merge just that WP
     - `--all` flag -- merge all done WPs
     - Empty -- prompt user to choose

2. **Determine feature context**:
   - Get current branch name from git
   - List all WPs from `dev/spec-kitty/work-packages/<branch-name>/`
   - Parse each WP's frontmatter for lane status

3. **Pre-merge validation**:
   - All targeted WPs must have `lane: done`
   - If `--all`: verify ALL WPs are done. If not, list remaining WPs and their lanes
   - For each WP to merge, check for potential merge conflicts:
     - Compare "Files To Modify" across WPs being merged
     - If overlapping files, warn about potential conflicts and suggest merge order

4. **Merge WPs** (in dependency order):

   For each WP to merge:

   a. Ensure we're on the feature branch:
      ```bash
      git checkout <feature-branch>
      ```

   b. Merge the worktree branch:
      ```bash
      git merge kitty/<branch>-<WP_ID> --no-ff -m "feat: merge WP## - <WP title>"
      ```

   c. Handle conflicts:
      - If merge conflicts occur, report the conflicting files to the user
      - Do NOT auto-resolve conflicts -- present them for manual resolution
      - After user resolves: `git add <resolved-files> && git commit`

   d. Clean up worktree:
      ```bash
      dev/spec-kitty/kittify/scripts/manage-workpackages.sh cleanup-worktree <branch> <WP_ID>
      ```

5. **Post-merge validation**:
   - Run formatting: `uv run invoke format` (Python), `cd frontend/app && npm run biome:fix` (frontend)
   - Run linting: `uv run invoke lint` (Python)
   - Run relevant tests if identifiable
   - Report any issues found

6. **Report merge summary**:
   ```markdown
   ## Merge Summary

   | WP | Title | Status | Conflicts |
   |----|-------|--------|-----------|
   | WP01 | ... | Merged | None |
   | WP02 | ... | Merged | 2 files resolved |

   **Post-merge checks**: Lint PASS, Format PASS
   **Worktrees cleaned**: WP01, WP02
   **Remaining WPs**: WP03 (planned), WP04 (doing)
   ```

7. **Suggest next steps**:
   - If all WPs merged: suggest `/git-commit` to commit and push for PR
   - If WPs remain: suggest `/kitty-spec.implement` for next planned WP
   - If review needed: suggest `/kitty-spec.review` for for_review WPs

## Merge Rules

- Always use `--no-ff` to preserve WP merge history
- Merge in dependency order (WPs with no deps first)
- Never force-merge or auto-resolve conflicts
- Clean up worktrees only after successful merge
- Run formatters/linters after all merges complete (not after each individual merge)
