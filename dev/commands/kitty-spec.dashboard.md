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

2. **Kill any existing dashboard and launch the browser dashboard**:

   Always launch the dashboard immediately — it handles empty/missing work packages gracefully.

   ```bash
   python dev/spec-kitty/kittify/scripts/dashboard.py --kill 2>/dev/null
   nohup python dev/spec-kitty/kittify/scripts/dashboard/server.py --feature <branch-name> > /dev/null 2>&1 &
   ```

   Report:
   - Dashboard URL: `http://localhost:5050`
   - How to stop: `/kitty-spec.dashboard stop`
   - Auto-refreshes every 5 seconds

3. **Display terminal summary** (only if work packages exist):

   If `dev/spec-kitty/work-packages/<branch-name>/` exists and contains WP files:

   Run the status script:
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

   If no work packages exist, simply note that no work packages have been generated yet.

4. **Suggest next actions** based on current state:
   - No WPs exist -> "Generate work packages with `/kitty-spec.tasks`"
   - WPs in `planned` with met dependencies -> "Ready to start: `/kitty-spec.implement <WP_ID>`"
   - WPs in `for_review` -> "Ready for review: `/kitty-spec.review <WP_ID>`"
   - WPs in `done` -> "Ready to merge: `/kitty-spec.merge <WP_ID>`"
   - All WPs `done` -> "All work packages complete! Run `/kitty-spec.merge --all` to merge everything"
