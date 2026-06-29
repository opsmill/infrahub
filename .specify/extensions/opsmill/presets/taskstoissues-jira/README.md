# taskstoissues-jira

A spec-kit preset that **overrides** the native `speckit.taskstoissues` command with a Jira-flavored implementation. One Jira issue is created per `## Phase N:` block in `tasks.md` (not per task line); inter-task `T<NNN>` mentions are resolved at phase granularity and emitted as `Blocks` issue links between phase issues (transitively reduced). All Atlassian traffic goes through the Atlassian MCP.

## Install

```bash
specify preset add taskstoissues-jira \
  --from https://github.com/opsmill/opsmill-speckit/archive/refs/heads/main.zip \
  --subdir presets/taskstoissues-jira
```

Local development install (from a working tree):

```bash
specify preset add --dev ./presets/taskstoissues-jira
```

After install, the preset's files live at `.specify/presets/taskstoissues-jira/` in the consumer repo, and `/speckit.taskstoissues` resolves to this preset's command body.

## Configuration model

One file: `dev/jira.yml` at the consumer repo root, committed. It holds every Jira parameter the preset reads — `cloud`, `default_project_key`, `default_issue_type`, `custom_fields.*`, `team.name` / `team.id`, `labels_default`. The assignee for every created issue is the user authenticated to the Atlassian MCP, resolved via `atlassianUserInfo`.

## One-time setup (per consumer repo)

1. Copy the project template into place:

   ```bash
   mkdir -p dev
   cp .specify/presets/taskstoissues-jira/templates/jira.example.yml dev/jira.yml
   ```

2. Edit `dev/jira.yml` and fill in every REQUIRED field:

   - `cloud` — your Atlassian site URL (e.g. `https://opsmill.atlassian.net/`). Matched against `getAccessibleAtlassianResources` to resolve `cloudId`. The shipped example points at `https://opsmill.atlassian.net/`; replace if your tenant differs.
   - `default_project_key` — your repo's Jira project key. The shipped placeholder `PROJ` aborts on purpose.
   - `default_issue_type` — issue type for created phase issues (e.g. `Task`, `Story`).
   - `custom_fields.epic_link` + `custom_fields.team` — real custom field IDs for your Jira instance. Resolve with `mcp__claude_ai_Atlassian__getJiraIssueTypeMetaWithFields` and replace each `customfield_XXXXX` placeholder.
   - `team.name` — the Atlassian Team for every created issue. Leave `team.id` empty on first run; the command resolves it from `name` and writes the UUID back. Expect a `dev/jira.yml` diff after the first run — commit it.
   - `labels_default` — labels stamped on every created issue (e.g. `[spec-kit]`).

3. Commit `dev/jira.yml`. The whole repo shares it.

Re-running `specify preset add taskstoissues-jira` only touches `.specify/presets/taskstoissues-jira/`, so `dev/jira.yml` is never clobbered by preset updates.

## Epic resolution

The command parses the current branch name for `<default_project_key>-\d+` (case-insensitive), falling back to `$ARGUMENTS`, then to an interactive prompt. The matched key is validated as an Epic via `getJiraIssue`.

## Failure mode

The run stops at the first `createJiraIssue` / `createIssueLink` error and prints the partial `phase_number → IssueKey` map. The command is **not** idempotent — delete the listed issues in Jira manually before retrying.

## Provenance

Ported from the Infrahub preset introduced in [opsmill/infrahub#9208](https://github.com/opsmill/infrahub/pull/9208). Generalized for cross-repo reuse: the Infrahub-specific project key (`IFC`) and custom field IDs become placeholders consumers fill in via `dev/jira.yml`.
