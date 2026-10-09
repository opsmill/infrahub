# Infrahub PR cleanup, reminders, and dashboard: requirements and implementation handoff

**Status:** Policy agreed through a detailed interview. No implementation, branch, PR, deployment, labels, comments, or dashboard issue has been created in this session. This document is the deliverable requested for a new agent.

**Goal:** Help valid Infrahub PRs move toward merge and automatically close abandoned work, using `actions/stale` for cleanup and a small companion script for exemptions, reminders, and a daily GitHub issue dashboard.

**Scope:** Start with `opsmill/infrahub` only. Deliver cleanup, targeted reminders, and dashboard together. The user explicitly rejected splitting reminders/dashboard into a later rollout.

**Added September 28, 2026:** Restore the broken elements of the existing stale-PR pipeline as an explicit deliverable, not merely a prerequisite mentioned in passing. Diagnose and repair its scan coverage, operation-budget handling, and continuation-state/cache failures. Scope this restoration to the stale-PR workflow and its dependencies; this is not an audit or repair of unrelated build/release pipelines.

**Architecture direction:** Extend the existing repository-local scheduled workflow. Retain the pinned upstream `actions/stale`; add minimal companion logic. Do not build a general lifecycle platform, replace stale with a custom closer, introduce Mergify, or deploy changes to the shared bot service without a new decision.

**Read this first:** The interaction between automated reminder comments and stale timers is unresolved. Investigate it before writing the final executable implementation plan. The task sequence below is an execution roadmap with acceptance criteria, not a claim that all mechanisms have already been proven feasible.

## 1. Settled requirements — do not repeat the interview

| Area | Agreed behavior |
|---|---|
| Normal inactivity period | 60 calendar days. Same threshold for drafts, PRs awaiting authors, and PRs awaiting reviewers. |
| Closure window | After 60 days of inactivity, start a fresh 14-calendar-day warning period. Close if still eligible and inactive when it expires. |
| Closure reminders | Three notices: 14 days remaining, 7 days remaining, and 1 day remaining. These replace ordinary weekly reminders during this window. |
| Ordinary reminders | First after 7 days of inactivity; at most once every 7 days per PR while attention is still needed. Includes drafts and exempt human-authored PRs. |
| Approval exemption | Any current, non-dismissed approval prevents automatic closure, even when all required approvals are not yet satisfied. This does not imply readiness to merge. |
| Pending review requests | Do not exempt indefinitely. An unapproved PR awaiting review follows the same 60+14-day cleanup policy. |
| Manual exemption | `keep-open` prevents closure but preserves reminders and dashboard visibility. Maintainers should leave a short explanation. No date parsing or automatic expiry is required. |
| Bot-authored PRs | Exclude from reminders and closure. List separately on dashboard. Includes dependency and branch-sync PRs; check how actual automation accounts are represented before classifying them. |
| Human activity | Accept upstream stale's standard activity semantics rather than custom meaningful-progress detection. A human comment can restart the cycle. |
| New stale cycle | Following human activity, a later stale cycle gets a full fresh 14-day warning window and all three notices again. |
| Reopening | A human reopening a closed PR clears previous warning state and restarts the normal 60-day inactivity period. |
| Initial backlog | Every eligible old PR receives a new full warning window. Existing `stale` labels/timestamps must never serve as notice under the new closure policy. |
| Merge behavior | Never automatically merge human-authored PRs. Ask authors to merge ready PRs; identify remaining blockers when approved but not ready. |
| Notifications | Actionable notices are PR comments. No Slack integration. |
| Dashboard | One ongoing GitHub issue, edited in place and refreshed daily. |
| Scope of custom code | A small companion script is accepted. Avoid custom per-person clocks, business-day calculations, automatic escalation, or a general service/database unless a concrete requirement makes it unavoidable and the user chooses that tradeoff. |

## 2. Reminder routing and language

Use the current state at posting time. Do not infer that a commit resolved review feedback. Do not equate one approval with all merge requirements being fulfilled.

The settled routing principles are:

- Draft: ask author to mark ready and request review, explain blockers, or close abandoned work.
- Non-draft without approvals, pending reviewers, or requested changes: ask author to request a person/team review. Dashboard category: `Needs reviewer`.
- Outstanding changes requested plus pending reviewers: author gets the reminder first. Ask them to address feedback and request another review.
- Waiting for review: remind the requested person/team.
- Approved and ready to merge: remind author to merge.
- Approved with remaining blockers: ask author to address blockers and move toward merge; never threaten automatic closure.

Classify conflicts/CI failures as blockers. The exact precedence between all overlapping technical states should be documented by the implementing agent, using the principles above, without introducing a complex workflow engine. Ordinary comments/unresolved threads are not automatically equivalent to a formal changes-requested review.

The user wants urgency and a concrete consequence (their wording: a little “FOMO”). Use accurate deadlines and direct instructions, not invented urgency:

> @author This PR has been inactive for 7 days and has no requested reviewer. Please request a review so it can move toward merge. Unapproved PRs without a keep-open exemption are marked stale after 60 days of inactivity, then closed after a further 14 days without activity.
>
> @author This PR is scheduled to close on **[actual date]** unless activity resumes. Please request a review, update the PR, or explain what is blocking it.

For a pending-review closure notice, include the author and requested reviewers/team. For exempt PRs, say what needs doing but never claim an automatic closure deadline. A fresh approval or `keep-open` exemption must cancel/neutralize a pending closure warning.

The three closure notices must retain the same deadline. Automation-generated reminders must not extend it. Include a stable machine-readable marker to recognize the bot's own lifecycle comments and prevent duplicate notifications; choose the exact format during implementation.

## 3. Dashboard requirements

Create or reuse exactly one issue in `opsmill/infrahub`; edit its body, not a new issue or comment on every run. A suitable proposed title is `PR lifecycle dashboard`. No issue number has been chosen or created.

Show:

- Summary counts and last successful refresh time.
- Ready to merge.
- Waiting for review.
- Waiting for author / needs reviewer.
- Blocked (conflicts, CI, or an explicit blocker).
- Drafts.
- Closing soon, with actual closure deadlines.
- Bot-authored PRs, separately and explicitly excluded.

Each PR should have one primary category, with exemptions and other blockers as annotations. Include PR link/title, author, next actor, next action, applicable inactivity/waiting measure, and next notice or closure deadline. Clearly label what the time metric measures; do not invent precise per-reviewer waiting times.

Use plain names for ordinary dashboard rows; actionable mentions belong in PR comments. Dashboard edits must not change PR activity or produce periodic comment spam. Keep the dashboard issue itself outside stale issue management. No historical Swarmia-style analytics are required.

## 4. Existing repository state and evidence

Repository: [source](https://github.com/opsmill/infrahub)

Existing workflow:
[source](https://github.com/opsmill/infrahub/blob/stable/.github/workflows/manage-stale-prs.yml)

Observed on September 26, 2026; re-read before editing:

- Default branch `stable`.
- Workflow name `Manage Stale Pull Requests`.
- Daily cron `0 2 * * *`, plus `workflow_dispatch`.
- Repository guard restricts execution to `opsmill/infrahub`.
- Uses `actions/stale@4391f3da665fdf50b6810c1a66712fb9ba21aa93` (v11.0.0).
- Permissions currently `pull-requests: write` and `issues: write`.
- Issues are excluded (`days-before-issue-stale: -1`, `days-before-issue-close: -1`).
- PR stale threshold 14 days; closure disabled (`days-before-pr-close: -1`).
- Stale label `stale`; activity removes that label.
- No explicit approval, review, or draft exemptions in the workflow.

Run history showed 248 runs; the latest five scheduled runs succeeded. The September 26 run processed 69 PRs and marked one newly stale:
[source](https://github.com/opsmill/infrahub/actions/runs/36211129362)

Despite its successful conclusion, that run logged:

- Operation budget exhausted at default `operations-per-run: 30`.
- Cache deletion failed with `403 Resource not accessible by integration`.
- Continuation-state cache save failed afterward.

Address scan completeness and continuation-state permissions as part of this work. Upstream recommends `actions: write` for its cache handling; confirm against the pinned version. Choose an operation budget from the actual backlog and API behavior; do not claim a success conclusion proves every PR was processed.

These are historical observations, not proof that the same failures remain present on the implementation date. Recheck recent runs and record which defects persist, which have already been fixed, and what evidence establishes each result. Budget exhaustion alone is not necessarily a defect when continuation works; the requirement is timely coverage of every PR without repeatedly starving older items.

Existing labels include `stale`, `state/blocked`, `state/draft`, `state/need-decision`, `state/need-more-info`, `state/needs-human-fix`, `state/needs-human-test`, `group/ci`, and `type/housekeeping`. `keep-open` was not in the inspected label list. Avoid reusing unrelated state labels without understanding existing automation. A new automation-owned exemption label and a distinct closure-warning label are possible implementation choices, not yet chosen.

## 5. Repository guidance and placement

Read current repository instructions, including:

- [source](https://github.com/opsmill/infrahub/blob/stable/AGENTS.md)
- [source](https://github.com/opsmill/infrahub/blob/stable/dev/guidelines/git-workflow.md)
- [source](https://github.com/opsmill/infrahub/blob/stable/.agents/commands/pre-ci.md)
- Any nested instructions and relevant `dev/knowledge/` guidance discovered in the actual checkout.

Observed git guidance says pure CI/config/tooling changes target `stable`; runtime changes target the appropriate branch. Follow actual current guidance when cutting the branch. The user has authorized the workflow direction; do not re-ask the same policy questions merely because repository instructions say to ask before CI changes.

Suggested file responsibilities (confirm repository conventions before choosing final paths):

1. Existing `.github/workflows/manage-stale-prs.yml`: schedule, permissions, concurrency, companion execution, pinned stale action, configuration, reporting.
2. One small companion script in the repository's established automation-script location: paginated collection, exemptions, reminder selection, dashboard rendering, dry-run support.
3. Focused tests alongside the existing appropriate test structure: classification, timestamps, idempotency, lifecycle transitions, and generated messages.
4. A short operator note explaining labels, thresholds, dashboard, and rollout/recovery.

Do not select a language, dependency, persistence layer, or exact new file paths solely from this handoff. Inspect existing tooling and minimize new dependencies.

Future home for a reusable workflow is `opsmill/opsmill-cicd-workflows`, not the shared bot service. That repository was verified private and pre-v1; public Infrahub cannot consume its private reusable workflow today. Do not modify its visibility, migrate it, or expand scope to other repos.

The existing `opsmill/infrahub-github-bot` service handles webhook-based branch syncing and other automations. Leave it unchanged for this rollout. It is context, not an implementation dependency.

## 6. First task: prove the timer interaction

This is the unresolved dependency, not a policy question the user failed to answer.

Inspect the exact pinned `actions/stale` source, especially how it uses `updated_at`, stale-label events, comments, cached processing state, and the `ignore-updates` / `remove-stale-when-updated` options. Do not rely on option names alone.

Known nuance: current upstream code filters bot comments in one post-warning comment check, but separately checks update timestamps. This does **not** prove automation comments cannot reset inactivity or remove stale state. Weekly reminders could prevent the 60-day threshold from being reached, and 7-/1-day notices could invalidate a closure window.

- [ ] Reproduce activity handling using fixtures or an isolated test repository, never production PRs.
- [ ] Compare human comments, this workflow's bot comments, new commits, labels, approvals, reopening, and no activity.
- [ ] Verify both pre-stale and post-stale timing.
- [ ] Verify initial labeling cannot allow same-run closure of an already-old PR.
- [ ] Check whether the exact deadline can be derived reliably for reminders and dashboard.
- [ ] Produce a short feasibility verdict and evidence before implementing the full integration.

Do not silently solve this by ignoring **all** updates, basing closure on creation date, postponing cleanup forever, or moving closure into custom code. Each changes an agreed requirement.

If stock stale cannot satisfy the combined reminders and timer behavior, report the concrete incompatibility and the smallest supported choices. Ask the user only about that new tradeoff. Do not claim the existing plan is implementable merely because each feature independently exists.

Also assess the interval between approval classification and stale execution: approval can arrive during that interval. Refresh exemptions immediately before action execution and fail closed if classification fails. Document any remaining upstream race limitation honestly; do not promise atomic approval protection the APIs/action do not provide.

## 7. Implementation roadmap after feasibility is established

### Task R — Restore the existing stale-PR pipeline

This repair task can start before the reminder-timer feasibility investigation finishes. Keep restoration changes distinguishable from new lifecycle behavior in the diff and validation report, while delivering the agreed combined rollout.

- [ ] Inspect current workflow registration, enabled status, default-branch configuration, and recent scheduled/manual run history. Confirm the actual trigger-to-job path rather than assuming the presence of a cron means execution works.
- [ ] Reproduce or establish the cause of the observed cache-deletion 403 and subsequent continuation-state save failure. Inspect effective token permissions, the pinned action's cache implementation, and overlapping runs. Grant only the permissions actually required; do not introduce a broad personal token as a workaround.
- [ ] Repair continuation-state save/restore and serialize mutating runs. Do not rely on clearing caches as a permanent fix. If a one-time stale-cache cleanup is necessary, document its exact target and why it is safe.
- [ ] Measure current backlog size and API operations. Set an explicit operation budget and cadence that cover the backlog within the daily policy-evaluation interval, or document evidence that reliable continuation achieves that interval. Increasing the budget must not conceal broken continuation or ignore rate limits.
- [ ] In isolation, force a low-budget run to stop partway, then run again and demonstrate that processing advances to previously unprocessed items and eventually covers all items. Also exercise lost/expired cache behavior so a cache miss cannot silently strand old PRs.
- [ ] Verify that labels/comments still work, issues remain excluded, and the repository guard remains effective. During restoration-only tests, keep production closure disabled and do not post diagnostic notices to real PRs.
- [ ] Add a concise run summary or equivalent observability showing processed counts, deferred work where measurable, and actionable failures. Do not report an incomplete scan or a failed state save as proven full coverage just because the upstream action exits successfully.
- [ ] Record before/after evidence: affected configuration, failure cause, isolated test results, and run links when available. Separate locally proven recovery from production recovery that still needs verification after authorized deployment.
- [ ] Document operator recovery steps for missed schedules, cache failures, and rate-limit exhaustion. After authorized rollout, confirm the next scheduled run and any required continuation complete; until then, mark production recovery as unverified.

### Task A — Repository preparation and executable design

- [ ] Read current guidance, inspect status/remotes and automation conventions, and create an isolated working branch from the correct base.
- [ ] Re-read workflow, action pin, labels, and current run logs.
- [ ] Turn the proven timer integration into an executable design with exact files and test commands.
- [ ] Keep stock `actions/stale` as cleanup owner. Avoid duplication of warning/closure ownership.

### Task B — Classification and exemptions

- [ ] Collect all open PRs and needed review/request/check data with pagination.
- [ ] Derive current reviews correctly: a superseded approval is not necessarily a current approval; ignore dismissed approvals.
- [ ] Separate exemption status from reminder category/readiness to merge.
- [ ] Manage automation-owned exemption labels idempotently; never remove manually owned `keep-open`.
- [ ] Recognize bot-authored PRs, including existing sync automation identities.
- [ ] On incomplete classification/API errors, stop the closure-capable stage and report failure.
- [ ] Test against the cases in section 8.

### Task C — Reminders and daily dashboard

- [ ] Implement the agreed routing and weekly rate limit.
- [ ] Implement closure notices at 14/7/1 days remaining through the proven integration, with no duplicate initial warning from two components.
- [ ] Use stable per-PR/per-cycle markers or another minimal proven way to deduplicate across reruns/restarts.
- [ ] Recheck current PR state before posting notices; suppress expired/wrong-state messages.
- [ ] Create/reuse one dashboard issue and update only when content changes materially.
- [ ] Use time injection in tests so thresholds and daily-run delays are deterministic.
- [ ] After a missed run, send at most the currently relevant notice rather than a burst of all missed reminders. This is a proposed operational default; document it.

### Task D — Workflow and migration

- [ ] Apply 60-day stale and 14-day close settings; preserve issue exclusions and do not delete branches.
- [ ] Preserve the repository guard and SHA pinning.
- [ ] Integrate the operation-budget, cache, and concurrency repairs from Task R; ensure the new companion steps do not invalidate the recovery evidence.
- [ ] Implement a fresh-warning migration that cannot reuse old `stale` timestamps for closure. Consider a distinct warning label, but prove migration behavior rather than assuming it.
- [ ] Preserve or accurately reset human-activity/reopening behavior, including stale comments and markers from prior cycles.
- [ ] Provide an observe-only mode that genuinely suppresses every write from both the companion and stale; do not assume a companion flag controls the action too.

### Task E — Validation and rollout

- [ ] Run relevant linters, workflow validation, focused tests, and applicable current `/pre-ci` checks. Record exact commands and results.
- [ ] Exercise the integration in isolation, including bot notices and freshly arriving approvals.
- [ ] Run a production read-only inventory showing exclusions, reminders, would-warn PRs, and eventual closure candidates. Existing backlog must not be closed on initial rollout.
- [ ] Prepare a reviewable PR with policy, migration, tests, limitations, and operational instructions.
- [ ] Keep implementation delivery distinct from merging/enabling production changes. Do not bulk-close PRs, publish test notices, or trigger production mutations as a test.

## 8. Acceptance matrix

| Scenario | Expected result |
|---|---|
| Unapproved draft idle 7 days | Author gets draft-specific reminder; next ordinary notice no sooner than 7 days later. |
| Open PR without reviewers | Author asked to request review; dashboard identifies next action. |
| Changes requested and another review pending | Author reminded first. |
| Pending review only | Requested reviewers/team reminded; PR remains eligible for 60+14 cleanup. |
| One current approval, other approval still required | No automatic closure; no claim it is ready to merge. |
| Approved but conflicting or failing checks | No closure; message asks for blockers to be fixed. |
| Fully approved and otherwise ready | Ask author to merge; never auto-merge. |
| Approval dismissed or superseded | Reclassify from current state; no stale cached exemption decision. |
| `keep-open` | No closure; normal reminders and dashboard remain. |
| Bot-authored | No reminders/closure; separate dashboard listing. |
| 60-day inactive eligible PR | New 14-day warning window with a concrete deadline. |
| Window reaches 7/1 days remaining | One appropriate notice, same deadline, no ordinary weekly notice. |
| Bot notice before or during warning | Does not postpone the required stale/closure schedule under the proven integration. |
| Human activity during warning | Cancel old cycle; if inactivity recurs, fresh 60-day period and 14/7/1 notices. |
| Human reopens PR | Old warning state cleared; fresh 60-day period. |
| Legacy stale label older than 14 days | No immediate closure; new warning required. |
| Approval or keep-open arrives during warning | Cancel closure eligibility; subsequent notices cannot threaten closure. |
| Rerun/restart/overlapping schedule | No duplicate comments/issues and no restarted deadlines. |
| Pagination or review-data fetch fails | No closure-capable run based on incomplete data. |
| Repeated successful scans | Entire backlog covered, not just the first operation-budget slice. |
| Forced operation-budget exhaustion | Next run resumes unprocessed work; successive runs complete coverage without starving older PRs. |
| Continuation cache save/delete/restore | Required operations succeed under intended permissions; failures are visible and not misreported as full coverage. |
| Expired or missing continuation cache | Processing restarts safely and still reaches all PRs within the documented evaluation interval. |
| Scheduled pipeline after authorized rollout | A real scheduled run executes the intended jobs; production recovery is supported by run evidence, not only local tests. |

## 9. References and suggested skills

Authoritative references:

- Pinned action source: [source](https://github.com/actions/stale/tree/4391f3da665fdf50b6810c1a66712fb9ba21aa93)
- Pinned inputs: [source](https://github.com/actions/stale/blob/4391f3da665fdf50b6810c1a66712fb9ba21aa93/action.yml)
- Pinned processor: [source](https://github.com/actions/stale/blob/4391f3da665fdf50b6810c1a66712fb9ba21aa93/src/classes/issues-processor.ts)
- Shared platform context: [source](https://github.com/opsmill/opsmill-cicd-workflows/blob/main/README.md)
- GitHub reuse behavior: [source](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations)

Suggested skills, according to what is available in the new session:

- `superpowers:systematic-debugging` for the timer/cache behavior investigation.
- `superpowers:writing-plans` after feasibility, to produce exact executable tasks from these requirements.
- `superpowers:executing-plans` for implementation; delegation is optional only if otherwise authorized.
- `superpowers:test-driven-development` for companion logic with meaningful behavioral tests.
- `opsmill-dev:opsmill-dev-verifying-changes` for evidence-backed validation.
- `opsmill-dev:opsmill-dev-commit` and `opsmill-dev:opsmill-dev-pr` when delivering commits/PRs, following current repo/session authorization rules.

The grill-me/grilling interview is already complete for the policies recorded here. Do not restart it. No new Codex task has been created; the user requested a document to pass to a new agent.

## Suggested opening prompt for the next agent

Read this handoff and implement the agreed Infrahub-only PR cleanup, reminders, and dashboard, including restoration of the existing stale-PR pipeline. Recheck and repair its observed operation-budget/continuation-cache failures, and prove how the pinned actions/stale handles our own reminder comments before and after a stale warning. Keep actions/stale as the cleanup mechanism and companion logic small. Do not repeat the settled policy interview. If the timer requirements conflict with stock stale, explain the reproduced incompatibility and ask for the smallest necessary policy/implementation decision; continue independent pipeline repairs. Otherwise prepare a tested PR targeting the branch required by current repository guidance; do not merge or activate production cleanup as part of testing. Report restoration evidence separately from new-feature evidence and do not claim production recovery before it is verified.
