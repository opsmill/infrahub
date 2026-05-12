---
description: Convert tasks.md into Jira issues under a single Epic
---


<!-- Source: infrahub -->
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
     - If the file is missing, prompt: `> No override found for <slug>. Copy .specify/templates/overrides/example.yml to .specify/templates/overrides/<slug>.yml and fill in assignee.email + team before retrying.` Stop. Do not silently default.

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
   > If `lookupJiraAccountId` returns no match, abort with: `> Assignee email <email> not found in Atlassian. Fix .specify/templates/overrides/<slug>.yml or use a valid Atlassian-linked email before re-running.` Do not create any issues.

6. **Parse `tasks.md`**: Iterate every unchecked `- [ ]` line. Each task line follows the format documented in `dev/skills/speckit-tasks/SKILL.md` and contains:
   - A task id (TID), e.g. `T001`
   - An optional parallel marker `[P]`
   - An optional user-story tag `[US<N>]`
   - A summary line
   - One or more affected file paths trailing the summary or appearing in subsequent indented lines

   Build an ordered list `tasks: [{tid, parallel, story, summary, files, description_body}]`. Skip tasks already checked (`- [x]`).

7. **Create Jira issues**: For each parsed task, call `mcp__claude_ai_Atlassian__createJiraIssue` with:
   - `cloudId` from step 3.
   - `projectKey` from `default_project_key`.
   - `issueTypeName` from `default_issue_type`.
   - `summary` = `"[<TID>] <task summary>"`.
   - `description` = `<task description_body>` + a `## Files` section listing each affected path as a bullet + a final line `_Source:_ <relative path from repo root to tasks.md>`.
   - `additional_fields`:
     - `assignee`: `{ accountId: <resolved accountId> }`
     - `labels`: union of `labels_default` (shared config) + `labels` (per-user override) + the `US<N>` tag if present on the task line
     - `custom_fields`:
       - `<custom_fields.epic_link>`: `<Epic key from step 4>` (e.g. `customfield_10014: "IFC-2521"`)
       - `<custom_fields.team>`: per-user override `team.id` if set, otherwise `team.name`

   Record `tid -> issueKey` in an in-memory map.

   > [!CAUTION]
   > UNDER NO CIRCUMSTANCES CREATE ISSUES IN A PROJECT OTHER THAN `default_project_key` FROM `config/jira.yml`.

   > [!CAUTION]
   > If any `createJiraIssue` call fails mid-run, **stop immediately**. Print the partial `tid -> issueKey` map and instruct: `> Partial run — delete the issues listed above manually in Jira before re-running. This skill is not idempotent in v1.` Do not retry, do not roll back automatically.

8. **Create dependency links**: After every issue exists, walk the task list a second time. For each task whose description body mentions another `TID` (e.g. `depends on T001`), call `mcp__claude_ai_Atlassian__createIssueLink` with:
   - `inwardIssue` = the mentioned task's Jira key
   - `outwardIssue` = the current task's Jira key
   - `type` = `"Blocks"`

   Phase headers and `[P]` markers are sequencing hints only — they are **not** first-class dependencies and must not produce link edges.

9. **Summary output**: Print a markdown table mapping `TID` → `IssueKey` → `Summary`. Do not edit `tasks.md` automatically; the user can paste the mapping back if they want.

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