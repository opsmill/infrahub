# Research: Dependency-bump autopilot

## R1. Split untrusted analysis from trusted actions

**Decision**: Two workflows. An agentic workflow (`dependabot-autopilot-analyze`) runs the analysis on the Dependabot `pull_request` event with a read-only token and emits a verdict artifact. A deterministic workflow (`dependabot-autopilot-act`) runs on `workflow_run` of the analysis (and of CI), validates the artifact, and performs every write: report comment, review, labels, reviewer requests, approval, merge, Jira.

**Rationale**:

- Workflows triggered by Dependabot on `pull_request` "receive a read-only `GITHUB_TOKEN` and do not have access to any secrets that are normally available"; only Dependabot secrets are exposed ([Troubleshooting Dependabot on GitHub Actions](https://docs.github.com/en/code-security/dependabot/troubleshooting-dependabot/troubleshooting-dependabot-on-github-actions)).
- `workflow_run` is "able to access secrets and write tokens, even if the previous workflow was not" ([Events that trigger workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)).
- The agent reads upstream changelogs, which are attacker-influenced text. Keeping merge, Jira and Slack credentials out of the agent's job means a prompt injection can at worst produce a wrong verdict, which the deterministic guards (R5, R6) still bound.

**gh-aw feature spike (2026-09-23)**: both features are supported, so the plan's fallback is not needed. A throwaway workflow compiled with 0 errors and 0 warnings on the pinned compiler v0.81.3 (release binary `darwin-arm64`) and on v0.81.6 (the installed `gh aw` extension). Frontmatter used:

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened]
  bots:
    - "dependabot[bot]"
engine: claude
permissions:
  contents: read
  pull-requests: read
safe-outputs:
  jobs:
    emit-verdict:
      description: "Emit the verdict JSON"
      runs-on: ubuntu-latest
      inputs:
        verdict:
          description: "Verdict JSON document"
          required: true
          type: string
      steps:
        - name: Write verdict
          run: echo "done"
```

Compiled result:

| Feature | What the lock file contains |
|---|---|
| `on.bots` | `GH_AW_ALLOWED_BOTS: "dependabot[bot]"` in the `activation` and `pre_activation` jobs |
| `safe-outputs.jobs` | An `emit_verdict` MCP tool (the key's `-` becomes `_`) with a required string `verdict` input, and an `emit_verdict` job that `needs: [agent, detection]`, runs only when the agent emitted that output type, downloads the `agent` artifact and exposes it to the custom steps as `GH_AW_AGENT_OUTPUT` (path to `agent_output.json`) |

Consequences for the analysis workflow: the custom job's steps receive the tool call inside `agent_output.json`, not as an environment variable, so a step must extract the `emit_verdict` item from that file and upload it as the `dependabot-autopilot-verdict` artifact. The job runs after gh-aw's threat-detection job. Compiling needs `--approve` the first time, because strict mode flags `ANTHROPIC_API_KEY` as a new restricted secret.

**Alternatives considered**: One gh-aw workflow using safe outputs for everything. Rejected: gh-aw's `merge-pull-request` safe output "always refuses" merges to the repository default branch, and the default branch is `stable`; it would also require copying the App key into Dependabot secrets.

## R2. Merge must be a custom deterministic step

**Decision**: Approve with `gh pr review --approve` and merge with `gh pr merge --squash --match-head-commit <sha>`, authenticated as a dedicated GitHub App.

**Rationale**: gh-aw's `merge-pull-request` refuses default-branch merges ([gh-aw safe outputs for pull requests](https://github.com/github/gh-aw/blob/main/docs/src/content/docs/reference/safe-outputs-pull-requests.md)). `--match-head-commit` makes the merge fail if the head moved after evaluation, which enforces FR-004's "analysed commit is still the head" atomically. Squash matches how Dependabot PRs land today (`380f6d15f chore(deps): bump the uv group … (#10689)`).

**Alternatives considered**: `gh pr merge --auto` (native auto-merge). Rejected: `stable` has zero required status checks, so native auto-merge would merge as soon as the approval lands, without waiting for CI.

## R3. Approval identity

**Decision**: A new GitHub App (`opsmill-dependabot-autopilot`) with `contents: write`, `pull-requests: write`, and `actions: read`, `checks: read`, `statuses: read` (artifact download and CI evaluation) on `opsmill/infrahub` only; the act workflow requests exactly these when minting its token, credentials in Actions secrets `DEPENDABOT_AUTOPILOT_APP_ID` / `DEPENDABOT_AUTOPILOT_APP_PRIVATE_KEY`. It is not added to any branch-rule bypass list.

**Rationale**: Least privilege; `opsmill-bot` already holds bypass rights on `stable`, so an approval from it would also be able to bypass the review rule entirely. Whether a `GITHUB_TOKEN` (`github-actions[bot]`) approval counts toward a required review is not documented authoritatively ([community discussion 181487](https://github.com/orgs/community/discussions/181487) says it does not); an App installation with write access is the reported working path. **Unconfirmed**: verified in quickstart scenario Q1 before enabling merges.

**Alternatives considered**: `opsmill-bot` (over-privileged), `GITHUB_TOKEN` with "Allow GitHub Actions to create and approve pull requests" (repo-wide setting affecting every workflow, uncertain to count).

## R4. Analysis skill in CI

**Decision**: Vendor `analyzing-dependency-bumps` into the repository root (`.agents/skills/analyzing-dependency-bumps/`) and record it in `skills-lock.json`, the same way `grilling-ideas` and `creating-prd` are vendored from `opsmill/opsmill-skills`. The workflow prompt adds a machine-readable output contract on top of the skill ([contracts/verdict.schema.json](contracts/verdict.schema.json)) instead of forking the skill.

**Rationale**: The skill exists today only in the `python_sdk` submodule (`python_sdk/.agents/skills/opsmill-dev-analyzing-dependency-bumps/`); CI checkouts of the root repo reach skills through `.claude/skills -> ../.agents/skills`. The skill's own output contract is a chat report, so the structured verdict is layered on in the workflow prompt.

## R5. "All checks green" without required checks

**Decision**: The act workflow evaluates the head commit from three sources and merges only when every entry is complete and passing:

1. Workflow runs for the head SHA (`GET /repos/{o}/{r}/actions/runs?head_sha=`), excluding the autopilot's own workflows by name.
2. Check runs from non-Actions apps (`GET /commits/{sha}/check-runs`, `app.slug != github-actions`), e.g. Chromatic.
3. Legacy commit statuses (`GET /commits/{sha}/status`).

`success`, `skipped` and `neutral` pass; `failure`, `cancelled`, `timed_out`, `action_required`, `stale` fail; anything not `completed` is pending.

**Rationale**: Check runs and commit statuses are separate APIs ([check runs](https://docs.github.com/en/rest/checks/runs), [statuses](https://docs.github.com/en/rest/commits/statuses)). Listing workflow runs lets the evaluator exclude its own in-progress run by workflow name, which the check-runs API does not expose directly.

**Re-evaluation triggers**: `workflow_run: completed` of `CI` and of the analysis workflow (whichever finishes last performs the merge), plus a 30-minute `schedule` sweep over open Dependabot PRs to cover checks from external apps finishing last and dropped events.

**Alternatives considered**: Making CI checks required on `stable`. Rejected in the spec (Out of Scope): it changes merge rules for every PR.

## R6. Withdrawing a stale approval promptly

**Decision**: The act workflow also listens to `workflow_run: requested` for the analysis workflow. The analysis starts on every `synchronize` of a Dependabot PR, so `requested` fires within seconds of a new push; the act job then dismisses every approval by the App whose `commit_id` differs from the PR head.

**Rationale**: `stable` has `dismiss_stale_reviews: false`, so a stale App approval would otherwise let a human merge unanalysed code. `workflow_run` runs in the trusted context, so the App key never has to be copied into Dependabot secrets. The merge path is independently protected by the verdict-SHA check and `--match-head-commit`.

**Alternatives considered**: `pull_request_target: synchronize`. Rejected: whether Dependabot-triggered `pull_request_target` runs receive Actions secrets could not be confirmed on a current doc page.

## R7. New-package detection is deterministic

**Decision**: The act workflow diffs the package sets of every lockfile changed by the PR (base vs head, fetched through the contents API, never by executing PR code): `uv.lock` (`[[package]] name`), `pnpm-lock.yaml` (`packages:` keys, versions stripped), `package-lock.json` (`packages` keys). Any name present at head and absent at base caps the verdict at `review required`, whatever the agent said.

**Rationale**: FR-006 enforces a constitution rule; it must not depend on the agent's judgment. Lockfiles in scope: `uv.lock`, `python_testcontainers/uv.lock`, `frontend/pnpm-lock.yaml`, `docs/package-lock.json`, `frontend/packages/plugins/template/package-lock.json` (submodule lockfiles are not touched by root Dependabot PRs). `github-actions` bumps have no lockfile and never add an action.

## R8. Jira deduplication key

**Decision**: Each opportunity carries a normalized `key` (lowercase package name + `:` + the upstream API, option or feature identifier, e.g. `fastapi:lifespan-state`). The act workflow derives the label `dbap-<first 12 hex of sha256(key)>` and searches `labels = "dbap-…" AND statusCategory != Done` through `/rest/api/3/search/jql` (the old `/rest/api/3/search` returns 410). Found → comment; not found → `POST /rest/api/3/issue` with labels `tech-debt`, `dependabot-autopilot`, `dbap-…` and the rubric priority.

**Rationale**: Exact label match is deterministic; free-text JQL would miss or over-match. The prompt constrains `key` to an identifier taken from the changelog, which keeps it stable across bumps of the same range. Stability is measured by SC-004.

**Alternatives considered**: gh-aw's built-in `jira-create-issue` safe output. Rejected: it runs in the agent's untrusted context (would need Jira credentials in Dependabot secrets) and has no search-before-create.

## R9. Priority rubric is deterministic

**Decision**: The agent classifies each opportunity into `security`, `deprecation-deadline`, `performance`, `simplification`, or `other`; the act workflow maps `security`/`deprecation-deadline` → High, `performance`/`simplification` with at least one code reference → Medium, everything else → Low.

**Rationale**: FR-012 is a rule, so the mapping lives in tested code; only the classification is judgment.

## R10. Owners and notifications

**Decision**: Owners are the `CODEOWNERS` teams matching the PR's changed files (last matching rule wins, GitHub semantics). With no match (every `.github/` change, since `CODEOWNERS` has no rule for it), the fallback is the repository variable `DEPENDABOT_AUTOPILOT_FALLBACK_REVIEWER`. Notification = a review request to those teams plus a mention in the verdict comment.

## R11. Slack digest

**Decision**: A scheduled workflow (Monday 09:30 UTC, after Dependabot's 09:00 run) queries Jira for `labels = dependabot-autopilot AND priority in (High, Medium) AND updated >= -7d` and posts one message through an incoming webhook bound to #release-radar (`SLACK_RELEASE_RADAR_WEBHOOK_URL`). No result → no post.

**Rationale**: One fixed channel, so an incoming webhook is the simplest credential ([Slack incoming webhooks](https://api.slack.com/messaging/webhooks)); `chat.postMessage` would need a bot token and scope management for no gain.

## R12. Kill switches and human precedence

**Decision**: Repository variable `DEPENDABOT_AUTOPILOT_MERGE` (`on`/`off`, default `off`) gates approve+merge only; the analysis and all other actions keep running (FR-016). The label `autopilot/hold`, a human `CHANGES_REQUESTED` review, or a closed/merged PR make the act job stop for that PR (FR-010).

**Rollout**: ship with `DEPENDABOT_AUTOPILOT_MERGE=off` (shadow mode), compare verdicts against human decisions for two weeks, then switch on.

## R13. Runtime for the deterministic code

**Decision**: A small stdlib-plus-PyYAML Python package at `.github/scripts/dependabot_autopilot/`, run with `uv run --no-project --with "pyyaml>=6,<7" python -m dependabot_autopilot …` (the same range as the root `pyproject.toml`). Pure decision logic is separated from I/O (GitHub, Jira, Slack) behind protocols so the logic is unit-tested with in-memory fakes. GitHub calls go through the `gh` CLI already present on runners.

**Rationale**: CI already runs `ruff check . --exclude python_sdk` and `ty check .` over the whole repository, so the package is linted and type-checked without new configuration. Avoiding the repository's full dependency set keeps the act job to seconds.

## R14. Open risk: CI duration versus SC-002

Of the 48 Dependabot PRs opened in the 90 days to 2026-09-23, 26 changed only `.github/` (GitHub Actions), 14 changed npm lockfiles, and 8 changed a `uv.lock`. GitHub Actions bumps skip most CI jobs through `.github/file-filters.yml` and should merge within minutes. `uv.lock` bumps trigger the full backend suite; if that suite routinely exceeds an hour, SC-002 (median under 1 hour) still holds as long as the GitHub Actions and npm bumps stay the majority. Measured during the shadow period.

## R15. Release-age cooldown against compromised releases

**Decision**: Add Dependabot's `cooldown` option (`default-days: 3`) to the `github-actions` entry of `.github/dependabot.yml`, so version updates are proposed only for releases at least three days old. Security updates are not subject to cooldown.

**Rationale**: A compromised upstream release can carry a benign changelog (the analysis finds no usage change) and pass CI; the autopilot would merge it faster than a human does today. Most malicious releases are detected and yanked within days. The delay applies before the PR opens, so SC-002 (open-to-merge latency) is unaffected. **Verified (2026-09-23)**: the [Dependabot options reference](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference#cooldown-) lists GitHub Actions among the package managers supporting `cooldown` `default-days` (the `semver-*-days` options are not supported for it). The same page states that Dependabot already applies a 3-day default cooldown to version updates when `cooldown` is not configured; the explicit setting pins that value so a change of the platform default does not shorten it. No release-age cap is needed in the act package.

**Alternatives considered**: A minimum PR age before merging. Rejected: it delays security updates too and directly defeats SC-002.
