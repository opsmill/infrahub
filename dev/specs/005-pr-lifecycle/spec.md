# Feature specification: PR cleanup, reminders, and dashboard

**Feature branch**: `codex/pr-lifecycle-ifc-3240`

**Created**: 2026-09-28

**Status**: Specified; companion timing approved for planning

**Input**: [IFC-3240](https://opsmill.atlassian.net/browse/IFC-3240) and the
[user's detailed handoff](source-requirements.md). The settled policy is authoritative.

## User scenarios and testing

### User story 1 — Reliable daily processing (Priority: P1)

Maintainers need every open PR evaluated daily, even after an interrupted scan or lost cache.
This is required for every reminder and deadline to be credible.

**Independent test**: Run isolated scans with a deliberately small operation budget. Verify
successive scans advance, eventually cover every PR, and restart safely after cache loss.

**Acceptance scenarios**:

1. Given a partial scan, when continuation succeeds, then the next scan processes deferred work.
2. Given a cache failure, when a run ends, then its failure is visible and coverage is not claimed.
3. Given overlapping triggers, when they execute, then mutating runs are serialized.
4. Given local repair tests, when reporting recovery, then production recovery remains unverified
   until an authorized scheduled run demonstrates successful execution and coverage.

### User story 2 — Predictable cleanup (Priority: P1)

Maintainers can close abandoned work while authors receive a full, accurate warning period.

**Independent test**: Inject time and PR activity into an isolated lifecycle test. Verify the
60-day threshold, fresh 14-day window, all notices, exemptions, cancellation, and reopening; missed windows follow the suppression rule.

**Acceptance scenarios**:

1. Given an eligible PR inactive for 60 calendar days, when evaluated, then it receives a new
   warning with an actual closure deadline 14 calendar days later.
2. Given an active warning, when 7 and 1 days remain, then the appropriate notice uses that same
   deadline; automated notices never extend it.
3. Given human activity or reopening, when evaluated, then the prior warning is cleared and
   subsequent inactivity must satisfy a fresh 60-day period and full warning window.
4. Given any current approval or `keep-open`, when evaluated, then closure is prevented and
   pending closure threats are neutralized.
5. Given only a legacy `stale` label, when first evaluated, then it cannot authorize closure.

### User story 3 — Actionable reminders (Priority: P1)

Authors and reviewers receive comments identifying the next action without duplicate notices.

**Independent test**: Evaluate each routing state with overlapping approvals, changes requested,
pending reviewers, conflicts, failed checks, exemptions, and elapsed-time boundaries.

**Acceptance scenarios**:

1. Given an inactive human-authored PR, when 7 days pass, then its next actor gets an actionable
   reminder; another ordinary reminder cannot occur sooner than 7 days later.
2. Given changes requested and pending reviewers, when reminded, then the author is addressed
   first to resolve feedback and request another review.
3. Given one approval with remaining requirements, when reminded, then the comment identifies
   blockers and neither claims merge readiness nor threatens closure.
4. Given a warning window, when an ordinary reminder would be due, then only the currently
   relevant closure notice is sent. A missed run does not produce a burst of old notices.

### User story 4 — One daily dashboard (Priority: P1)

Maintainers can inspect current PR status and next actions in one ongoing issue.

**Independent test**: Render all categories from fixtures, rerun, and verify one issue is reused,
each PR has one primary category, and updates produce no periodic comments or mentions.

**Acceptance scenarios**:

1. Given open PRs, when refreshed, then counts, successful refresh time, next actions, exemptions,
   blockers, time measures, and applicable deadlines are visible.
2. Given a rerun, when the dashboard is updated, then the same issue body is used.
3. Given a bot-authored PR, when listed, then it appears separately as excluded from cleanup and
   reminders, with no actionable notification sent to it.

All four stories ship together. Their independent tests do not authorize separate rollouts.

### Edge cases

The complete [acceptance matrix](source-requirements.md#8-acceptance-matrix) is normative,
including dismissed or superseded approvals, partial approval, fresh approval during a warning,
human reopening, old labels, duplicate runs, failed pagination, and expired continuation state.

## Requirements

### Functional requirements

- **FR-001**: Scope execution to `opsmill/infrahub`; retain daily scheduling and manual dispatch.
- **FR-002**: Apply 60 calendar days of inactivity and a fresh 14-calendar-day closure window
  equally to drafts, author-waiting PRs, and reviewer-waiting PRs. Never delete branches.
- **FR-003**: Send closure notices at 14, 7, and 1 days remaining with one unchanged actual
  deadline. Bot lifecycle comments must not postpone staleness or closure.
- **FR-004**: Accept standard human activity, including comments, as resetting inactivity.
  Reopening clears old warning state and starts a new 60-day period.
- **FR-005**: Any current, non-dismissed approval prevents closure. Resolve superseded reviews
  from current reviewer state. Approval does not establish readiness to merge.
- **FR-006**: Manual `keep-open` prevents closure but preserves reminders and dashboard inclusion.
  Maintainers should explain its use. Do not parse dates, expire it, or remove it automatically.
- **FR-007**: Exclude bot-authored PRs from reminders and closure, including dependency and
  branch-sync automation. Confirm actual account representation before classification.
- **FR-008**: Begin ordinary reminders at 7 days of inactivity, at most once per 7 days per PR,
  including drafts and exempt human-authored PRs. Use closure notices instead during warnings.
- **FR-009**: Route draft reminders to authors; ask them to mark ready and request review, explain
  blockers, or close abandoned work. Without approval, pending reviewers, or formal changes
  requested, ask authors to request a person/team review and classify as Needs reviewer.
- **FR-010**: Outstanding changes requested take author-routing precedence over pending review.
  Otherwise remind requested people/teams when waiting for review. A commit alone does not prove
  feedback resolved; ordinary comments and unresolved threads are not formal changes requests.
- **FR-011**: Ask authors to merge approved, ready PRs; identify remaining blockers otherwise.
  Conflicts and failed checks are blockers. Never automatically merge human-authored PRs.
- **FR-012**: Use accurate consequences and direct instructions. Pending-review closure notices
  address both author and requested reviewers/team. Exempt PRs never receive closure threats.
- **FR-013**: Fetch all PR, review, request, and check data with pagination. Recheck current state
  before notices and exemptions immediately before closure-capable execution. Incomplete data
  prevents that stage; document remaining non-atomic approval races honestly.
- **FR-014**: Recognize lifecycle comments with stable machine-readable markers and deduplicate
  across reruns and cycles. Each new cycle receives all three notices again.
- **FR-015**: Create/reuse exactly one dashboard issue and edit its body daily. Include summary
  counts and successful refresh time. Avoid materially redundant updates and comment spam.
- **FR-016**: Give each PR one primary category: Ready to merge, Waiting for review, Waiting for
  author/Needs reviewer, Blocked, Drafts, Closing soon, or excluded Bot-authored PRs. Annotate
  secondary blockers and exemptions. Define overlap precedence during design.
- **FR-017**: Include PR link/title, plain author name, next actor/action, accurately named time
  measure, and next notice or closure deadline where applicable. Do not invent per-reviewer clocks.
  Actionable mentions belong in PR comments; dashboard edits must not change PR activity.
- **FR-018**: Keep all issues, including the dashboard, outside stale issue management. Existing
  backlog must receive a fresh warning; historical labels or timestamps cannot count as notice.
- **FR-019**: Restore cache save/restore and reliable continuation, serialize mutation runs, and
  select an explicit operation budget from backlog/API evidence. Cover all PRs within the daily
  evaluation interval, including after cache loss. Do not hide broken continuation with a budget.
- **FR-020**: Report processed counts, deferred work where measurable, and actionable failures.
  Separate before/after evidence and local tests from post-deployment production recovery.
- **FR-021**: Provide a true observe-only mode suppressing every write in every component. Test
  in isolation and run a production read-only inventory; never use production notices as tests.
- **FR-022**: Keep cleanup owned by pinned upstream `actions/stale` and companion logic minimal.
  If timing cannot meet policy, request a specific tradeoff before final executable planning.
- **FR-023**: Deliver focused behavioral tests, workflow checks, applicable pre-CI checks, operator
  recovery notes, and a reviewable PR. Do not merge or activate production cleanup during testing.
- **FR-025**: Deliver the PR and a read-only dry test without backlog closure or notification spam.
  The shipped workflow must not expose a live activation input; enable mutation only in a later
  reviewed change. Explain the implemented logic and dry-run results in the PR description and
  `dev/knowledge/pr-lifecycle.md`.
- **FR-024**: Exclude Slack, Mergify, historical analytics, business-day calculations, escalation,
  custom per-person clocks, other repositories, and shared-bot changes. Do not change visibility
  or migrate to the private reusable-workflow repository.

### Key entities

- **PR snapshot**: Author kind, draft state, reviews, requests, blockers, labels, and activity.
- **Warning cycle**: Fresh notice time, stable deadline, sent notices, and cancellation state.
- **Reminder**: Current recipient, next action, applicability, cycle, and deduplication identity.
- **Dashboard**: Stable issue identity, categorized rows, counts, and successful refresh time.
- **Scan**: Inventory, processed/deferred work, continuation state, budget, and failure evidence.

## Success criteria

- **SC-001**: Every scenario in the supplied acceptance matrix passes isolated behavioral tests.
- **SC-002**: Every open PR is evaluated within the daily policy interval; interrupted scans make
  measurable progress, and cache loss cannot permanently strand older PRs.
- **SC-003**: Eligible PRs receive a fresh full warning window. Reminder comments never change
  the promised deadline; approved, manually exempt, and bot-authored PRs are not selected to close.
- **SC-004**: Reruns create no duplicate notices or dashboard issues; missed runs send at most the
  currently relevant notice. Every dashboard PR has one primary category and a next action.
- **SC-005**: Observe-only execution produces zero writes. Failed/incomplete classification cannot
  enable closure. Production recovery is claimed only with authorized scheduled-run evidence.

## Assumptions and unresolved dependency

- Daily execution may occur after the exact deadline; never close before it. Display actual
  deadlines and preserve the full initial warning period despite scheduling delays.
- Send only the currently relevant notice after missed runs; do not replay all missed notices.
  Use UTC calendar-date windows for the 7-/1-day notices so normal daily jitter does not skip them;
  the exact absolute closure deadline remains fixed and notices never claim exact remaining hours.
- This is repository automation, with no Infrahub runtime or database/API schema changes.
- **Approved refinement (2026-09-28)**: The user authorized moving forward after the proposed
  companion-managed activity clock and eligibility gate. The companion owns the 60+14 policy;
  pinned upstream stale remains the only closer. The [research](research.md) records proof and
  limitations of this integration, including non-atomic activity and approval snapshots.
