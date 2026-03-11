---
description: Display kanban dashboard for work package status, with optional browser-based view.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Outline

This command displays the current status of all work packages for the feature, both as a terminal summary and optionally as a browser-based kanban board.

0. **Check for stop/kill request**:
   - If `$ARGUMENTS` contains `stop`, `kill`, or `--kill`, stop the running dashboard:
     ```bash
     python dev/spec-kitty/kittify/scripts/dashboard.py --kill
     ```
   - Report that the dashboard has been stopped and exit — do NOT continue to the remaining steps.

1. **Determine feature**:
   - Parse `$ARGUMENTS` for an optional feature/branch name
   - If not provided, use the current git branch name
   - Verify `dev/spec-kitty/work-packages/<branch-name>/` exists

2. **Read all WP files** from `dev/spec-kitty/work-packages/<branch-name>/`:
   - Parse YAML frontmatter from each WP (id, lane, assigned_to, agent)
   - Extract title from heading
   - Count acceptance criteria per WP

3. **Display terminal summary**:

   First, run the status script:
   ```bash
   dev/spec-kitty/kittify/scripts/manage-workpackages.sh status <branch-name>
   ```

   Then display a detailed kanban view:

   ```
   ┌─────────────┬─────────────┬─────────────┬─────────────┐
   │   PLANNED   │    DOING    │ FOR REVIEW  │    DONE     │
   ├─────────────┼─────────────┼─────────────┼─────────────┤
   │ WP03        │ WP01 (agent)│ WP02        │             │
   │ WP04        │             │             │             │
   │ WP05        │             │             │             │
   └─────────────┴─────────────┴─────────────┴─────────────┘
   Progress: 0/5 done (0%)
   ```

   Also list each WP with its title:
   ```bash
   dev/spec-kitty/kittify/scripts/manage-workpackages.sh list <branch-name>
   ```

4. **Launch browser dashboard** (optional):

   If the user requests it or the environment supports it:

   ```bash
   python dev/spec-kitty/kittify/scripts/dashboard.py --feature <branch-name> &
   ```

   Report:
   - Dashboard URL: `http://localhost:5050`
   - How to stop: `/kitty-spec.dashboard stop`
   - Auto-refreshes every 5 seconds

5. **Suggest next actions** based on current state:
   - WPs in `planned` with met dependencies -> "Ready to start: `/kitty-spec.implement <WP_ID>`"
   - WPs in `for_review` -> "Ready for review: `/kitty-spec.review <WP_ID>`"
   - WPs in `done` -> "Ready to merge: `/kitty-spec.merge <WP_ID>`"
   - All WPs `done` -> "All work packages complete! Run `/kitty-spec.merge --all` to merge everything"
