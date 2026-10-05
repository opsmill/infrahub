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
| **Merge follow-up path** | The regeneration that a merge starts itself: the post-merge dispatcher of generators and artifacts, the coalesced recompute and its chained levels, and the schema-scoped recompute that a schema-changing merge starts. |

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
a branch that is synchronised with Git and that changes a repository file. Read the repository on
the default branch. It must show one pending delivery, the status "action required", the cause
"permission or branch protection" and the remote's rejection message.

**Acceptance Scenarios**:

1. **Given** a read-write repository whose remote rejects pushes to its default branch, **When** a
   branch synchronised with Git and carrying repository changes merges, **Then** the repository
   reports one pending delivery for that merge, with the status "action required".
2. **Given** the same repository, **When** a user reads its delivery state, **Then** the state
   carries the cause and the remote's rejection message verbatim, with credentials removed.
3. **Given** the same repository, **When** a user reads its commit on the default branch, **Then**
   the commit is unchanged, and the remote has it.
4. **Given** a merge whose first delivery attempt succeeds, **When** a user reads the repository,
   **Then** it reports nothing pending and no error.
5. **Given** a pending delivery, **When** a user views the repository from a branch that is not the
   default branch, **Then** the view shows the current delivery state of the default branch, and
   never a stale copy that the branch inherited when it was created.
6. **Given** a pending delivery, **When** a user reads the required action, **Then** it also says
   that imports from the remote default branch are paused until the pending pushes clear.
7. **Given** a merge whose branch changed only data and no repository file, **When** it merges,
   **Then** no delivery is queued for it.

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
   **Then** the replay merges onto the fetched remote head, no force-push happens, the delivered
   commit is recorded, and the repository objects of that commit are imported.
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

While a repository has a pending delivery, the regeneration that a merge starts for the definitions
this repository owns waits. When the queue clears, the held work runs once, against the commit that
is then on the remote. The definitions of other repositories regenerate as usual.

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
   release for X runs, against the delivered commit. It covers every held definition.
3. **Given** a delivery that completes before the merge follow-up runs, **When** the follow-up runs,
   **Then** it dispatches normally, holds nothing, and no release runs.
4. **Given** a held definition that a user deletes before the release, **When** the release runs,
   **Then** it widens to full regeneration of that repository's definitions instead of skipping the
   gap.
5. **Given** pending deliveries on two repositories, **When** each queue clears, **Then** each
   repository releases its own held work, independently.
6. **Given** a Python-transform computed attribute whose transform belongs to X, **When** the
   coalesced recompute of a merge runs, or the schema-scoped recompute of a schema-changing merge
   runs, **Then** the recompute of that attribute is held. Jinja2 computed attributes, display
   labels and human-friendly ids are never held.
7. **Given** held work for X, **When** a user abandons the queue of X, **Then** the release still
   runs, exactly once.
8. **Given** a merge whose first delivery attempt succeeds within the short hold window, **When** the
   held work is released, **Then** it dispatches the same targets, members and node ids that the
   merge would have dispatched with no pending delivery.

---

### User Story 4 - Transient faults heal, policy faults stop at once (Priority: P2)

A network blip during a push resolves without anyone. A worker that dies during a delivery does not
leave it pending for ever. A missing permission or a branch protection does not retry for an hour.
The repository says at once what to fix.

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
5. **Given** a delivery attempt lost to a worker restart, **When** the next synchronisation cycle
   runs after the attempt went stale, **Then** a new attempt starts with no user action, and a user
   can also retry at once.
6. **Given** a push to a remote that stops answering, **When** the bound of the Git command expires,
   **Then** the attempt fails as transient and does not hang.

---

### User Story 5 - Abandon an undeliverable change, with a record (Priority: P2)

Sometimes the queue cannot be delivered. For example, the remote default branch received a change
that conflicts with a pending merge. The user can resolve the conflict on the remote and retry. Or a
user with write access abandons the queue on purpose. The repository returns to a working state, and
the system records what was dropped, by whom and when.

**Why this priority**: Without it, a stuck repository stays stuck for ever. It ships with the MVP,
because the queue must have an exit from the first day.

**Independent Test**: Make a pending merge conflict with a change pushed directly to the remote.
Trigger a retry. It must fail at that merge and push nothing. Abandon the queue. The queue must be
empty, the record must name the merges, the user and the time, and the held regeneration must run.

**Acceptance Scenarios**:

1. **Given** a queue whose replay conflicts with the remote head, **When** a retry runs, **Then** it
   stops at that merge, pushes nothing, and sets the status "action required" with the cause "replay
   conflict". The required actions are: merge the source branch on the remote by hand and retry, or
   abandon.
2. **Given** a conflicting entry that a user merged by hand on the remote, **When** a retry runs,
   **Then** the system sees that the remote holds that entry and clears it with no replay.
3. **Given** a pending queue, **When** a user with write access abandons it and names the queue
   state that the user saw, **Then** the queue clears, a record of the abandoned merges, the user
   and the time is stored, and the held regeneration is released.
4. **Given** a queue that changed after the user read it, **When** that user abandons it, **Then**
   the system refuses the request as stale.
5. **Given** an abandonment, **When** it completes, **Then** the repository says that the default
   branch can hold repository objects that the recorded commit lacks, and, when an owed import was
   dropped, that it can lack objects that the commit holds. It names the commit and offers the
   existing reimport of the current commit.
6. **Given** an abandonment, **When** it completes, **Then** nothing was removed from the remote,
   and the remote source branches still exist.
7. **Given** any repository content, **When** a user abandons, **Then** the abandonment does not fail
   because of that content.
8. **Given** any path other than a delivery or an abandonment, including the generic repository
   update, **When** it runs, **Then** it cannot change or clear the delivery state.

---

### User Story 6 - A delivery keeps the commits it needs (Priority: P2)

A pending delivery replays merge inputs from the remote. The remote branch that holds a source commit
must stay on the remote until the delivery clears. Other merges continue while one repository's
remote is broken.

**Why this priority**: If the source branch is deleted, the source commit can be garbage-collected
and the delivery becomes impossible. With `delete_git_branch_after_merge` enabled this path is
reachable today, on the success path as well, because the deletion and the push are submitted
together.

**Independent Test**: Enable branch deletion after merge. Reject pushes. Merge a branch. The remote
source branch must still exist after the deletion flow ran, and the next synchronisation must not
import it again as a new branch. Lift the rejection and retry. The remote source branch must then be
deleted.

**Acceptance Scenarios**:

1. **Given** a pending delivery whose source is remote branch S, **When** Infrahub would delete S
   from the remote, **Then** it does not delete S, it logs why, and it deletes S once the delivery
   of that entry succeeds.
2. **Given** a pending delivery whose source is remote branch S, **When** the synchronisation runs,
   **Then** it does not import S as a new Infrahub branch.
3. **Given** a pending delivery whose source is S, **When** a user abandons it, **Then** S stays on
   the remote, and the next synchronisation imports it as a new Infrahub branch on every worker.
4. **Given** no pending delivery that references S, **When** Infrahub deletes S, **Then** the
   deletion proceeds as it does today.
5. **Given** a pending delivery on repository X, **When** a user merges another branch, **Then** the
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
  now conflicts. The retry fails at that entry and cannot succeed as it is. Inside Infrahub,
  abandonment is the only exit. Outside Infrahub, a user can merge the source branch on the remote
  by hand, and the next retry clears the entry by observation. See "Decisions Taken During
  Specification".
- **The worker that performed the merge never returns.** Nothing on a worker's disk is
  load-bearing. The queue names merge inputs that are on the remote, so any worker can perform the
  delivery. The next synchronisation cycle starts a new attempt once the lost one is stale.
- **The remote destination advanced between the failure and the retry.** The replay merges onto the
  freshly fetched remote head. No force-push happens. Infrahub records the delivered commit, then
  imports it, with a durable obligation to import that survives a crash.
- **The periodic synchronisation runs while a delivery is pending.** It does not advance the
  destination branch of that repository. A desired-state import of the remote head would delete
  the merged repository objects that are not delivered yet. The delivery imports the remote commits
  instead. Other branches synchronise as usual.
- **A worker clones the repository while a delivery is pending.** The seed import after a fresh
  clone skips the default branch, for the same reason.
- **The remote source branch would be deleted after the merge.** Refused while a delivery that
  references it is outstanding, so the commit needed for the replay cannot be garbage-collected. The
  synchronisation does not import that branch again as a new Infrahub branch while it is kept. The
  delivery deletes it once the entry is delivered. An abandonment keeps it on the remote, and the
  next synchronisation imports it again as a new Infrahub branch, so the user can merge it again.
- **The delivery succeeds but the recording fails.** The destination worktree is reset behind the
  remote, and the queue stays. The next attempt sees that the remote already holds the merges. It
  records the commit and clears the queue by observation, never by replay.
- **The import fails after a successful push.** The commit is recorded, and the obligation to
  import stays. A database or connection fault gets the cause "import interrupted" and retries. A
  content fault stops with the cause "import failed" until the content is fixed on the remote and a
  retry runs.
- **A merge lands during the import of a delivered commit.** The desired-state import can delete the
  new merge's repository objects, which the delivered commit does not hold yet. The obligation to
  import then stays, and the next attempt imports a commit that holds them. Their object ids can
  change. A merge racing a synchronisation import has the same exposure today.
- **A branch is left ahead of its remote.** The reset on failure prevents the once-a-minute "update
  detected but commit unchanged" loop.
- **The delivery completes before the merge follow-up runs.** The barrier sees an empty queue and
  dispatches as usual. It holds nothing, and no release runs. Nothing regenerates twice.
- **The merge cannot record its queue entry.** The merge retries the record a bounded number of
  times. If every try fails, the merge follow-up sees no pending delivery. It regenerates the work of
  that repository against the commit recorded before the merge. The delivery records the entry
  before its first attempt. After the delivery, the release regenerates every definition of that
  repository against the delivered commit. Work runs twice, and no stale result stays.
- **Several repositories fail delivery after the same merge.** Each keeps its own queue and its own
  held set, and each releases independently.
- **A held definition is deleted before the release.** It is skipped, and its absence widens the
  release to full regeneration of that repository's definitions instead of leaving a silent gap.
- **A failure between the release dispatch and the clear of the held set.** The release can run a
  second time. It can never be lost. Over-execution is the accepted direction.
- **The same definition is held again during a release.** A hold that arrives after the release
  started survives the clear, so the definition is released again later.
- **A branch forked from the default branch while a delivery is pending.** A branch-local value is
  read through the branch it forked from, so the new branch sees a copy of the delivery state as it
  was at the fork. The product never acts on that copy and never presents it as current. The new
  branch's graph also holds the pending merges' objects, while its Git branch does not hold their
  files. A later import of that branch deletes them on the branch. The reimport of the current
  commit refuses on every branch while a delivery is pending. A synchronisation import of such a
  branch is a known limitation, documented.
- **A git-synced branch that changed only data.** It carries no repository content. When the branch
  never recorded a commit of its own, or its own commit equals the default branch's commit at its
  fork point, no entry is queued.
- **A staging repository.** It is never queued. It is delivered when its proposed change merges, as
  today.
- **A worker whose clone of the repository has no remote.** Every repository has a location, so
  such a clone is broken. A delivery attempt on that worker fails. It records no commit, and every
  entry stays in the queue. The failure is unclassified and is not retried automatically. Its
  message names the broken clone. A retry on another worker, or after a fresh clone, can deliver
  the queue.
- **An abandonment while a delivery attempt runs.** The two never interleave. The abandonment waits
  for the attempt. The attempt removes the entries it delivered before it lets the abandonment in,
  so the version has moved and the abandonment is refused as stale. The release that follows a
  delivery or an abandonment runs under a lease, so no other run releases the same work again.
- **An abandonment after the remote accepted a push that Infrahub did not record.** Abandonment never
  removes content from the remote. The remote keeps the merged content, and the next synchronisation
  imports it.
- **An abandonment of a merge whose repository objects stay in the graph.** The import never deletes
  artifact definitions, and the recorded commit lacks the abandoned merges' files. The released
  regeneration can then fail for those definitions. The repository says so and offers the reimport
  of the current commit.
- **A late first attempt of an abandoned merge.** A merge flow that starts after its entry was
  abandoned does not put the entry back.
- **A direct edit, or a live event of another writer, while a delivery is pending.** It runs
  transforms against the recorded commit, which is the commit on the remote. It is not held. Only
  the merge follow-up path is held.
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
the IFC-3210 PRD, which that epic defers to this one. FR-005a, FR-005b and FR-022 to FR-027 are
added here. "Decisions Taken During Specification" says why each one is added.

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
  after the remote accepted the push counts as transient. Every Git command of a delivery attempt,
  outside the repository import, MUST be bounded in time, so that a remote that stops answering
  produces a transient failure. FR-027 covers the import.
- **FR-005**: The system MUST keep, per repository and destination branch, an ordered queue of
  merges awaiting delivery. A later merge MUST be appended and MUST NOT displace an earlier one. An
  entry MUST hold the merge inputs, the remote source branch and the source commit that Infrahub
  imported, and never the merge result. A merge that carries no repository content and a staging
  repository MUST NOT be queued. A worker whose clone of the repository has no remote MUST NOT
  record a commit, and MUST NOT remove an entry from the queue.
- **FR-005a**: The system MUST record a merge in the queue before the first delivery attempt for it
  starts, and before the merge follow-up consults the regeneration barrier. When the record fails,
  the system MUST retry it a bounded number of times. If every retry fails, the delivery MUST record
  the entry before its first attempt, and the regeneration that the merge follow-up dispatched for
  that repository without a hold MUST run again after the delivery. A failure to record one
  repository's entry MUST NOT stop the delivery of any repository.
- **FR-005b**: An entry that left the queue MUST NOT come back.
- **FR-006**: The system MUST NOT force-push to the remote under any circumstance.

#### Recovery

- **FR-007**: Users with write access to a repository MUST be able to trigger a delivery retry. The
  retry replays every pending merge in order against the current remote state and delivers them in
  a single push. The first attempt of a merge and a retry MUST be the same operation.
- **FR-008**: Users with write access to a repository MUST be able to abandon its pending queue. The
  request MUST name the queue state it abandons, and the system MUST refuse it when the queue
  changed. The system MUST durably record what was abandoned, by whom and when.
- **FR-009**: The system MUST NOT remove an undelivered entry from the queue by any path other than
  an abandonment that produces that record. A delivery MUST remove an entry only when the remote
  holds it. The generic repository create and update operations MUST NOT be able to write the
  delivery state.
- **FR-010**: The system MUST NOT block a branch merge because a repository's delivery is
  outstanding.
- **FR-011**: The system MUST NOT delete a remote branch while a delivery that references its commit
  is outstanding. When the system refused a deletion that was requested, it MUST delete the branch
  once the referencing entry is delivered, and MUST NOT delete it when the entry is abandoned. While
  the branch is kept, the system MUST NOT import it as a new Infrahub branch.
- **FR-012**: When a push succeeded but recording it did not, the system MUST clear the pending
  queue by observing that the remote already contains the merges, and never by replaying them.

#### Deferred regeneration

- **FR-013**: The system MUST hold the regeneration requests for definitions owned by a repository
  with a pending delivery, partitioned by the repository that owns each definition. It MUST dispatch
  the rest of the selection normally.
- **FR-014**: The system MUST persist held work as identifiers only: definition identifiers, without
  member or target narrowing. A long recovery then cannot dispatch a stale target set. A narrowed
  selection MAY be kept outside the persisted state for a short, bounded time, and used only by a
  release inside that time.
- **FR-015**: When the pending queue of a repository clears, by delivery or by abandonment, the
  system MUST dispatch exactly one release for that repository, covering the work it held. A failure
  between the dispatch and the clear MAY repeat the release. It MUST NOT drop it. A hold recorded
  after a release started MUST survive that release's clear.
- **FR-016**: A deferred regeneration MUST always reach a release. No path may clear the held work
  without dispatching it. An unresolvable held set MUST widen to full regeneration of the owning
  repository's definitions and MUST NOT be skipped. Every dispatch on the merge follow-up path, a
  release included, MUST pass through the barrier. When the barrier cannot read the delivery state,
  it MUST first retry the read a bounded number of times. If every retry fails, it MUST dispatch and
  log at error level, never hold blindly.
- **FR-017**: The coalesced recompute and the schema-scoped recompute MUST consult the same barrier
  for transform-based computed attributes, so that a transform never runs on the merge follow-up
  path against a repository with a pending delivery. At those two consultation points the barrier
  MAY also hold runs on the default branch that no merge started, such as a schema load or a
  manual recompute; such a run MUST still reach a release. Recomputes that live events of other
  writers start, and webhooks that run a transform, are not held.

#### Visibility

- **FR-018**: The system MUST report the cause and the required action for a failed delivery on the
  repository itself, with the remote's own message verbatim and free of credentials. Worker logs and
  orchestrator access MUST NOT be necessary.
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
  the remote by any other path: the synchronisation, the seed import after a fresh clone, and the
  reimport of the current commit. When a delivery records a commit that holds remote commits the
  system has not imported, the system MUST keep a durable obligation to import that commit until an
  import of it succeeds.
- **FR-024**: An abandonment MUST NOT fail because of repository content. After an abandonment, the
  repository MUST say that the default branch can hold repository objects that the recorded commit
  lacks, and MUST offer the existing reimport of the current commit.

#### Location, liveness and side effects of the state

- **FR-025**: The system MUST read and write the delivery state only on the branch that is the
  destination of the delivery. A branch that sees an inherited copy of that state MUST NOT act on
  it, and the repository view MUST NOT present the copy as current.
- **FR-026**: A write of delivery state by the system MUST NOT start the automations that a direct
  user edit of the repository starts.
- **FR-027**: A pending delivery MUST NOT stay pending without a running or scheduled attempt. When
  an attempt is lost, the system MUST start a new one within a bounded time, and a user MUST be able
  to retry at once. The same check MUST release held work that waits behind an empty queue.

### Key Entities *(include if feature involves data)*

- **`CoreRepository`**: gains the delivery state, as branch-local attributes that the system writes
  on Infrahub's default branch. Branch-local makes each value invisible to branch diffs and proposed
  changes, and never a merge conflict. This is the pattern the recorded commit, the synchronisation
  status and the internal status already use. Users can read the state. Only the system writes it.
  The state has these parts:
  - **Delivery status**: names the required action. Nothing pending, pending (an attempt runs or an
    automatic retry waits), or action required.
  - **Failure cause**: why the last attempt failed. At least remote unreachable, credentials,
    permission or branch protection, repository not found, certificate, replay conflict, source
    commit no longer on the remote, destination history rewritten, import interrupted, import
    failed, and unclassified.
  - **Error message**: the remote's message, verbatim, with credentials removed.
  - **Delivery queue**: the ordered entries. Each entry names the remote source branch, the source
    commit, the Infrahub branch it came from and the time of the merge. The queue carries a version
    that an abandonment names, the identifiers of recently removed entries, and any owed import.
  - **Delivery progress**: the time of the last progress, the start of the last attempt, and when a
    waiting retry is due.
  - **Held regeneration set**: identifiers only. Artifact definitions, generator definitions, and
    Python-transform computed attributes, each with the sequence number of its last hold, plus the
    leases of the releases in progress.
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

- **SC-001**: After any delivery attempt, Infrahub never reports a commit for the default branch that
  the remote does not have.
- **SC-002**: The cause of a delivery failure and the required action can both be read from the
  repository view alone, with no access to worker logs or the orchestrator. Baseline today: both are
  necessary, at about two hours of Solution Architecture time per incident.
- **SC-003**: A delivery failure caused by a transient network fault, or by a lost worker, needs
  zero user actions. A failure caused by a permission or branch-protection problem needs exactly one
  user action after the cause is fixed, however many merges accumulated while it failed.
- **SC-004**: A recovery produces exactly one regeneration release per repository. It covers only
  the definitions that the repository owns. Outside the widened fallback, it covers only the
  definitions that the affected merges touched. No artifact, generator or transform-based computed
  attribute on the merge follow-up path runs against a commit other than the one that is finally on
  the remote. Two exceptions are logged at error level. First, the barrier cannot read the delivery
  state after a bounded retry. Second, the merge cannot record its queue entry after a bounded retry.
  In the second case, the release after the delivery runs that regeneration again, so no result of
  the earlier commit stays.
  A failure between the dispatch and the clear can repeat a release, and it can never drop one.
- **SC-005**: No deferred regeneration is ever dropped. The clear of the held work and its dispatch
  are inseparable, on the abandonment path and on the delivery path.
- **SC-006**: No pending delivery is ever cleared without a durable record of what was abandoned, by
  whom and when.
- **SC-007**: No delivery ever pushes a commit that a history rewrite removed from the remote.
- **SC-008**: A git-synced merge whose first delivery attempt succeeds within the hold window
  dispatches the same regeneration targets, members and node ids included, as the same merge with no
  barrier.

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
- A repository import deletes the queries, transforms, checks, generator definitions and objects
  that the imported commit lacks. It never deletes artifact definitions or schema. FR-023 and FR-024
  depend on this.
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
- **The Python SDK.** New schema attributes regenerate the SDK protocols, which live in the
  `python_sdk` submodule. That change needs its own SDK PR, shared with IFC-3210.

## Out of Scope

- History-rewrite detection and reconciliation itself. IFC-3210 covers it.
- Pausing synchronisation, and pinning a repository to an earlier commit (INFP-672).
- The per-branch status list, the commit log, the upstream-versus-imported comparison, and the new
  meaning of the synchronisation status (INFP-671 and INFP-557).
- A delivery signal outside the repository page, such as on the proposed change or the repository
  list. INFP-671 owns those surfaces. The delivery runs appear in the repository's task list.
- Gating a merge on the import state of a branch, a separate and genuinely unsafe condition, for a
  later INFP-670 slice.
- Bringing Python-transform computed attributes to parity with the coalesced families (IFC-3002).
  This work consumes that outcome and does not deliver it.
- Unifying the generator and artifact regeneration path with the coalesced recompute path. The
  barrier is consulted by both, and they stay separate.
- Holding recomputes that live events of other writers start, and webhooks that run a transform.
- Dead-worker concurrency-slot recovery (IFC-2912) and scheduled-task recreation.
- A pull-request-based delivery mode for protected remotes.
- Repository type naming (INFP-95).
- Delivering a replayable prefix of an unreplayable queue, or skipping one entry. See decision 1.
- Decomposing the Git modules as an end in itself (INFP-546). New components follow the
  component-design rule. Existing code is not refactored opportunistically.

## Decisions Taken During Specification

These were settled without asking. Three of them need confirmation, and say so.

1. **PRD open question: is abandonment the only exit from an unreplayable queue?** Inside Infrahub,
   yes, in this epic. Outside Infrahub, a user can merge the source branch on the remote by hand,
   and the next retry clears the entry by observation. Delivering a replayable prefix, or skipping
   one entry, needs reasoning about which later entries depend on a dropped one, and a partial
   abandonment would need its own record shape. The cost of whole-queue abandonment is real: every
   later good entry is dropped too, and an Infrahub branch that merged cannot merge again, so
   re-delivery means a manual merge on the remote for each dropped entry. A conflicting queue needs
   the remote destination to receive a conflicting change during an outage, which is rare. **To
   confirm with Patrick Ogenstad, with that cost in view.**
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
   delivery has not started. The record itself can fail. The merge follow-up then sees no pending
   delivery and regenerates against the old commit. So FR-005a also requires a bounded retry, and a
   second run of that regeneration after the delivery. A block of the delivery for that repository
   was rejected: the remote would then never receive the merge.
6. **FR-005b is added.** A merge flow can start after its entry was abandoned. Without the rule, it
   would put the entry back and push it.
7. **FR-022 is added.** It carries IFC-3210's FR-005b, "the system MUST NOT push a commit the remote
   has already discarded", onto the replay. A source branch forked from a discarded trunk carries the
   discarded commits. Replaying it onto the rewritten trunk and pushing would restore them.
8. **FR-023 is added.** The PRD's edge case "the remote destination advanced" stops at the replay.
   Two gaps follow from it. First, an import of the advanced remote head during the outage deletes
   the merged repository objects that are not delivered yet, because the import is desired-state.
   Three paths import: the synchronisation, the seed import after a fresh clone, and the reimport of
   the current commit. Second, a delivery that merges remote commits and records the result without
   an import leaves the graph without those commits' objects. Nothing would ever import them,
   because the local and remote clones then agree. The obligation is durable, and the record comes
   first, because regeneration that the import starts reads the recorded commit.
9. **FR-024 is added, and it is deliberately weak.** An earlier draft re-imported the recorded commit
   inside the abandonment. That is beyond the PRD, and the import cannot do it: it never deletes
   artifact definitions, and it can refuse to delete a transform that an artifact definition needs.
   The only exit must never fail, so the abandonment only clears, records and releases, and the user
   decides on the reimport.
10. **FR-025 is added.** It turns the PRD's "branch-local" into a testable rule. Because a branch read
    falls back to its origin branch, a new branch sees a frozen copy of the default branch's delivery
    state. Without the rule, the view of that branch would show "action required" for ever.
11. **FR-026 is added.** The PRD's further notes say that "delivery bookkeeping writes should carry a
    non-live mutation origin per 0016". This states the observable outcome instead of the mechanism.
12. **FR-027 is added.** A worker restart, a lost workflow submission or a hung push would otherwise
    leave a delivery pending for ever, with its regeneration held, and with no action available to a
    user. SC-003 counts a lost worker as transient.
13. **SC-008 and the second sentence of FR-014 are added.** A merge of a git-synced branch nearly
    always reaches the coalesced recompute before its first delivery attempt completes, so the hold
    is the normal path for such a merge. Without a short-lived narrowed selection, every such merge
    would recompute whole kinds. SC-008 makes that cost measurable.
14. **The merge follow-up path is defined in "Terms".** FR-016 and FR-017 hold the regeneration that a
    merge starts itself. A live event of another writer, such as a generator write in the cascade,
    can still start a per-node recompute of a held repository's transform. It runs against the
    recorded commit, which the remote has. Holding every live path would gate the per-node
    automations on repository state, which is a much larger change.
15. **After an abandonment, a kept source branch comes back as a new Infrahub branch.** The
    abandonment tells every worker to drop its local branch, so the result is the same on every
    worker. The user then has the undelivered content as a branch and can merge it again, which
    softens the cost of decision 1. **To confirm with the product owner**: the alternative is to
    keep the branch on the remote only.
16. **FR-017 accepts a wider hold.** Two consultation points cannot tell a merge-started run from
    another run on the default branch. Holding both delays work only during an outage and never
    drops it. Telling them apart would need a new parameter on four flows.
17. **The delivery state lives on `CoreRepository` only**, not on the generic. A read-only repository
    never delivers, so the attributes would be dead on that kind. The PRD names "CoreRepository /
    CoreGenericRepository" and leaves the choice open.
