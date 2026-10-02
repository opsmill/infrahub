# Feature Specification: Git remote writeback failure handling

**Feature Branch**: `gma-20261002-ifc3220`

**Created**: 2026-10-02

**Status**: Draft

**Input**: Jira epic IFC-3220 "Git remote writeback failure handling". Source PRD: Notion page
`a81228b830258373bc5b81dbb878345c`, mirrored on Confluence page 861896706. Product card INFP-670.
Sibling epic IFC-3210, specified in `dev/specs/ifc-3210-history-rewrite-reconciliation/`.

## Context

When Infrahub merges a branch that is synchronised with Git, it merges the matching Git branches and
pushes the result to the remote. The push can fail. The usual causes are a missing push permission,
branch protection, an expired token, a network fault and a certificate error.

PR #10465 (IFC-1449) is on `develop`. After a rejected push, Infrahub no longer records a commit the
remote does not have, and the destination worktree goes back to its pre-merge commit. Four gaps
remain:

- Nothing on the repository says that the push failed. The only trace is a failed task run, which a
  user must know to look for.
- The product has no retry. Recovery needs orchestrator access. In practice a member of the Solution
  Architecture team does it, at about two hours per incident.
- Merges that accumulate while the remote rejects pushes are not tracked. Nothing knows what is
  still to deliver, and nothing can abandon a change that cannot be delivered.
- Post-merge regeneration does not wait for the push. When the push fails, artifacts, generators and
  transform-based computed attributes run against the commit recorded before the merge, while the
  merged data expects the merged content.

Two writes to independent systems have no transaction that spans them. The order of the writes only
chooses which side can get ahead. Persisted delivery state is what coordinates them, and that is
this work.

### Terms

| Term | Meaning |
|---|---|
| **Delivery** | The push of merged repository content from Infrahub to the remote. |
| **Pending delivery** | A merge whose repository content Infrahub has not delivered yet. |
| **Delivery queue** | The ordered list of pending deliveries for one repository and one destination branch. |
| **Delivery attempt** | One run that fetches the remote, replays the queue, pushes once and records the result. |
| **Held regeneration** | Regeneration work that waits until the delivery queue of its repository clears. |
| **Release** | The dispatch of held regeneration after the queue clears. |
| **Abandonment** | A deliberate decision by a user to stop delivering the pending queue. |

In this codebase a branch merge always targets Infrahub's default branch. The destination of every
delivery is therefore the repository's configured default branch on the remote, and the delivery
state lives on the repository as seen from Infrahub's default branch.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A failed delivery is visible on the repository (Priority: P1)

An operator merges a branch that is synchronised with Git. The remote rejects the push. The
repository itself shows that the merged content did not reach the remote, why, in the remote's own
words, and what the operator must do. The operator needs no worker log and no orchestrator access.

**Why this priority**: This is the first gap. Without it, users assume that merged changes are live,
and nobody knows that recovery is necessary.

**Independent Test**: Install a server-side rejection on the default branch of a live remote. Merge
a branch that is synchronised with Git. Read the repository on the default branch. It must show one
pending delivery, the status "action required", the cause "permission or branch protection" and the
remote's rejection message.

**Acceptance Scenarios**:

1. **Given** a read-write repository whose remote rejects pushes to its default branch, **When** a
   branch synchronised with Git merges, **Then** the repository reports one pending delivery for
   that merge, with the status "action required".
2. **Given** the same repository, **When** a user reads its delivery state, **Then** the state
   carries the cause and the remote's rejection message exactly as the remote sent it.
3. **Given** the same repository, **When** a user reads its commit on the default branch, **Then**
   the commit is unchanged and equals the commit on the remote.
4. **Given** a merge whose first delivery attempt succeeds, **When** a user reads the repository,
   **Then** it reports nothing pending and no error.
5. **Given** a pending delivery, **When** a user views the repository from a branch that is not the
   default branch, **Then** the view shows the current delivery state of the default branch, and
   never a stale copy that the branch inherited when it was created.

---

### User Story 2 - One retry delivers everything that accumulated (Priority: P1)

The operator fixes the cause, for example by granting push permission. A user with write access on
the repository triggers one retry from the product. Infrahub fetches the remote, replays every
pending merge in order on top of the current remote branch, and delivers them all in one push. The
repository returns to a healthy state.

**Why this priority**: This removes the support ticket. A multi-day outage must need one action, not
one action per merge.

**Independent Test**: Reject pushes on a live remote. Merge two branches. Lift the rejection.
Trigger one retry. The remote must hold both merges, in order, after one push. The recorded commit
must equal the remote head, and nothing must be pending.

**Acceptance Scenarios**:

1. **Given** two merges pending in order, **When** a user with write access triggers a retry,
   **Then** both merges are replayed in order, one push delivers them, the recorded commit advances
   to the delivered commit, and nothing is pending.
2. **Given** one pending merge, **When** a second branch merges, **Then** the second merge is
   appended to the queue, and the first one stays in the queue.
3. **Given** a remote default branch that advanced during the outage, **When** the retry runs,
   **Then** the replay merges onto the fetched remote head, no force-push happens, and the remote
   commits that Infrahub had not imported are imported before the delivered commit is recorded.
4. **Given** a push that the remote accepted while the recording failed, **When** the next attempt
   runs, **Then** Infrahub sees that the remote already holds the merges, records the commit, clears
   the queue and pushes nothing again.
5. **Given** a user without write access on the repository, **When** that user triggers a retry,
   **Then** the system refuses it.
6. **Given** a repository with nothing pending, **When** a user triggers a retry, **Then** the system
   refuses it and says that nothing is pending.
7. **Given** a pending queue and a fixed cause, **When** another branch merges before anyone
   triggers a retry, **Then** the first attempt of that merge delivers the whole queue. The first
   attempt and the retry are the same operation.

---

### User Story 3 - Regeneration waits for the final content and runs once (Priority: P1)

While a repository has a pending delivery, the post-merge regeneration of the definitions that this
repository owns waits. When the queue clears, the held work runs once, against the commit that is
then on the remote. The definitions of other repositories regenerate as usual.

**Why this priority**: Without this, a failed push produces artifacts and computed values from a
commit that does not match the merged data, and a recovery pays the regeneration cost twice.

**Independent Test**: Use two repositories, each with an artifact definition, a generator definition
and a Python-transform computed attribute. Reject pushes for the first one. Merge a branch that
touches both. The second repository must regenerate at once. The first must regenerate nothing until
the delivery clears, then exactly once, against the delivered commit.

**Acceptance Scenarios**:

1. **Given** repository X with a pending delivery and repository Y without one, **When** a merge
   follow-up selects definitions of both, **Then** the definitions of Y are dispatched normally and
   the definitions of X are held.
2. **Given** held work for X, **When** the queue of X clears by delivery, **Then** exactly one
   release for X runs. It covers every held definition with no member or target narrowing, and it
   runs against the delivered commit.
3. **Given** a delivery that completes before the merge follow-up runs, **When** the follow-up runs,
   **Then** it dispatches normally, holds nothing, and no release runs.
4. **Given** a held definition that a user deletes before the release, **When** the release runs,
   **Then** it widens to full regeneration of the branch instead of skipping the gap.
5. **Given** pending deliveries on two repositories, **When** each queue clears, **Then** each
   repository releases its own held work, independently.
6. **Given** a Python-transform computed attribute whose transform belongs to X, **When** the
   coalesced recompute of a merge runs, **Then** the recompute of that attribute is held. Jinja2
   computed attributes, display labels and human-friendly ids are never held.
7. **Given** held work for X, **When** a user abandons the queue of X, **Then** the release still
   runs, exactly once.

---

### User Story 4 - Transient faults heal, policy faults stop at once (Priority: P2)

A network blip during a push resolves without anyone. A missing permission or a branch protection
does not retry for an hour. The repository says at once what to fix.

**Why this priority**: It turns a momentary fault into zero user actions, and a policy fault into
one clear action. It depends on the queue and the status of P1.

**Independent Test**: Make the remote unreachable for a short time during a push, then reachable.
The delivery must complete with no user action. Separately, reject the push by policy. The status
must become "action required" after one attempt, with no automatic retry.

**Acceptance Scenarios**:

1. **Given** a transient network failure during a delivery, **When** the fault clears within the
   window of the automatic retries, **Then** the delivery completes with zero user actions.
2. **Given** a transient failure that lasts longer than every automatic retry, **When** the last
   automatic retry fails, **Then** the status is "action required" with the cause "remote
   unreachable", and a manual retry is available.
3. **Given** a credential, permission or branch-protection failure, **When** the attempt fails,
   **Then** no automatic retry runs and the status is "action required" at once.
4. **Given** an automatic retry that waits to run, **When** a user reads the status, **Then** the
   status is "pending", not "action required".

---

### User Story 5 - Abandon an undeliverable change, with a record (Priority: P2)

Sometimes the queue cannot be delivered. For example, the remote default branch received a change
that conflicts with a pending merge. A user with write access abandons the queue on purpose. The
repository returns to a working state, and the system records what was dropped, by whom and when.

**Why this priority**: Without it, a stuck repository stays stuck for ever. It ships after P1
because it matters only once deliveries can be pending.

**Independent Test**: Make a pending merge conflict with a change pushed directly to the remote.
Trigger a retry. It must fail at that merge and push nothing. Abandon the queue. The queue must be
empty, the record must name the merges, the user and the time, and the held regeneration must run.

**Acceptance Scenarios**:

1. **Given** a queue whose replay conflicts with the remote head, **When** a retry runs, **Then** it
   stops at that merge, pushes nothing, and sets the status "action required" with the cause "replay
   conflict". The required action is to abandon.
2. **Given** a pending queue, **When** a user with write access abandons it and names the queue
   state that the user saw, **Then** the queue clears, a record of the abandoned merges, the user
   and the time is stored, and the held regeneration is released.
3. **Given** a queue that changed after the user read it, **When** that user abandons it, **Then**
   the system refuses the request as stale.
4. **Given** an abandonment, **When** it completes, **Then** the repository-owned objects on the
   default branch match the content of the commit recorded for that branch, before the release
   runs.
5. **Given** an abandonment, **When** it completes, **Then** nothing was removed from the remote,
   and the remote source branches still exist.
6. **Given** any path other than a delivery or an abandonment, including the generic repository
   update, **When** it runs, **Then** it cannot change or clear the delivery state.

---

### User Story 6 - A delivery keeps the commits it needs (Priority: P2)

A pending delivery replays merge inputs from the remote. The remote branch that holds a source commit
must stay on the remote until the delivery clears. Other merges continue while one repository's
remote is broken.

**Why this priority**: If the source branch is deleted, the source commit can be garbage-collected
and the delivery becomes impossible. With `delete_git_branch_after_merge` enabled this path is
reachable today.

**Independent Test**: Enable branch deletion after merge. Reject pushes. Merge a branch. The remote
source branch must still exist after the deletion flow ran. Clear the queue. A later deletion must
proceed normally.

**Acceptance Scenarios**:

1. **Given** a pending delivery whose source is remote branch S, **When** Infrahub would delete S
   from the remote, **Then** it does not delete S, and it logs why.
2. **Given** no pending delivery that references S, **When** Infrahub deletes S, **Then** the
   deletion proceeds as it does today.
3. **Given** a pending delivery on repository X, **When** a user merges another branch, **Then** the
   merge is not blocked.

---

### User Story 7 - A history rewrite that breaks or reverts a delivery is reported (Priority: P3)

A developer rewrites a remote branch that a pending delivery depends on. Or someone rewrites the
remote default branch and discards a commit that Infrahub delivered. Infrahub never pushes the
discarded commits back, and it says which case happened.

**Why this priority**: These requirements come from the sibling epic IFC-3210, which defers them to
this epic because they read this queue. The safety checks of scenarios 1 and 2 ship with the replay
of User Story 2. Scenario 3 needs the rewrite detection of IFC-3210.

**Independent Test**: Queue a delivery. Force-push the remote source branch so that the queued
source commit is no longer on it. Trigger a retry. It must push nothing and report the delivery as
unreplayable, with a cause that names the discarded source commit.

**Acceptance Scenarios**:

1. **Given** a queued source commit that is no longer reachable from its remote branch, **When** the
   next attempt runs, **Then** it pushes nothing and marks the delivery unreplayable, with the cause
   "source commit no longer on the remote".
2. **Given** a remote default branch whose history no longer contains the commit recorded for it,
   **When** the next attempt runs, **Then** it pushes nothing and marks the delivery unreplayable,
   with the cause "destination history rewritten".
3. **Given** a rewrite of the remote default branch that discarded a commit Infrahub delivered,
   **When** the reconciliation of IFC-3210 handles the rewrite, **Then** the system records a
   reverted delivery, as a condition distinct from scenario 1.

---

### Edge Cases

- **A second merge lands while a delivery is outstanding.** It is appended to the queue and never
  replaces an earlier entry. One retry delivers both.
- **The pending queue becomes unreplayable.** The remote destination advanced and a replayed merge
  now conflicts. The retry fails at that entry and cannot succeed. Abandonment is the only exit. See
  "Decisions Taken During Specification".
- **The worker that performed the merge never returns.** Nothing on a worker's disk is
  load-bearing. The queue names merge inputs that are on the remote, so any worker can perform the
  delivery.
- **The remote destination advanced between the failure and the retry.** The replay merges onto the
  freshly fetched remote head. No force-push happens. Infrahub imports the remote commits it had not
  imported before it records the delivered commit.
- **The periodic synchronisation runs while a delivery is pending.** It does not advance the
  destination branch of that repository. A desired-state import of the remote head would delete
  the merged repository objects that are not delivered yet. The delivery imports the remote commits
  instead. Other branches synchronise as usual.
- **The remote source branch would be deleted after the merge.** Refused while a delivery that
  references it is outstanding, so the commit needed for the replay cannot be garbage-collected. The
  remote branch stays after the queue clears. It is not deleted later.
- **The delivery succeeds but the recording fails.** The destination worktree is reset behind the
  remote, and the queue stays. The next attempt sees that the remote already holds the merges. It
  records the commit and clears the queue by observation, never by replay.
- **The import fails after a successful push.** The remote received content that Infrahub cannot
  import. The attempt fails with the cause "import failed" and the remote content stays. A retry
  after the content is fixed on the remote imports and records it.
- **A branch is left ahead of its remote.** The reset on failure prevents the once-a-minute "update
  detected but commit unchanged" loop.
- **The delivery completes before the merge follow-up runs.** The barrier sees an empty queue and
  dispatches as usual. It holds nothing, and no release runs. Nothing regenerates twice.
- **Several repositories fail delivery after the same merge.** Each keeps its own queue and its own
  held set, and each releases independently.
- **A held definition is deleted before the release.** It is skipped, and its absence widens the
  release to full regeneration of the branch instead of leaving a silent gap.
- **A failure between the release dispatch and the clear of the held set.** The release can run a
  second time. It can never be lost. Over-execution is the accepted direction.
- **A branch forked from the default branch while a delivery is pending.** A branch-local value is
  read through the branch it forked from, so the new branch sees a copy of the delivery state as it
  was at the fork. The product never acts on that copy and never presents it as current.
- **An abandonment while a delivery attempt runs.** The two never interleave. The abandonment waits
  for the attempt or is refused, and it then checks the queue state again.
- **An abandonment after the remote accepted a push that Infrahub did not record.** Abandonment never
  removes content from the remote. The remote keeps the merged content, and the next synchronisation
  imports it.
- **A direct edit while a delivery is pending.** A live edit runs transforms against the recorded
  commit, which is the commit on the remote. It is not held. Only the merge follow-up is held.
- **Concurrent attempts.** The first attempt of a merge and a manual retry can overlap. They run one
  after the other. The second one finds nothing pending and does nothing.
- **The Infrahub source branch is deleted after the merge.** The queue references the source by its
  remote branch and its commit, not by the Infrahub branch, so the replay still works.
- **The repository is deleted while a delivery is pending.** Its delivery state and its held work go
  with it. The repository's definitions are deleted with it, so nothing it owned remains to
  regenerate.
- **Time-travel queries against a superseded commit.** The recorded commit stays queryable at a past
  time. Content at that commit cannot always be re-derived once the remote no longer holds it, and
  that varies by worker. Accepted and documented. The sibling spec says more.
- **A repository with two hundred branches.** The delivery state lives on the default branch only,
  so any surface that lists it needs one read per repository, not one per branch.

## Requirements *(mandatory)*

The identifiers FR-001 to FR-019 match the source PRD. FR-020 and FR-021 are FR-015 and FR-016 of
the IFC-3210 PRD, which that epic defers to this one. FR-005a and FR-022 to FR-026 are added here.
"Decisions Taken During Specification" says why each one is added.

### Functional Requirements

#### Delivery correctness

*FR-001 to FR-003 are satisfied by PR #10465. They stay, because they remain requirements of the
system, and the new delivery path must keep them true.*

- **FR-001** *(satisfied by #10465)*: The system MUST deliver content to the remote before it
  records the resulting commit, and MUST NOT record a commit the remote has not accepted.
- **FR-002** *(satisfied by #10465)*: On a failed delivery the system MUST return the local
  repository state to its pre-attempt commit, so that a later attempt re-derives the delivery and
  does not silently do nothing.
- **FR-003** *(satisfied by #10465)*: The system MUST distinguish push rejections by cause, at
  least a policy or hook denial and a non-fast-forward, and MUST surface the distinction in the
  raised error.
- **FR-004**: The system MUST retry a transient failure automatically, a bounded number of times. It
  MUST NOT automatically retry a credential, permission or branch-protection failure. A failure
  after the remote accepted the push counts as transient.
- **FR-005**: The system MUST keep, per repository and destination branch, an ordered queue of
  merges awaiting delivery. A later merge MUST be appended and MUST NOT displace an earlier one. An
  entry MUST hold the merge inputs, the remote source branch and the source commit that Infrahub
  imported, and never the merge result.
- **FR-005a**: The system MUST record a merge in the queue before the first delivery attempt for it
  starts, and before the merge follow-up consults the regeneration barrier.
- **FR-006**: The system MUST NOT force-push to the remote under any circumstance.

#### Recovery

- **FR-007**: Users with write access to a repository MUST be able to trigger a delivery retry. The
  retry replays every pending merge in order against the current remote state and delivers them in
  a single push. The first attempt of a merge and a retry MUST be the same operation.
- **FR-008**: Users with write access to a repository MUST be able to abandon its pending queue. The
  request MUST name the queue state it abandons, and the system MUST refuse it when the queue
  changed. The system MUST durably record what was abandoned, by whom and when.
- **FR-009**: The system MUST NOT clear a pending delivery by any path that does not produce that
  record. The generic repository create and update operations MUST NOT be able to write the delivery
  state.
- **FR-010**: The system MUST NOT block a branch merge because a repository's delivery is
  outstanding.
- **FR-011**: The system MUST NOT delete a remote branch while a delivery that references its commit
  is outstanding.
- **FR-012**: When a push succeeded but recording it did not, the system MUST clear the pending
  queue by observing that the remote already contains the merges, and never by replaying them.

#### Deferred regeneration

- **FR-013**: The system MUST hold the regeneration requests for definitions owned by a repository
  with a pending delivery, partitioned by the repository that owns each definition. It MUST dispatch
  the rest of the selection normally.
- **FR-014**: The system MUST persist held work as identifiers only: definition identifiers, without
  member or target narrowing. A long recovery then cannot dispatch a stale target set.
- **FR-015**: When the pending queue of a repository clears, by delivery or by abandonment, the
  system MUST dispatch exactly one release for that repository, covering the work it held. A failure
  between the dispatch and the clear MAY repeat the release. It MUST NOT drop it.
- **FR-016**: A deferred regeneration MUST always reach a release. No path may clear the held work
  without dispatching it. An unresolvable held set MUST widen to full branch regeneration and MUST
  NOT be skipped. Every dispatch on the merge follow-up path, a release included, MUST pass through
  the barrier.
- **FR-017**: The coalesced recompute path MUST consult the same barrier for transform-based
  computed attributes, so that a transform never runs on the merge follow-up path against a
  repository with a pending delivery.

#### Visibility

- **FR-018**: The system MUST report the cause and the required action for a failed delivery on the
  repository itself, with the remote's message verbatim. Worker logs and orchestrator access MUST NOT
  be necessary.
- **FR-019**: The delivery state MUST NOT appear in a branch diff or a proposed change, and MUST NOT
  be able to produce a merge conflict.

#### Interaction with history rewrites

- **FR-020** *(IFC-3210 PRD FR-015)*: When a queued source commit is no longer reachable from its
  remote branch, the system MUST mark the delivery unreplayable, with a named cause that
  distinguishes it from every other delivery failure. It MUST NOT push that commit. The system MUST
  detect this no later than the next delivery attempt.
- **FR-021** *(IFC-3210 PRD FR-016)*: When a history rewrite of the remote destination discards a
  commit that the system delivered, the system MUST record a reverted delivery, as a condition
  distinct from FR-020.
- **FR-022**: When the history of the remote destination no longer contains the commit recorded for
  it, the system MUST NOT replay onto it. The delivery MUST be marked unreplayable, with a named
  cause.

#### Consistency with the import

- **FR-023**: While a delivery is pending for a branch, the system MUST NOT import that branch from
  the remote by any other path. When a delivery merges remote commits that the system has not
  imported, the system MUST import the delivered commit before it records it.
- **FR-024**: When a queue is abandoned, the system MUST return the repository-owned objects on the
  destination branch to the content of the commit recorded for that branch, before it releases the
  held regeneration.

#### Location and side effects of the state

- **FR-025**: The system MUST read and write the delivery state only on the branch that is the
  destination of the delivery. A branch that sees an inherited copy of that state MUST NOT act on
  it, and the repository view MUST NOT present the copy as current.
- **FR-026**: A write of delivery state by the system MUST NOT start the automations that a direct
  user edit of the repository starts.

### Key Entities *(include if feature involves data)*

- **`CoreRepository`**: gains the delivery state, as branch-local attributes that the system writes
  on Infrahub's default branch. Branch-local makes each value invisible to branch diffs and proposed
  changes, and never a merge conflict. This is the pattern the recorded commit, the synchronisation
  status and the internal status already use. Users can read the state. Only the system writes it.
  The state has these parts:
  - **Delivery status**: names the required action. Nothing pending, pending (an attempt runs or an
    automatic retry waits), or action required.
  - **Failure cause**: why the last attempt failed. At least remote unreachable, credentials,
    permission or branch protection, replay conflict, source commit no longer on the remote,
    destination history rewritten, import failed, and unclassified.
  - **Error message**: the remote's message, verbatim.
  - **Delivery queue**: the ordered entries. Each entry names the remote source branch, the source
    commit, the Infrahub branch it came from and the time of the merge. The queue carries a version
    that an abandonment names.
  - **Held regeneration set**: identifiers only. Artifact definitions, generator definitions, and
    Python-transform computed attributes.
  - **Abandonment record**: the abandoned entries, the user and the time of the last abandonment.
    Earlier records stay readable through the temporal history of the node.
  - **Last delivered commit**, and the **reverted delivery** record of FR-021.
- **`CoreReadOnlyRepository`**: unaffected. It never delivers content to a remote.
- **Repository operational status**: unchanged. It describes whether the remote is reachable, which
  is a different phase.
- **Repository synchronisation status**: unchanged. Delivery failures are not folded into it, so
  INFP-671 can redefine it to mean "the last commit imported successfully" independently.
- **Branch**: unaffected. A merge stays permitted while a delivery is outstanding.

No new node kind is introduced. A related record would be visible in diffs, would need its own
permission model, and would work against the approach of INFP-671, which reads per-branch repository
state from the repository node.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After any push that the remote rejects, the commit Infrahub reports for that branch
  equals the commit on the remote. No state exists in which Infrahub reports a commit the remote does
  not have.
- **SC-002**: The cause of a delivery failure and the required action can both be read from the
  repository view alone, with no access to worker logs or the orchestrator. Baseline today: both are
  necessary, at about two hours of Solution Architecture time per incident.
- **SC-003**: A delivery failure caused by a transient network fault needs zero user actions. A
  failure caused by a permission or branch-protection problem needs exactly one user action after
  the cause is fixed, however many merges accumulated while it failed.
- **SC-004**: A recovery produces exactly one regeneration release per repository. It covers only
  the definitions that the repository owns and that the affected merges touched. No artifact,
  generator or transform-based computed attribute on the merge follow-up path runs against a commit
  other than the one that is finally on the remote. A failure between the dispatch and the clear can
  repeat a release, and it can never drop one.
- **SC-005**: No deferred regeneration is ever dropped. The clear of the held work and its dispatch
  are inseparable, on the abandonment path and on the delivery path.
- **SC-006**: No pending delivery is ever cleared without a durable record of what was abandoned, by
  whom and when.
- **SC-007**: No delivery ever pushes a commit that a history rewrite removed from the remote.

## Assumptions

- Infrahub never resolves a Git conflict. A delivery never introduces file content that did not
  already exist on one side.
- Losing the ability to re-derive content at a superseded commit is acceptable.
- Delivery failures resolve on human timescales, days and not minutes. A time-bounded automatic
  retry is therefore not a viable primary recovery mechanism, only a cure for blips.
- The number of definitions that a single merge touches is small, so a held set stays small however
  long an outage lasts.
- Jinja2 computed attributes, display labels and human-friendly ids render from the schema in the
  graph and do not depend on repository delivery state.
- A repository import is desired-state: it deletes the repository-owned objects that are not in the
  imported commit. FR-023 and FR-024 depend on this.
- A branch-local attribute isolates writes, diffs and merges, but a read on a branch falls back to
  the branch it forked from. The sibling spec documents this in its data model. FR-025 depends on
  it.
- A branch merge always targets Infrahub's default branch, so the default branch is the only
  delivery destination.

## Dependencies

- **PR #10465 (IFC-1449)**, on `develop` as `7d1bab3d1`. It delivers the push-before-record order,
  the worktree reset, the push-rejection wording and the Gogs pre-receive hook helpers that this
  work extends.
- **PR #10542 (IFC-3105)**, on `develop`. It changes how a repository object resolves its trunk and
  where the write probe runs.
- **IFC-3018** is done, so the coalesced pass already holds the Python-transform family. FR-017 is
  an integration point that exists, not one that waits.
- **IFC-3002** is in progress. Whoever works there must know that the coalesced pass gains a barrier
  consultation for repository-owned transforms, and that this work adopts its widen-never-skip
  invariant as FR-016.
- **IFC-3210** is recommended first. FR-021 needs its rewrite detection. FR-020 and FR-022 do not:
  they are checks of the replay and ship with it.

## Out of Scope

- History-rewrite detection and reconciliation itself. IFC-3210 covers it.
- Pausing synchronisation, and pinning a repository to an earlier commit (INFP-672).
- The per-branch status list, the commit log, the upstream-versus-imported comparison, and the new
  meaning of the synchronisation status (INFP-671 and INFP-557).
- Gating a merge on the import state of a branch, a separate and genuinely unsafe condition, for a
  later INFP-670 slice.
- Bringing Python-transform computed attributes to parity with the coalesced families (IFC-3002).
  This work consumes that outcome and does not deliver it.
- Unifying the generator and artifact regeneration path with the coalesced recompute path. The
  barrier is consulted by both, and they stay separate.
- Dead-worker concurrency-slot recovery (IFC-2912) and scheduled-task recreation.
- A pull-request-based delivery mode for protected remotes.
- Delivering a replayable prefix of an unreplayable queue. See decision 1 below.
- Deleting, after the queue clears, a remote branch whose deletion this work refused.
- Decomposing the Git modules as an end in itself (INFP-546). New components follow the
  component-design rule. Existing code is not refactored opportunistically.

## Decisions Taken During Specification

These were settled without asking. Two of them answer the open questions of the PRD and need
confirmation from the PRD owner.

1. **PRD open question: is abandonment the only exit from an unreplayable queue?** Yes, in this
   epic. Delivering the replayable prefix needs reasoning about which later entries depend on an
   abandoned one, and a partial abandonment would need its own record shape. The remote source
   branches stay on the remote while a delivery is pending (FR-011), so a user can still deliver a
   prefix by hand in Git. A conflicting queue needs the remote destination to receive a conflicting
   change during an outage, which is rare. **To confirm with Patrick Ogenstad.**
2. **PRD open question: the user-facing label of the delivery status.** The provisional label is
   "Push to remote". The attribute names do not carry the label, so INFP-671 can change the label
   later without a schema migration. **To settle with the owner of INFP-671.**
3. **An abandonment covers the whole queue as the user saw it.** It names the queue version. The PRD
   says the abandonment takes "the pending delivery it is abandoning as an argument so it cannot be
   invoked blindly". A version gives that guarantee for a queue of any length.
4. **FR-020 and FR-021 keep the meaning of IFC-3210 PRD FR-015 and FR-016**, renumbered so that they
   cannot collide with this PRD's own FR-015 and FR-016. FR-020 is narrowed in one way: the system
   detects an orphaned source commit at the next delivery attempt, which is where the safety matters.
   An earlier mark from the synchronisation path is not required.
5. **FR-005a is added.** The PRD states it as an implementation decision: "Delivery state is recorded
   before the delivery workflow is submitted, which makes the barrier race-free". It is a
   requirement in fact, because without it the barrier can see an empty queue for a merge whose
   delivery has not started.
6. **FR-022 is added.** It carries IFC-3210's FR-005b, "the system MUST NOT push a commit the remote
   has already discarded", onto the replay. A source branch forked from a discarded trunk carries the
   discarded commits. Replaying it onto the rewritten trunk and pushing would restore them.
7. **FR-023 is added.** The PRD's edge case "the remote destination advanced" stops at the replay.
   Two gaps follow from it. First, a synchronisation that imports the advanced remote head during the
   outage deletes the merged repository objects that are not delivered yet, because the import is
   desired-state. Second, a delivery that merges remote commits and records the result without an
   import leaves the graph without those commits' objects. Nothing would ever import them, because
   the local and remote clones then agree.
8. **FR-024 is added.** After an abandonment, the graph holds repository objects from the abandoned
   merges that the recorded commit does not contain. The release would then run those definitions
   against files that do not have them. Converging the objects to the recorded commit before the
   release keeps SC-004 true.
9. **FR-025 is added.** It turns the PRD's "branch-local" into a testable rule. Because a branch read
   falls back to its origin branch, a new branch sees a frozen copy of the default branch's delivery
   state. Without the rule, the view of that branch would show "action required" for ever.
10. **FR-026 is added.** The PRD's further notes say that "delivery bookkeeping writes should carry a
    non-live mutation origin per 0016". This states the observable outcome instead of the mechanism.
11. **The delivery state lives on `CoreRepository` only**, not on the generic. A read-only repository
    never delivers, so the attributes would be dead on that kind. The PRD names "CoreRepository /
    CoreGenericRepository" and leaves the choice open.
