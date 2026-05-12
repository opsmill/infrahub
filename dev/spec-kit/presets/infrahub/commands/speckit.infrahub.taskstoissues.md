---
description: "Convert tasks.md into Jira issues under a single Epic"
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

2. **Load preset configuration**:
   - Read shared config from `dev/spec-kit/presets/infrahub/config/jira.yml` (preferred) or `.specify/presets/infrahub/config/jira.yml` (installed copy) — try the installed copy first, fall back to the source copy. Expected keys: `cloud`, `default_project_key`, `default_issue_type`, `custom_fields.*`, `labels_default`.

     > [!CAUTION]
     > If any `custom_fields.*` value still equals `customfield_XXXXX`, abort with: `> config/jira.yml still has placeholder custom field IDs. Resolve real IDs with mcp__claude_ai_Atlassian__getJiraIssueTypeMetaWithFields and update the file before re-running.` Do not invent IDs.

   - Resolve the per-user override:
     - Run `git config user.email` and slugify the result: lowercase, replace every non-alphanumeric character with `-` (e.g. `pol@opsmill.com` → `pol-opsmill-com`).
     - Load `dev/spec-kit/presets/infrahub/templates/overrides/<slug>.yml` (or the installed-copy equivalent under `.specify/presets/infrahub/`).
     - If the file is missing, prompt: `> No override found for <slug>. Copy templates/overrides/example.yml to templates/overrides/<slug>.yml and fill in assignee.email + team before retrying.` Stop. Do not silently default.

3. **Resolve Atlassian cloud id**: Call `mcp__claude_ai_Atlassian__getAccessibleAtlassianResources` once and match `cloud` from the shared config against the returned site URLs to obtain `cloudId`.

   > [!CAUTION]
   > If `cloudId` cannot be resolved, or `getAccessibleAtlassianResources` returns more than one site without a unique match to the configured `cloud`, abort with: `> Multiple Atlassian sites accessible — pin one in config/jira.yml under 'cloud' before re-running.`

4. **Resolve the Epic key**:
   1. Run `git rev-parse --abbrev-ref HEAD`. Match `/[Ii][Ff][Cc]-(\d+)/` against the branch name and uppercase the match (e.g. `pmi-ifc-2521-auto-create-groups` → `IFC-2521`).
   2. If the branch yields no match, test `$ARGUMENTS` against the same pattern.
   3. If still no match, prompt: `> Provide the Jira Epic for these tasks (e.g. IFC-2521):` and wait for input. Validate the input matches `[Ii][Ff][Cc]-\d+`.
   4. Validate the resolved key by calling `mcp__claude_ai_Atlassian__getJiraIssue` and confirming `fields.issuetype.name == "Epic"`. Abort if it is not an Epic.

5. **Resolve assignee account id**: From the per-user override read `assignee.email`. Call `mcp__claude_ai_Atlassian__lookupJiraAccountId` once with that email and `cloudId`. Cache the returned `accountId` for the duration of this run.

   > [!CAUTION]
   > If `lookupJiraAccountId` returns no match, abort with: `> Assignee email <email> not found in Atlassian. Fix templates/overrides/<slug>.yml or use a valid Atlassian-linked email before re-running.` Do not create any issues.

6. **Resolve team UUID**: From the per-user override read `team.id` and `team.name`. Jira's Atlassian Teams picker (`customfield_10001`) only accepts a UUID — `team.name` is kept in the override file as a human label/comment, never sent to Jira.

   - If `team.id` is set, use it as-is.
   - If `team.id` is empty or missing, resolve it once via Atlassian:
     1. Call `mcp__claude_ai_Atlassian__searchJiraIssuesUsingJql` with:
        - `cloudId` from step 3
        - `jql = 'project = <default_project_key> AND "Team[Team]" is not EMPTY ORDER BY created DESC'`
        - `fields = ["customfield_10001"]`
        - `maxResults = 20`
     2. Scan the returned issues' `customfield_10001.name` for an exact case-insensitive match to the override's `team.name`. Extract the matching `customfield_10001.id` (the UUID).
     3. If a match is found, persist the UUID back into the per-user override file at `team.id` so future runs skip this lookup, and use that UUID for issue creation.
     4. If no match is found, abort with: `> Team '<team.name>' not found in Atlassian (searched recent issues in <default_project_key>). Set team.id explicitly in templates/overrides/<slug>.yml before re-running.` Do not create any issues.

   Pass the resolved value to `createJiraIssue` as a **bare UUID string** (e.g. `"customfield_10001": "079e72e1-..."`). The object form `{"id": "<uuid>"}` and the name form (`"Backend Team"`) are both rejected by Jira's Teams picker — confirmed empirically: the bare-string form is the only one that works.

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
   - `summary` = `"[<feature-id> P<phase_number>] <phase_title>"` where `<feature-id>` is the JPD/Jira reference parsed from the branch name (e.g. `INFP-556`, `IFC-2521`) — fall back to the Epic key from step 4 if no JPD reference is present. Example: `"[INFP-556 P3] US1 (P1 MVP) — Auto-create groups …"`.
   - `description` composed in this order:
     1. The `goal_block` (if any).
     2. The `independent_test_block` (if any).
     3. A `## Tasks` section containing the phase's task lines as a markdown checklist — each entry is the verbatim `- [ ] T<NNN> …` line.
     4. A `## Files` section listing each affected path from `files` as a bullet.
     5. A `## Exit criteria` section reproducing `exit_criteria` (if any).
     6. A trailing line `_Source:_ <relative path from repo root to tasks.md>`.
   - `additional_fields`:
     - `assignee`: `{ accountId: <resolved accountId> }`
     - `labels`: union of `labels_default` (shared config) + `labels` (per-user override) + `US<story>` if the phase has a `story` value
     - `custom_fields`:
       - `<custom_fields.epic_link>`: `<Epic key from step 4>` (e.g. `customfield_10014: "IFC-2521"`)
       - `<custom_fields.team>`: the bare UUID string resolved in step 6 (e.g. `customfield_10001: "079e72e1-..."`). Never send the object form `{"id": "<uuid>"}` and never send `team.name`.

   Record `phase_number -> issueKey` in an in-memory map.

   > [!CAUTION]
   > UNDER NO CIRCUMSTANCES CREATE ISSUES IN A PROJECT OTHER THAN `default_project_key` FROM `config/jira.yml`.

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

   Example shape (from the INFP-556 run): 10 direct edges across 8 phases — `P1 -> P2`; `P2 -> P3, P6`; `P3 -> P4, P5, P7`; `P4 -> P7`; `P5, P6, P7 -> P8`.

   Phase headers and `[P]` markers remain sequencing hints only — they are **not** first-class dependencies and must not produce link edges. The link source is exclusively `T<NNN>` mentions, now resolved at phase granularity.

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
