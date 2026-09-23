# Feature Specification: Dependency-bump autopilot

**Feature Branch**: `dependabot-autopilot`

**Created**: 2026-09-23

**Status**: Draft

**Input**: User description: "Dependency-bump autopilot. Source PRD: Notion hackathon card 'Automatic middleware dependencies management and opportunities identification' plus the hardened idea brief. Scope: Dependabot-opened PRs only; P1 verdict + automatic merge, P2 deduplicated Jira tech-debt items with rubric priority, P3 weekly #release-radar digest."

## Context

Dependabot opens roughly four pull requests a week against `stable` (48 in the 90 days to 2026-09-23). Every one of them was merged; none was rejected. An engineer still has to trigger the dependency-bump analysis by hand, read the report, approve, and merge, which puts a median of 8.2 hours (p90 23 hours) between a bump being proposed and it landing. Upstream features worth adopting are noticed by chance and filed by hand, if at all.

The dependency-bump analysis already exists as an agent skill. It produces one of three verdicts per PR (`safe to merge`, `needs code changes`, `review required`), grounds every "safe" claim in a search of the repository's actual usage, and lists breaking changes, deprecations and opportunities per package. This feature runs that analysis without a human and acts on its verdict. Merging patch and minor bumps by version number alone would remove the wait too, but it would merge minor releases that break code the repository uses and would never surface opportunities; grounding the decision in actual usage is what makes unattended merging acceptable.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Verdict and automatic merge (Priority: P1)

When Dependabot opens or updates a pull request, the analysis runs on its own and posts its report on the PR. A `safe to merge` verdict on a PR whose checks are all green leads to an approval and a merge with no human action. A `needs code changes` verdict blocks the PR with the reasons. A `review required` verdict leaves the PR open, labelled, with its owner notified.

**Why this priority**: This removes the recurring manual step on every Dependabot PR and closes the 8-hour latency on security patches. It is the smallest slice that delivers the time saving the idea is about.

**Independent Test**: Open three Dependabot-authored PRs in a sandbox repository or against fixtures: one bumping a package the code base does not use, one bumping a package whose removed API is used, one whose changelog cannot be retrieved. Observe a merge, a blocking review, and an escalation respectively, with no human action.

**Acceptance Scenarios**:

1. **Given** a Dependabot PR against `stable` whose bumped packages touch no code the repository uses, and every check on its head commit is green, **When** the analysis finishes with `safe to merge`, **Then** the report is posted on the PR, the PR is approved by the automation, and it merges without human action.
2. **Given** a Dependabot PR where a breaking change affects code the repository uses, **When** the verdict is `needs code changes`, **Then** a blocking review lists each affected usage with its file and line, the PR's owner is notified, and the PR does not merge.
3. **Given** a Dependabot PR whose changelog is ambiguous, whose analysis fails, or whose lockfile gains a package that was not there before, **When** the verdict is `review required`, **Then** the PR is labelled, its owner is notified, and it does not merge.
4. **Given** a PR the automation has approved, **When** Dependabot pushes a new commit to it, **Then** the automation withdraws its approval, analyses the new head commit, and acts on the new verdict only.
5. **Given** a `safe to merge` verdict, **When** any check on the head commit fails, **Then** the PR does not merge and is escalated as `review required`.

---

### User Story 2 - Tech-debt items from opportunities (Priority: P2)

Opportunities and deprecations the analysis finds become tech-debt items in Jira with an initial priority, so they enter the normal triage flow instead of being lost in a PR comment. The same opportunity seen on a later bump updates the existing item instead of creating a duplicate.

**Why this priority**: It turns the analysis's opportunity findings into tracked work. It depends on the analysis running automatically (P1) but not on automatic merge, and it can ship after P1.

**Independent Test**: Run the analysis on two successive Dependabot PRs that bump the same package and surface the same opportunity. Observe one Jira item created by the first run and a comment linking the second PR added by the second run.

**Acceptance Scenarios**:

1. **Given** a report that lists an opportunity for a package, **When** no open tech-debt item exists for that package and opportunity, **Then** one is created with the priority given by the rubric and a link to the PR.
2. **Given** an open tech-debt item already exists for that package and opportunity, **When** a later PR's report lists it again, **Then** the existing item receives a comment linking the new PR and no new item is created.
3. **Given** a PR whose verdict is `needs code changes`, **When** the report is processed, **Then** no tech-debt item is created for the blocking breaking changes; the blocked PR is the tracker.

---

### User Story 3 - Weekly #release-radar digest (Priority: P3)

Once a week, a single message in #release-radar lists the High and Medium tech-debt items filed or updated that week, with their links, so engineers see what upstream releases unlocked without watching every PR.

**Why this priority**: Visibility on top of P2's data. Useful but not required for either the time saving (P1) or the tracking (P2).

**Independent Test**: With at least one High and one Low item filed during the week, trigger the digest and observe one message that lists the High item and omits the Low one.

**Acceptance Scenarios**:

1. **Given** High or Medium tech-debt items were filed or updated during the week, **When** the weekly digest runs, **Then** one message is posted to #release-radar listing each of them with its link.
2. **Given** no High or Medium item was filed or updated during the week, **When** the weekly digest runs, **Then** no message is posted.

---

### Edge Cases

- **New commit after approval**: the branch rules on `stable` do not withdraw approvals when new commits arrive, so the automation must withdraw its own approval itself before analysing the new head commit (FR-003).
- **Grouped PR with mixed verdicts**: one package's `needs code changes` blocks the whole PR; the strictest verdict across packages applies (FR-007).
- **Analysis failure or timeout, unreachable changelog**: the verdict falls back to `review required`, never to `safe to merge` (FR-006).
- **Checks still running when the verdict lands**: the automation waits for every check on the analysed commit to finish before deciding; it does not merge while any check is pending (FR-004).
- **`safe to merge` with a failed check**: no merge; the PR is escalated as `review required` (FR-004).
- **New package in the lockfile**: a grouped bump that pulls in a package absent from the lockfile before the PR is capped at `review required`, whatever the analysis says (FR-006).
- **PR with no code owner**: `github-actions` bumps touch `.github/`, which has no code owner; the notification goes to the fallback recipient (FR-009).
- **Blocked PR left open**: a PR blocked by `needs code changes` can stay open for weeks. It is tracked only on the code host, not in Jira or the digest.
- **Same opportunity on repeated bumps**: Dependabot re-proposes the same package range several times (for example the cache action from 5.0.5 to 6.1.0 appeared on three PRs); the dedup rule adds a comment instead of a new item (FR-011).
- **Analysis never runs**: the analysis workflow is disabled, an event is dropped, or runners are unavailable. Sixty minutes after a head commit with no analysis run for it, the PR is escalated as `review required` with the reason "analysis did not run" (FR-017).
- **Freshly published release**: a compromised upstream release can carry a benign changelog and pass CI. Version updates are proposed only once the release has aged (FR-018); security updates are not delayed.
- **A human intervenes**: a human who approves, merges, closes, or requests changes on the PR takes precedence; the automation does not undo a human action.

## Requirements *(mandatory)*

### Functional Requirements

#### Verdict and merge (P1)

- **FR-001**: System MUST run the dependency-bump analysis on every pull request authored by Dependabot when it is opened and whenever its head commit changes, with no manual trigger.
- **FR-002**: System MUST post the analysis report on the PR, including the evidence behind every `safe` or `not used` claim (the search that proves the absence of usage, or the role mismatch).
- **FR-003**: System MUST bind each verdict to the head commit it analysed. When the head commit changes, System MUST withdraw any approval it gave and analyse the new head commit.
- **FR-004**: System MUST approve and merge a PR only when all of the following hold: the verdict is `safe to merge`, the analysed commit is still the PR's head commit at merge time, and every check on that commit has finished successfully. A failed check MUST escalate the PR as `review required`.
- **FR-005**: On `needs code changes`, System MUST submit a blocking review that lists each affected usage with its file and line, and MUST notify the PR's owner. No tech-debt item is created.
- **FR-006**: System MUST set the verdict to `review required` when the analysis fails, times out, or cannot retrieve a changelog, and when the lockfile diff adds a package that was not present before the PR.
- **FR-007**: For a PR that bumps several packages, System MUST apply the strictest per-package verdict to the whole PR (`needs code changes` over `review required` over `safe to merge`).
- **FR-008**: On `review required`, System MUST label the PR and notify its owner, and MUST NOT approve or merge it.
- **FR-009**: The owner of a PR MUST be the code owners of the files it changes; when no code owner matches, System MUST notify a single configured fallback recipient.
- **FR-010**: System MUST NOT act on pull requests that Dependabot did not author, and MUST NOT override a human's approval, merge, close, or request for changes on a PR.

#### Tech-debt items (P2)

- **FR-011**: System MUST create at most one open tech-debt item per (package, opportunity). Before creating an item, System MUST look for an open item with the same package and opportunity and, if one exists, add a comment linking the new PR instead.
- **FR-012**: System MUST set each new item's initial priority from this rubric: security fix or deprecation with a removal deadline → High; performance or simplification with cited code → Medium; anything else → Low.
- **FR-013**: Each tech-debt item MUST link the PR that surfaced it and cite the code locations the opportunity applies to.

#### Digest (P3)

- **FR-014**: System MUST post at most one message per week to #release-radar listing the High and Medium tech-debt items filed or updated that week, with their links, and MUST post nothing in a week with no such item.

#### Operations

- **FR-015**: Users MUST be able to see, for every automated action (approval, merge, blocking review, escalation, item creation), which commit and verdict it was based on, from the PR itself.
- **FR-016**: Users MUST be able to turn the automatic merge off without disabling the analysis, so that verdicts keep being posted while merges wait for a human.
- **FR-017**: When no analysis has run for a Dependabot PR's head commit 60 minutes after that commit was pushed, System MUST escalate the PR as `review required` with the reason "analysis did not run".
- **FR-018**: Dependabot version updates MUST be proposed only for releases published at least 3 days earlier; security updates MUST NOT be delayed.
- **FR-019**: System MUST treat the analysis output as untrusted: it MUST NOT execute anything from it, and MUST neutralize mentions and hidden markup in the report text before posting it on the PR.
- **FR-020**: An unavailable tech-debt tracker or chat service MUST NOT block, delay or change a PR's verdict or merge; filing is retried on the next evaluation of the same head commit.

### Key Entities

- **Dependabot PR** (existing): a pull request authored by Dependabot against `stable`. The only unit of work this feature acts on.
- **Verdict** (existing): the outcome of the analysis for one PR at one head commit: `safe to merge`, `needs code changes`, or `review required`. The automation needs it in a form it can act on, not only as prose.
- **Opportunity** (existing concept in the analysis report): a new upstream capability, default or deprecation worth acting on, with the code it applies to. Identified by (package, opportunity) for deduplication.
- **Tech-debt item** (existing Jira concept): the tracked work created from an opportunity, carrying the rubric priority and links back to the PR and code.
- **Automation identity** (new): the identity that approves and merges on behalf of the automation. Its approval counts toward the one approval `stable` requires.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 80% of Dependabot PRs merge with no human action over the first 8 weeks after launch.
- **SC-002**: The median time from a `safe to merge` PR being opened to it being merged is under 1 hour (baseline: 8.2 hours).
- **SC-003**: No automatically merged bump is reverted, or needs a follow-up fix attributed to the bump, in the first 3 months after launch.
- **SC-004**: No duplicate tech-debt item is created, and at most 20% of automatically filed items are closed as "won't do" or "not relevant" within 30 days of creation.

## Constitution Alignment

- **VI. Security & Input Boundaries, "Dependencies MUST be reviewed before addition"**, and **Security Requirements, "Dependency additions require review"**: preserved as written. A PR that adds a package to the lockfile never merges automatically (FR-006).
- **VI, "kept updated to address known vulnerabilities"** and **Security Requirements, "Known vulnerability patches MUST be applied promptly"**: supported by the latency target (SC-002).
- **Code Quality Gates, "All code MUST pass these gates before merge"**: enforced by the automation itself, because `stable` has no required checks (FR-004).
- **VII. Simplicity & Maintainability**: the feature reuses the existing analysis skill and the repository's existing agentic-workflow setup rather than building a new analysis engine.

## Governance Gates Crossed

| Gate (from AGENTS.md "Ask First") | Crossed | Why |
|---|---|---|
| Database schema or migration changes | No | No product change |
| GraphQL schema modifications | No | No product change |
| New dependencies | No | No runtime dependency; the automation runs in CI |
| CI/CD workflow changes | **Yes** | New workflow triggered by Dependabot PRs, able to merge into `stable`, plus a weekly scheduled workflow |
| Authentication/authorization changes | **Yes** | New automation identity allowed to approve and merge on `stable`; Jira and Slack credentials held by CI |

## Out of Scope

- Pull requests not authored by Dependabot, including hand-rolled bumps of runtime libraries (Prefect, FastAPI, zod). They may receive the analysis manually as today.
- Service images shipped with Infrahub (Neo4j, RabbitMQ, Redis, Prefect server) in the compose file or the Helm chart.
- The automation writing code fixes for `needs code changes`.
- Changing the branch rules on `stable` (required checks, dismissing approvals on new commits).
- Adding version-update ecosystems to the Dependabot configuration. The only Dependabot configuration change in scope is the release-age cooldown (FR-018).
- Dependabot PRs targeting branches other than `stable`.

## Assumptions

- Dependabot keeps opening `github-actions`, `uv` and `npm` PRs against `stable` at roughly the current rate (about 4 a week) without configuration changes.
- The analysis skill can run without a human and can emit its verdict in a machine-readable form alongside the prose report.
- Merges into `stable` reach `develop` through the existing stable-to-develop merge process.
- **Tech-debt location** (resolved during specification): items go to the engineering Jira project with a tech-debt label, unassigned, so they enter the existing triage queue. The project key is configuration, not code.
- **Automation identity** (resolved during specification): a dedicated identity whose only elevated right is approving and merging Dependabot PRs, rather than the existing bot account that already has branch-rule bypass rights. Least privilege outweighs reusing an existing account.
- **Owner to notify** (resolved during specification): the code owners of the changed files, with a single configured fallback recipient for files no code owner covers (such as `.github/`).
