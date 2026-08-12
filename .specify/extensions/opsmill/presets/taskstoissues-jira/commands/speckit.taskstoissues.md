---
description: Convert tasks.md into Jira issues under a single Epic (one Jira issue per phase).
---


## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Pre-Execution Checks

**Check for extension hooks (before tasks-to-issues conversion)**:
- Check if `.specify/extensions.yml` exists in the project root.
- If it exists, read it and look for entries under the `hooks.before_taskstoissues` key
- If the YAML cannot be parsed or is invalid, skip hook checking silently and continue normally
- Filter out hooks where `enabled` is explicitly `false`. Treat hooks without an `enabled` field as enabled by default.
- For each remaining hook, do **not** attempt to interpret or evaluate hook `condition` expressions:
  - If the hook has no `condition` field, or it is null/empty, treat the hook as executable
  - If the hook defines a non-empty `condition`, skip the hook and leave condition evaluation to the HookExecutor implementation
- When constructing slash commands from hook command names, replace dots (`.`) with hyphens (`-`). For example, `speckit.git.commit` → `/speckit-git-commit`.
- For each executable hook, output the following based on its `optional` flag:
  - **Optional hook** (`optional: true`):
    ```
    ## Extension Hooks

    **Optional Pre-Hook**: {extension}
    Command: `/{command}`
    Description: {description}

    Prompt: {prompt}
    To execute: `/{command}`
    ```
  - **Mandatory hook** (`optional: false`):
    ```
    ## Extension Hooks

    **Automatic Pre-Hook**: {extension}
    Executing: `/{command}`
    EXECUTE_COMMAND: {command}

    Wait for the result of the hook command before proceeding to the Outline.
    ```
- If no hooks are registered or `.specify/extensions.yml` does not exist, skip silently

## Outline

1. **Setup**: Run `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` from repo root and parse `FEATURE_DIR` and `AVAILABLE_DOCS` list. All paths must be absolute. Extract the absolute path to `tasks.md` from `FEATURE_DIR`. For single quotes in args like "I'm Groot", use escape syntax: e.g `'I'\''m Groot'` (or double-quote if possible: `"I'm Groot"`).

2. **Load project configuration**:
   - Read the project-level Jira config from `dev/jira.yml` at the repo root. Required keys: `cloud`, `default_project_key`, `default_issue_type`, `custom_fields.epic_link`, `custom_fields.team`, `team.name`, `labels_default`. Optional: `team.id` (cached UUID; auto-populated on first run), additional `custom_fields.*` entries (e.g. `sprint`, `story_points`) for future use.

     > [!CAUTION]
     > If `dev/jira.yml` does not exist, abort with: `> dev/jira.yml not found. Copy .specify/presets/taskstoissues-jira/templates/jira.example.yml to dev/jira.yml at the repo root, fill in every REQUIRED field, and commit before re-running.`

     > [!CAUTION]
     > If any required top-level key is missing from `dev/jira.yml`, abort with: `> dev/jira.yml is missing required key '<key>'. See .specify/presets/taskstoissues-jira/templates/jira.example.yml for the full schema.` Do not silently default.

     > [!CAUTION]
     > If `default_project_key` still equals the example placeholder `PROJ`, abort with: `> dev/jira.yml still has placeholder default_project_key 'PROJ'. Set it to your repo's Jira project key before re-running.`

     > [!CAUTION]
     > If `custom_fields.epic_link` or `custom_fields.team` equals `customfield_XXXXX`, abort with: `> dev/jira.yml still has placeholder custom field IDs. Resolve real IDs with mcp__claude_ai_Atlassian__getJiraIssueTypeMetaWithFields and update the file before re-running.` Do not invent IDs.

3. **Resolve Atlassian cloud id**: Call `mcp__claude_ai_Atlassian__getAccessibleAtlassianResources` once and match `cloud` from `dev/jira.yml` against the returned site URLs to obtain `cloudId`.

   > [!CAUTION]
   > If `cloudId` cannot be resolved, or `getAccessibleAtlassianResources` returns more than one site without a unique match to the configured `cloud`, abort with: `> Multiple Atlassian sites accessible — pin one in dev/jira.yml under 'cloud' before re-running.`

4. **Resolve the Epic key**:
   1. Run `git rev-parse --abbrev-ref HEAD`. Build a case-insensitive regex from `default_project_key` of the form `<default_project_key>-\d+` and match it against the branch name; uppercase the project-key portion of the match (e.g. with `default_project_key=IFC`, `pmi-ifc-2521-auto-create-groups` → `IFC-2521`).
   2. If the branch yields no match, test `$ARGUMENTS` against the same pattern.
   3. If still no match, prompt: `> Provide the Jira Epic for these tasks (e.g. <default_project_key>-1234):` and wait for input. Validate the input matches the same `<default_project_key>-\d+` pattern (case-insensitive).
   4. Validate the resolved key by calling `mcp__claude_ai_Atlassian__getJiraIssue` and confirming `fields.issuetype.name == "Epic"`. Abort if it is not an Epic.

5. **Resolve assignee account id**: Call `mcp__claude_ai_Atlassian__atlassianUserInfo` once and read `account_id` from the response. That is the accountId of the user currently authenticated to the Atlassian MCP — the same user running the command — and becomes the assignee for every issue created in this run. Cache it for the duration of this run.

   > [!CAUTION]
   > If `atlassianUserInfo` fails or returns no `account_id`, abort with: `> Atlassian MCP not authenticated. Authenticate the Atlassian MCP server before re-running.` Do not create any issues.

6. **Resolve team UUID**: From `dev/jira.yml` read `team.name` and `team.id`. Jira's Atlassian Teams picker (`custom_fields.team`) only accepts a UUID — `team.name` is kept in `dev/jira.yml` as a human label, never sent to Jira.

   - If `team.id` is set, use it as-is.
   - If `team.id` is empty or missing, resolve it once via Atlassian:
     1. Call `mcp__claude_ai_Atlassian__searchJiraIssuesUsingJql` with:
        - `cloudId` from step 3
        - `jql = 'project = <default_project_key> AND "Team[Team]" is not EMPTY ORDER BY created DESC'`
        - `fields = ["<custom_fields.team>"]`
        - `maxResults = 20`
     2. Scan the returned issues' `<custom_fields.team>.name` for an exact case-insensitive match to `team.name` from `dev/jira.yml`. Extract the matching `<custom_fields.team>.id` (the UUID).
     3. If a match is found, persist the UUID back into `dev/jira.yml` at `team.id` so future runs skip this lookup, and use that UUID for issue creation.
     4. If no match is found, abort with: `> Team '<team.name>' not found in Atlassian (searched recent issues in <default_project_key>). Set team.id explicitly in dev/jira.yml before re-running.` Do not create any issues.

   Pass the resolved value to `createJiraIssue` as a **bare UUID string** (e.g. `"<custom_fields.team>": "079e72e1-..."`). The object form `{"id": "<uuid>"}` and the name form (e.g. `"Backend Team"`) are both rejected by Jira's Teams picker.

7. **Parse `tasks.md` by phase**: Walk the file top-to-bottom and split it into phases, where a phase starts at a `## Phase <N>: <title>` header and ends at the next `## Phase` header (or end of file). For each phase capture:
   - `phase_number` (`<N>`) and `phase_title` (`<title>`) from the header line
   - `goal_block`: the `**Goal**:` paragraph immediately under the header, if present
   - `independent_test_block`: the `**Independent Test**:` paragraph, if present
   - `tasks`: every unchecked `- [ ] T<NNN> …` line inside the phase, preserved verbatim including its `[P]` and `[US<N>]` tags and trailing file paths. Skip tasks already checked (`- [x]`).
   - `story`: if the phase header matches `User Story <n>` **or** every child task carries the same `[US<n>]` tag, capture `<n>` as the phase's user-story number; otherwise leave unset.
   - `files`: the union of affected file paths across the phase's task lines (trailing the summary or on subsequent indented lines), deduplicated and sorted.
   - `exit_criteria`: any trailing `**Exit criteria**` / `**Checkpoint**` paragraph in the phase, if present.

   Skip phases that contain zero unchecked tasks. Build an ordered list `phases: [{phase_number, phase_title, story, goal_block, independent_test_block, tasks, files, exit_criteria}]`.

8. **Create one Jira issue per phase**: For each parsed phase, call `mcp__claude_ai_Atlassian__createJiraIssue` with:
   - `cloudId` from step 3.
   - `projectKey` from `default_project_key`.
   - `issueTypeName` from `default_issue_type`.
   - `summary` = `phase_title` from step 7, with spec-kit-internal taxonomy tags stripped:
     - `US<N>` tags — already captured as a `US<N>` label below.
     - `P<N>` tags — already captured by the `Blocks` links in step 9.
     - Bracketed `[…]` decorations carrying the same data (`[P]`, `[US<N>]`).

     **Keep** meaningful tier markers (`MVP`, `Beta`, `Alpha`, etc.) and the descriptive feature text. Drop surrounding parentheses if their only remaining content is itself dropped (e.g. `(P1 MVP)` → `MVP`, but `(Beta)` stays as `(Beta)`).
   - Examples:
     - `Phase 3: US1 (P1 MVP) — Auto-create groups` → `"MVP — Auto-create groups"`
     - `Phase 1: US2 — Bulk import` → `"Bulk import"`
     - `Phase 2: (Beta) Pagination on lists` → `"(Beta) Pagination on lists"`
   - `description` composed in this order:
     1. The `goal_block` (if any).
     2. The `independent_test_block` (if any).
     3. A `## Tasks` section containing the phase's task lines as a markdown checklist — each entry is the verbatim `- [ ] T<NNN> …` line.
     4. A `## Files` section listing each affected path from `files` as a bullet.
     5. A `## Exit criteria` section reproducing `exit_criteria` (if any).
     6. A trailing line `_Source:_ <relative path from repo root to tasks.md>`.
   - `additional_fields`:
     - `assignee`: `{ accountId: <resolved accountId> }`
     - `labels`: `labels_default` (from `dev/jira.yml`) + `US<story>` if the phase has a `story` value
     - `custom_fields`:
       - `<custom_fields.epic_link>`: `<Epic key from step 4>` (e.g. `customfield_10014: "IFC-2521"`)
       - `<custom_fields.team>`: the bare UUID string resolved in step 6 (e.g. `customfield_10001: "079e72e1-..."`). Never send the object form `{"id": "<uuid>"}` and never send `team.name`.

   Record `phase_number -> issueKey` in an in-memory map.

   > [!CAUTION]
   > UNDER NO CIRCUMSTANCES CREATE ISSUES IN A PROJECT OTHER THAN `default_project_key` FROM `dev/jira.yml`.

   > [!CAUTION]
   > If any `createJiraIssue` call fails mid-run, **stop immediately**. Print the partial `phase_number -> issueKey` map and instruct: `> Partial run — delete the issues listed above manually in Jira before re-running. This skill is not idempotent in v1.` Do not retry, do not roll back automatically.

9. **Create phase-level dependency links**: After every phase issue exists, derive the phase dependency graph from `T<NNN>` mentions inside each phase's task bodies:
   1. Build a `tid -> phase_number` index from the parse in step 7 — every `T<NNN>` owned by a phase maps to that phase's `phase_number`.
   2. For each phase `P`, scan its task bodies for `T<NNN>` mentions whose owning phase is **not** `P` itself. For each such mention, emit a directed edge `(phase_of_mentioned_tid) -> P` (the phase that owns the cited task blocks `P`).
   3. Deduplicate edges, then apply a transitive reduction so only direct edges remain. If the graph has `A -> B`, `B -> C`, and `A -> C`, drop `A -> C`.
   4. For each surviving edge `(blocker_phase) -> (blocked_phase)`, call `mcp__claude_ai_Atlassian__createIssueLink` with:
      - `type` = `"Blocks"`
      - `inwardIssue` = the blocker phase's Jira key (from the `phase_number -> issueKey` map)
      - `outwardIssue` = the blocked phase's Jira key

   Phase headers and `[P]` markers remain sequencing hints only — they are **not** first-class dependencies and must not produce link edges. The link source is exclusively `T<NNN>` mentions.

10. **Summary output**: Print a markdown table mapping `Phase` → `IssueKey` → `Summary`. Do not edit `tasks.md` automatically; the user can paste the mapping back if they want.

## Post-Execution Checks

**Check for extension hooks (after tasks-to-issues conversion)**:
Check if `.specify/extensions.yml` exists in the project root.
- If it exists, read it and look for entries under the `hooks.after_taskstoissues` key
- If the YAML cannot be parsed or is invalid, skip hook checking silently and continue normally
- Filter out hooks where `enabled` is explicitly `false`. Treat hooks without an `enabled` field as enabled by default.
- For each remaining hook, do **not** attempt to interpret or evaluate hook `condition` expressions:
  - If the hook has no `condition` field, or it is null/empty, treat the hook as executable
  - If the hook defines a non-empty `condition`, skip the hook and leave condition evaluation to the HookExecutor implementation
- When constructing slash commands from hook command names, replace dots (`.`) with hyphens (`-`). For example, `speckit.git.commit` → `/speckit-git-commit`.
- For each executable hook, output the following based on its `optional` flag:
  - **Optional hook** (`optional: true`):
    ```
    ## Extension Hooks

    **Optional Hook**: {extension}
    Command: `/{command}`
    Description: {description}

    Prompt: {prompt}
    To execute: `/{command}`
    ```
  - **Mandatory hook** (`optional: false`):
    ```
    ## Extension Hooks

    **Automatic Hook**: {extension}
    Executing: `/{command}`
    EXECUTE_COMMAND: {command}
    ```
- If no hooks are registered or `.specify/extensions.yml` does not exist, skip silently
