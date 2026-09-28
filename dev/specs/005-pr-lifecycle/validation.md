# Validation status

## Passed locally

- `git diff --check`: no whitespace errors in the tracked workflow diff.
- `uv --cache-dir /tmp/ifc-3240-uv-cache tool run --from yamllint yamllint -s .github/workflows/manage-stale-prs.yml`:
  workflow YAML lint passed; no project dependency was added.
- Pinned-source fixture `node dev/specs/005-pr-lifecycle/evidence/stale-repro.mjs`: 26 assertions passed against
  the pinned upstream processor and state method bodies. See [research](research.md) for scope
  and limitations. Node uses its experimental TypeScript stripping API for this investigation.
- Jira description and supplied handoff were compared against the specification; see
  [alignment check](alignment-check.md).

- `markdownlint-cli2 'dev/specs/005-pr-lifecycle/**/*.md' --config .markdownlint-cli2.yaml`:
  all 13 Markdown documents passed with zero issues.
- `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks`:
  resolved the feature and all planning artifacts successfully.
- Independent Spec Kit critique: both must-address gaps and five recommendations incorporated;
  [report](critiques/critique-20260928.md). Task-format validation found 32 sequential unchecked tasks.
- Agent-context hook refreshed `CLAUDE.md` to the plan. Optional automatic commit hooks are disabled
  in repository configuration; no local checkpoint commit was created in this planning stage.

## Pending

- Companion implementation/integration tests, workflow action lint, and applicable full
  pre-CI checks. The focused checks above do not constitute a completed pre-CI run.
- Full restoration observability, API budget measurement under the combined workflow, and hosted
  cache save/restore verification. The current budget is provisional, as described in research.
- Local commits and PR delivery. No push, merge, or production workflow dispatch has occurred.
- Authorized production rollout and the next scheduled run before claiming production recovery.

The current workflow diff changes only cache permissions, concurrency, and operation budget.
It preserves the pinned action, repository guard, issue exclusions, and disabled PR closure.
