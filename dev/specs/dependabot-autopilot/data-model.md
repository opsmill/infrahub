# Data Model: Dependency-bump autopilot

No Infrahub schema, database or API entity is added. The entities below live in CI: a JSON artifact passed between the two workflows, frozen dataclasses inside the act package, and labels/fields on GitHub and Jira objects.

## VerdictReport (artifact, produced by the analysis workflow)

Serialized per [contracts/verdict.schema.json](contracts/verdict.schema.json).

| Field | Type | Rule |
|---|---|---|
| `schema_version` | int | Must equal `1`; any other value is treated as a malformed report |
| `pr_number` | int | Must equal the PR the act job is evaluating |
| `head_sha` | str (40 hex) | Must equal the `workflow_run.head_sha` and the PR's current head; otherwise the report is stale |
| `verdict` | enum | `safe-to-merge` \| `needs-code-changes` \| `review-required`, the agent's overall verdict |
| `packages` | list[PackageFinding] | At least one entry |
| `report_markdown` | str | The human-readable report posted on the PR; at most 60,000 characters |

### PackageFinding

| Field | Type | Rule |
|---|---|---|
| `name` | str | Package or action name as in the manifest |
| `ecosystem` | enum | `github-actions` \| `uv` \| `npm` |
| `from_version`, `to_version` | str | |
| `verdict` | enum | Same values as the overall verdict |
| `impacts` | list[Impact] | Required non-empty when `verdict` is `needs-code-changes` |
| `opportunities` | list[Opportunity] | May be empty |

**Impact**: `summary` (str), `path` (str, repo-relative), `line` (int ≥ 1).

**Opportunity**: `key` (str, `^[a-z0-9._-]+:[a-z0-9._/-]+$`), `title` (str ≤ 120), `category` (`security` \| `deprecation-deadline` \| `performance` \| `simplification` \| `other`), `summary` (str), `code_refs` (list of `path:line` strings).

## Decision (computed by the act package, never trusted from the agent)

Frozen dataclass computed from the report plus repository state.

| Field | Derivation |
|---|---|
| `effective_verdict` | Strictest of: every `PackageFinding.verdict`, the overall `verdict`, `review-required` if the lockfile diff adds a package, `review-required` if the report is malformed or stale, `review-required` if the report is missing once the analysis run completed or 60 minutes after the head commit's commit date ("analysis did not run", "analysis did not complete"), `review-required` if the analysis run that produced the report completed without success ("analysis run did not succeed") or cannot be found, `review-required` if any commit is not authored by `dependabot[bot]` |
| `reasons` | Ordered list of human-readable reasons for any downgrade from the agent's verdict |
| `ci_state` | `green` \| `pending` \| `red` from the check evaluation (research R5) |
| `action` | See state transitions below |

Strictness order: `needs-code-changes` > `review-required` > `safe-to-merge`.

## State transitions per PR head commit

```text
                 ┌──────────────┐  new push (workflow_run requested)
                 │  analysing   │◄──────────────────────────────────┐
                 └──────┬───────┘   dismiss App approvals ≠ head      │
       report received  │                                           │
     ┌──────────────────┼────────────────────────┐                  │
     ▼                  ▼                        ▼                  │
needs-code-changes  review-required         safe-to-merge           │
 REQUEST_CHANGES     label + reviewers        ci pending → wait     │
 label + reviewers                            ci red → review-required
     │                  │                     ci green + merge=on + no hold
     │                  │                        → APPROVE → squash merge
     └──────────────────┴──────────── any state ─┴──────────────────┘
```

Terminal: PR merged or closed. Human precedence: `autopilot/hold` label or a human `CHANGES_REQUESTED` review stops all approve/merge actions for that PR until removed.

## GitHub labels (added to `.github/labels.yml`)

| Label | Meaning |
|---|---|
| `autopilot/safe` | Effective verdict `safe-to-merge` for the current head |
| `autopilot/needs-code-changes` | Blocked; see the blocking review |
| `autopilot/review-required` | Escalated to owners |
| `autopilot/hold` | Human hold; the autopilot does not approve or merge |

Exactly one of the first three is present at a time; the act job replaces the previous one.

## Tech-debt item (Jira issue)

| Field | Value |
|---|---|
| Project | Repository variable `DEPENDABOT_AUTOPILOT_JIRA_PROJECT` |
| Issue type | Repository variable `DEPENDABOT_AUTOPILOT_JIRA_ISSUE_TYPE` (default `Task`) |
| Summary | `[<package>] <opportunity title>` |
| Labels | `tech-debt`, `dependabot-autopilot`, `dbap-<12 hex of sha256(key)>` |
| Priority | Rubric (research R9) |
| Description | Opportunity summary, code refs, link to the PR |
| Assignee | None |

Dedup identity: the `dbap-…` label among issues whose status category is not Done. An item one of whose comments already links the PR receives no further comment for that PR.

## Configuration

| Name | Kind | Store | Used by |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | secret | **Dependabot secrets** | analysis workflow |
| `DEPENDABOT_AUTOPILOT_APP_ID`, `DEPENDABOT_AUTOPILOT_APP_PRIVATE_KEY` | secret | Actions secrets | act workflow |
| `JIRA_BASE_URL`, `JIRA_USER_EMAIL`, `JIRA_API_TOKEN` | secret | Actions secrets | act workflow, digest workflow |
| `SLACK_RELEASE_RADAR_WEBHOOK_URL` | secret | Actions secrets | digest workflow |
| `DEPENDABOT_AUTOPILOT_MERGE` | variable | repository | act workflow (`on`/`off`, default `off`) |
| `DEPENDABOT_AUTOPILOT_FALLBACK_REVIEWER` | variable | repository | act workflow (team slug) |
| `DEPENDABOT_AUTOPILOT_JIRA_PROJECT`, `DEPENDABOT_AUTOPILOT_JIRA_ISSUE_TYPE` | variable | repository | act workflow |
