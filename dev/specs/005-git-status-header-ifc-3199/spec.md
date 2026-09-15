# Feature Specification: Git status indicator in the app header

**Feature Branch**: `ple-git-status-header-ifc-3199`

**Spec Directory**: `specs/005-git-status-header-ifc-3199`

**Created**: 2026-09-15

**Status**: Draft

**Jira**: [IFC-3199](https://opsmill.atlassian.net/browse/IFC-3199) — epic IFC-3104

**Input**: Synthesized research brief from three parallel codebase explorations (existing header patterns, repository sync-status APIs, test coverage), plus the Jira ticket.

## Clarifications

### Session 2026-09-15

- Q: Which icon should the glyph use, given BranchSelector already sits in the same header using `mdi:source-branch` and `mdi:source-branch-sync`? → A: `mdi:source-branch` — the ticket's "branch glyph", accepted with the collision risk noted below.
- Q: How should the five states be distinguished from one another? → A: One glyph throughout; colour plus a pulsing dot carry the state. Error = danger colour + pulsing dot; neutral = default foreground; inert = dimmed and not activatable; loading = spinner in place of the glyph; check-failed = `mdi:error-outline` in danger colour. **[SUPERSEDED by the P1 critique entry below: check-failed must NOT use the danger colour.]**
- Q: Is the E2E test required by constitution Principle IV in scope for this ticket? → A: Yes — in scope, driving a branch with a genuinely failed repository import. **[SUPERSEDED: the status is now set directly via mutation; see research R5.]**
- Q: Do the non-error sync statuses (`syncing`, `unknown`) deserve treatment of their own? → A: No. Only the import-error value is distinguished; every other value is neutral, per the ticket's "neutral otherwise". Answered from the ticket rather than asked.
- Q: (from critique, E1) Should the header's time-machine selection re-scope the indicator? → A: No — FR-014 added. The planned data source inherits the time-machine date for free, which is why all three planning explorations missed it. Verified that the existing task indicator does not inherit it, so this is consistency, not an exception.
- Q: (from critique, P1) Should check-failed use the danger colour? → A: No — FR-011 amended. A permission-limited operator fails the lookup permanently, and a red glyph they can never clear is worse than the state it replaced.
- Q: (from critique, E2) Does "either lookup failed" really outrank "no repositories"? → A: No — precedence corrected in data-model.md. When the total is zero the answer is fully determined, so a failed failure-count lookup is irrelevant rather than alarming.
- Q: Should a permission-denied operator see the inert state (as originally specified) or the check-failed state? → A: Check-failed. Raised during planning, where two of three independent plans found the original wording unimplementable as written: the reusable count use-case collapses every GraphQL error to a message and discards the error code, so permission-denied is indistinguishable from any other failure without duplicating that fetching layer inside the repository slice. Rather than add a second count-fetching path for one error code, the requirement changed to match both the honest answer and the existing task-indicator precedent. Recorded as a spec amendment, not a silent implementation choice.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Notice a broken Git import from anywhere (Priority: P1)

An operator is working somewhere in Infrahub — a node list, a proposed change, a schema
page. A repository import on their current branch has failed. Today nothing tells them:
they find out when data they expect is missing, or when someone else reports it. With this
feature a glyph in the top bar turns red and pulses, on every page, so the failure is
noticed while it is still cheap to fix.

**Why this priority**: This is the entire purpose of the epic. The failure this addresses
is one that currently reports itself as healthy — a task can finish green while the import
left the branch in `Import Error`. Without this story there is no feature.

**Independent Test**: Put one repository on a branch into an error sync status, load any
page on that branch, and observe the indicator in the header is red and pulsing. Delivers
the whole "did something break?" answer on its own, even with no other story built.

**Acceptance Scenarios**:

1. **Given** a branch with at least one repository in an error sync status, **When** the
   operator loads any page scoped to that branch, **Then** the header indicator renders in
   its error appearance with a pulsing dot.
2. **Given** a branch whose repositories are all healthy, **When** the operator loads any
   page scoped to that branch, **Then** the header indicator renders in its neutral
   appearance with no pulsing dot.
3. **Given** the operator is viewing a branch with a failure, **When** they switch to a
   branch with no failures, **Then** the indicator returns to neutral without a page reload.
4. **Given** a repository import fails while the operator has a page open, **When** the
   indicator's next poll completes, **Then** it changes to the error appearance without the
   operator reloading or navigating.

---

### User Story 2 - Get from the alarm to the failing repository (Priority: P2)

Seeing that something is wrong is only useful if the operator can act on it. Activating the
indicator lands them on the repository list for that branch, already narrowed to the
repositories in an error state, so they do not have to scan a list or guess which one broke.

**Why this priority**: Turns an alert into a workflow. Valuable only once P1 exists, but
without it the operator has to find the failure by hand, which is the cost this epic set
out to remove.

**Independent Test**: With a branch in a failed state, activate the header indicator and
confirm the destination is the repository list, scoped to the same branch, filtered to the
error sync status, and that the failing repository is present in the result.

**Acceptance Scenarios**:

1. **Given** the indicator is in its error appearance, **When** the operator activates it,
   **Then** they arrive at the repository list filtered to repositories in an error sync
   status, scoped to the branch they were on.
2. **Given** the operator is on a non-default branch, **When** they activate the indicator,
   **Then** the destination remains scoped to that branch and not to the default branch.
3. **Given** the operator is on the default branch, **When** they activate the indicator,
   **Then** the destination carries no redundant branch qualifier.

---

### User Story 3 - Stay out of the way when Git is not in use (Priority: P3)

Not every deployment has Git repositories. Without them the indicator has nothing to report
and nowhere useful to send the operator, so it is present but inert: visible, not activatable,
and occupying exactly the same space it occupies in every other state.

**Why this priority**: A correctness and polish requirement rather than a new capability.
It matters because the header must not shift when the indicator changes state — a control
that appears and disappears moves everything beside it and makes the red state feel like a
glitch rather than a signal.

**Independent Test**: With no Git repositories configured, confirm the indicator is rendered,
is not activatable, and that the header layout is unchanged from the same page where
repositories do exist.

**Acceptance Scenarios**:

1. **Given** no Git repositories are configured, **When** the operator loads any page,
   **Then** the indicator is visible but not activatable.
2. **Given** no Git repositories are configured, **When** the operator compares the header to
   a deployment that has them, **Then** the indicator occupies the same position and
   dimensions in both.
3. **Given** no Git repositories are configured, **When** the operator hovers the indicator,
   **Then** it explains that there are none rather than offering an action. The explanation
   does not describe this as a property of the current branch, because repositories are
   branch-agnostic.

---

### Edge Cases

- **The status lookup itself fails** (network error, backend error): the indicator MUST
  show a distinct error-of-the-check appearance and say so, rather than silently claiming
  the branch is healthy. A failed check and a healthy branch are different facts and MUST
  NOT look the same.
- **First load, before the lookup returns**: the indicator MUST hold its place and show it
  is still determining status, never flashing a neutral or error state it has not confirmed.
- **The branch changes while a lookup is in flight**: the displayed status MUST correspond
  to the branch currently selected, never to the previous one.
- **A repository is added to a previously empty branch**: the indicator MUST become
  activatable on a subsequent poll without a reload.
- **Every repository on the branch is in an error state**: behaves as the ordinary error
  case; no special "all broken" treatment.
- **The operator lacks permission to view repositories**: the status lookup fails, so the
  indicator MUST show the check-failed state of FR-011 — not the inert state of User Story 3.
  Reporting "no Git repositories on this branch" to an operator who simply cannot see them
  would assert something the application does not know, and a branch with many failing
  repositories would read as an empty one. "Status could not be checked" is the accurate
  statement. See the Clarifications entry for the reasoning and the cost that decided it.
- **Many repositories on a branch**: the indicator asks only for counts, so its cost MUST
  NOT grow with the number of repositories.
- **The operator moves the time machine**: the indicator MUST continue to report present-day
  health, unchanged, and the destination it links to MUST also be present-day — a historical
  repository list may not contain the repository failing now (FR-014).
- **The branch has no repositories and the failure lookup fails**: the indicator MUST show
  the inert state, not check-failed. A branch with no repositories cannot have failing ones,
  so the successful lookup fully determines the answer and the failed one is irrelevant.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST display a Git status indicator in the application header on
  every page that renders the header.
- **FR-002**: The indicator MUST derive its state from the sync status of Git repositories,
  and MUST NOT derive it from task state. A completed task does not imply a healthy import.
- **FR-003**: The indicator MUST be scoped to the branch the operator is currently viewing,
  and MUST reflect the branch selected in the application, not a branch named in the URL.
- **FR-004**: The indicator MUST render an error appearance — the glyph in the danger colour
  accompanied by a pulsing dot — when one or more repositories on the current branch are in
  an error sync status.
- **FR-005**: The indicator MUST render a neutral appearance — the glyph in its default
  foreground colour, with no pulsing dot — when the current branch has repositories and none
  are in an error sync status.
- **FR-005a**: The indicator MUST distinguish exactly one condition: whether any repository
  on the branch carries the import-error sync status. Every other sync status value,
  including in-progress and unknown states, MUST render as neutral. The indicator MUST NOT
  introduce a third status treatment.
- **FR-005b**: The indicator MUST use a single glyph across its states. State MUST be
  conveyed by colour, the pulsing dot, the disabled treatment, and the substitutions defined
  in FR-007a and FR-011 — never by swapping the glyph for a different subject.
- **FR-006**: The indicator MUST be present but not activatable when there are no Git
  repositories, and MUST occupy identical space in every state so that no state change alters
  the header layout. Note that repository nodes are branch-agnostic — only their sync status
  is per-branch — so this condition is deployment-wide in practice: a branch cannot have no
  repositories while another branch has some. The count is still issued with branch context,
  which costs nothing and keeps the two lookups consistent.
- **FR-007**: The indicator MUST refresh its state on a recurring interval without operator
  action, on the same cadence as the existing task indicator.
- **FR-007a**: While the first status lookup is outstanding, the indicator MUST show a
  loading treatment in place of the glyph, occupying the same space, and MUST NOT present
  any of the resolved states until the lookup returns.
- **FR-008**: When activated, the indicator MUST navigate to the repository list, scoped to
  the current branch and filtered to repositories in an error sync status.
- **FR-009**: The branch qualifier MUST be omitted from the destination when the current
  branch is the deployment's default branch, and present otherwise. The default branch MUST
  be determined from application state, never by comparing against a hard-coded name.
- **FR-010**: Every visual state MUST carry an equivalent text explanation available on
  hover and to assistive technology. The indicator MUST NOT rely on colour alone to
  distinguish error from neutral — the pulsing dot is the non-colour carrier of that
  distinction, and MUST be present in the error state and absent otherwise.
- **FR-010a**: Each state MUST have distinct hover and assistive-technology text, naming the
  condition rather than the control. The five states are: repositories failing on this
  branch; repositories present and healthy; no repositories configured; status still being
  determined; and status could not be checked. The inert state's name MUST NOT mention a
  branch: repositories are branch-agnostic, so it would be inaccurate.
- **FR-011**: When the status lookup fails, the indicator MUST substitute a dedicated
  check-failed symbol, with its own explanation, and MUST NOT report the branch as healthy.
  This substitution is the one permitted exception to FR-005b, since the subject genuinely
  changes from "Git health" to "this check did not run". The check-failed state MUST NOT use
  the danger colour reserved for FR-004: an operator who lacks permission to read
  repositories fails this lookup on every page indefinitely, and a permanent red alarm they
  can never clear would both misreport their situation and erode the meaning of the real
  error state for everyone else. A muted or warning treatment is required.
- **FR-014**: The indicator MUST report Git health as of now, and MUST NOT be re-scoped by
  the header's time-machine selection. An operator inspecting a past point in time MUST still
  see the current state of the branch. Reporting historical health in the present tense would
  recreate, through a different route, exactly the falsely-reassuring signal this feature
  exists to eliminate. Note that the existing task indicator is already unaffected by the time
  machine, so this keeps the two header controls consistent rather than making an exception.
- **FR-012**: The indicator MUST count repositories of every Git repository kind on the
  branch, not only the standard kind.
- **FR-013**: The existing task indicator MUST remain in the header, unchanged in behaviour
  and appearance. The two controls MUST NOT be merged.

### Out of Scope

- Per-repository detail in the header, a dropdown, or a notification list. The indicator
  links out; it does not explain.
- Any change to how repository sync status is produced, recorded, or recovered.
- Any change to the existing task indicator.
- Release notes. A changelog fragment is in scope; release notes are assembled per release.

### Key Entities

- **Git repository**: a repository tracked by Infrahub on a branch. Carries a sync status
  whose value is per-branch. Exists in more than one kind; all kinds count for this feature.
- **Repository sync status**: the per-branch state of a repository's last import. The
  feature cares about exactly one distinction — is it the error value, or not.
- **Current branch**: the branch the operator is viewing, held in application state. Its
  default-branch flag is deployment-configurable.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator on a branch with a failed repository import can tell that
  something is wrong from any page in the application, without navigating.
- **SC-002**: From noticing the indicator, an operator reaches the specific failing
  repository in one activation.
- **SC-003**: A repository failure that occurs while a page is open becomes visible within
  one refresh interval, with no operator action.
- **SC-004**: The header's layout is identical across all indicator states — no element
  moves when the indicator changes between inert, neutral, error, loading, and check-failed.
- **SC-005**: Every indicator state is distinguishable without perceiving colour.
- **SC-006**: The indicator's cost does not grow with the number of repositories on the
  branch.
- **SC-007**: A failed status lookup is never presented as a healthy branch.

## Assumptions

### Decisions already taken (do not re-open)

- **Empty state is inert, not hidden.** The indicator is held in place and made
  non-activatable when the branch has no repositories. Determining this requires knowing
  both how many repositories are on the branch and how many are failing — two counts. The
  user explicitly chose two separate lookups over a single combined one.
- **The branch is based on `cross-branch-repo-status-infp-671`** and the pull request will
  target that branch, not the default branch.
- **The glyph is `mdi:source-branch`** — the ticket's "branch glyph", taken literally. This
  was chosen over a purpose-drawn asset with a known risk accepted: the branch selector sits
  a few pixels away in the same header and already renders `mdi:source-branch`, so the same
  symbol will appear twice in one bar meaning two different things. Mitigations available to
  the plan without re-opening the decision: the danger colour and pulsing dot differentiate
  the error state, and the two controls differ in shape treatment. If review finds the two
  read as one control, substituting a bespoke asset is a contained change — the icon is
  referenced from exactly one component.
- **The E2E test is in scope for this ticket**, exercising a branch that genuinely carries the
  import-error status rather than only asserting the indicator renders. The status is set
  directly on an existing fixture repository — it is an ordinary writable attribute — rather
  than by engineering a real import failure, which would have tested the importer rather than
  this feature. See research R5.

### Technical constraints established by research

- **`InfrahubRepositoryBranchStatus` (IFC-3126) MUST NOT be the data source.** It is a
  contract stub: it is keyed by a single repository and returns one row per branch — the
  opposite of the axis this feature needs; its values are fabricated from a hash of the
  branch name; its own module documentation states it will be deleted; and its resolver
  explicitly rejects filtering on sync status while the values are placeholders. Building on
  it would produce an indicator that reports convincing nonsense.
- The indicator reads counts of the generic Git repository kind, filtered on the error sync
  status value, with the branch supplied as query context. The generic kind covers every
  concrete repository kind in one lookup, satisfying FR-012.
- The error sync status value is the backend enum's import-error value; its human label is
  "Import Error". Sync status is a per-branch attribute, which is what makes FR-003
  answerable at all.
- The existing task indicator is the structural precedent for this control end to end —
  layering, polling cadence, tooltip, pulse, and branch-aware link construction. Deviating
  from it needs a reason.
- Filters on attribute values are submitted as partial matches by the shared query builder.
  For the error value this yields a correct count today because no other sync status value
  contains it as a substring — but this is incidental, and the plan MUST either confirm it
  is safe or avoid the partial-match path.

### Scope and environment assumptions

- The header is the right surface: it is the one element present on every page, which is
  what "from every page" in the ticket requires.
- Ten seconds is the correct refresh cadence, matching the existing task indicator. Faster
  adds load for a condition that changes on the order of minutes; slower makes the signal
  feel stale.
- Operators who can view a branch can generally view its repositories; where they cannot, the
  lookup fails and the check-failed state of FR-011 applies. This is deliberately not the inert
  state — see the Clarifications entry on permission-denied.

## Constitutional Compliance

- **Principle II (Branch-Safe by Default)**: the feature is branch-scoped by construction.
  Branch correctness — including the configurable default branch name and in-flight branch
  changes — is covered by FR-003, FR-009 and the edge cases, and MUST be tested.
- **Principle III (Type Safety)**: generated API types are consumed as generated; no
  hand-edited generated files, no `any`, no non-null assertions.
- **Principle IV (Test Discipline)**: component tests for every indicator state; a unit
  test for the state-derivation logic; and an E2E test, confirmed in scope, that seeds a
  a repository carrying the import-error status rather than asserting mere presence — the constitution holds the
  feature incomplete until E2E passes. Note that the header currently has no test of its
  own, so mounting coverage is a genuine addition.
- **Principle V (Query Efficiency)**: counts only, never repository lists — see SC-006.
- **Principle VII (Simplicity)**: follows the existing task-indicator pattern rather than
  introducing a second approach to the same problem.
- **Quality gates**: a Towncrier changelog fragment is required (user-facing change), and
  user documentation under `docs/` must be assessed.
