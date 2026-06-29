# Changelog — preset collection

Release history for the `presets/` directory, taken as a unit.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this collection adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-05-20

### Added
- **`taskstoissues-jira`** (preset version `1.0.0`) — initial release of
  the collection's first preset. Spec-kit preset
  (`schema_version: "1.0"`, `requires.speckit_version: ">=0.8.0"`) that
  declares one command override under `provides.templates`:
  `type: command`, `name: speckit.taskstoissues`,
  `file: commands/speckit.taskstoissues.md`,
  `replaces: speckit.taskstoissues` (default `replace` strategy).
  Installable independently via:

  ```bash
  specify preset add taskstoissues-jira \
    --from https://github.com/opsmill/opsmill-speckit/archive/refs/heads/main.zip \
    --subdir presets/taskstoissues-jira
  ```

  Overrides the native `/speckit.taskstoissues` to fan `tasks.md` out
  into Jira issues under a single Epic — one issue per `## Phase N:`
  block, with `Blocks` links derived from `T<NNN>` mentions
  (transitively reduced). Talks to Atlassian through the Atlassian MCP.
  Project config lives at `dev/jira.yml` in the consumer repo; the
  assignee is the user authenticated to the Atlassian MCP (resolved via
  `atlassianUserInfo`). See
  [`taskstoissues-jira/README.md`](taskstoissues-jira/README.md) for the
  full configuration model and behavior.

### Provenance
`taskstoissues-jira` is ported from the Infrahub preset in
[opsmill/infrahub#9208](https://github.com/opsmill/infrahub/pull/9208).
Generalized for cross-repo reuse:
- Project key + Epic key regex driven by `default_project_key` from
  config rather than hardcoded `IFC`.
- Custom field IDs reduced to placeholders (`customfield_XXXXX`);
  operator resolves real IDs via `getJiraIssueTypeMetaWithFields`.
- Preset id renamed from `infrahub` to `taskstoissues-jira` so the
  install path reads as a portable Jira-flavored override of
  `speckit.taskstoissues` rather than a single-product preset.
