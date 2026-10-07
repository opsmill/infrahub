# Feature Specification: Git history-rewrite reconciliation

**Feature Branch**: `history-rewrite-reconciliation-ifc-3210`

**Created**: 2026-09-29

**Status**: Draft

**Input**: Jira epic IFC-3210 "Git history-rewrite reconciliation". Source PRD: Notion page
`992228b83025825990bc011568cc2f4b`, mirrored on Confluence page 896466945. Product card INFP-670.

## Context

A developer rebases a branch that Infrahub tracks and force-pushes it. Infrahub then fails to
synchronise that branch. The error says there are merge conflicts to resolve. No conflict exists.
The branch stays on its old commit for ever, and no recovery path exists in the product.

The failure is not contained to one branch. The synchronisation flow raises on the failed branch
before it sends the worker-convergence broadcast. One developer's rebase therefore stops every
other branch of the same repository from converging across the worker pool. A read-only
repository absorbs the same event in silence and reports nothing at all.

Rewriting history is ordinary Git practice. Infrahub is the only participant that cannot cope
with it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A rewritten branch reconciles itself (Priority: P1)

A developer rebases a tracked branch and force-pushes it. On the next synchronisation cycle,
Infrahub sees that the remote head no longer descends from the commit it imported. It resets the
branch worktree to the remote head, converges the other workers, re-imports the branch objects,
and records what happened. The developer does nothing. No error is raised.

**Why this priority**: This is the reported failure. It removes the stuck branch, the wrong
"conflict" message and the missing recovery path in one slice.

**Independent Test**: Push a branch to a live remote, let Infrahub import it, rewrite the branch
history on the remote, force-push, and run one synchronisation cycle. The branch commit in the
graph must match the new remote head, the imported objects must match the rewritten tree, and the
repository must report healthy.

**Acceptance Scenarios**:

1. **Given** a synchronised non-default branch whose remote history was rewritten, **When** the
   next synchronisation cycle runs, **Then** Infrahub classifies the branch as diverged and not as
   conflicted.
2. **Given** the same branch, **When** the cycle completes, **Then** the branch worktree is at the
   remote head, the branch objects are re-imported, and the repository reports healthy.
3. **Given** the same branch, **When** the cycle completes, **Then** Infrahub records the previous
   commit, the new commit, the reconciliation time and a count incremented by one.
4. **Given** the same branch, **When** the cycle completes, **Then** no error is raised and no
   operator action is needed.
5. **Given** a tracked branch whose remote head is a descendant of the imported commit, **When**
   the cycle runs, **Then** the branch fast-forwards as it does today and no record is written.

---

### User Story 2 - Every worker converges, including one that heard nothing (Priority: P1)

A worker was offline, restarting or newly added while a branch was reconciled. The first time that
worker advances the branch worktree, it detects the divergence on its own clone and resets to the
remote head. It does not wait to be told.

**Why this priority**: Without this, convergence depends on who was listening at the time. The
broadcast is a pre-warm, not the correctness mechanism. This slice makes the property true by
construction.

**Independent Test**: Reconcile a branch on one worker while a second worker receives no
broadcast. Make the second worker advance that branch worktree. Assert that it ends on the remote
head, writes no rewrite record and emits no signal.

**Acceptance Scenarios**:

1. **Given** a branch reconciled while one worker was unavailable, **When** that worker later runs
   any operation that advances the branch worktree, **Then** it detects the divergence itself and
   resets to the remote head.
2. **Given** the same worker, **When** it resets, **Then** it writes no rewrite record and emits
   no signal. It may write the branch commit, because it reaches the reset through a path that
   updates it. That value is the one the reconciling worker already stored.
3. **Given** the same worker, **When** it resets, **Then** the operation it was asked to run
   completes successfully.
4. **Given** a worker that has never seen the repository, **When** it first touches it, **Then** it
   clones from the remote and needs no reset.

---

### User Story 3 - One rewritten branch never blocks the others (Priority: P1)

A repository has two tracked branches. One of them fails during a synchronisation cycle. The other
branch still converges across the worker pool.

**Why this priority**: This is the outage half of the reported bug. A single developer's rebase
must not be a repository-wide event.

**Independent Test**: Make one branch of a repository fail during a cycle. Assert that the
convergence broadcast for the healthy branch is still sent, and that a second worker converges on
it.

**Acceptance Scenarios**:

1. **Given** a repository with two tracked branches, one of which fails during the cycle, **When**
   the cycle runs, **Then** the broadcast for the healthy branch is still sent.
2. **Given** a cycle that reconciled several branches, **When** the cycle completes, **Then** the
   broadcast covers every branch the cycle reconciled, and not only the trunk.
3. **Given** a cycle with a failing branch, **When** the cycle raises for that branch, **Then** the
   broadcast was already sent before the raise.

---

### User Story 4 - A rewritten trunk is reconciled and announced (Priority: P2)

The configured default branch of a repository has its history rewritten. Infrahub reconciles it in
exactly the same way as any other branch. It also emits at most one outbound signal, because on a
synchronised repository a rewritten trunk is a security remediation, a migration or a mistake.

**Why this priority**: The trunk carries the largest blast radius, but the reconciliation logic is
the same as P1. Only the signal is new. It depends on P1 landing first.

**Independent Test**: Rewrite the trunk of a tracked repository on a live remote. Run several
synchronisation cycles. Assert at most one record, at most one signal, never a second of either,
and a healthy repository. SC-002 says why the guarantee is one-sided.

**Acceptance Scenarios**:

1. **Given** a repository whose configured default branch had its history rewritten, **When** the
   next cycle runs, **Then** the same reconciliation happens as for any other branch.
2. **Given** the same repository, **When** several cycles elapse, **Then** at most one record is
   written and at most one signal is emitted, and never more than one.
3. **Given** a rewrite of a branch that is not the configured default branch, **When** the cycle
   runs, **Then** no signal is emitted.
4. **Given** an emitted signal, **When** a consumer is subscribed to it, **Then** the consumer
   receives that signal once and never twice.

---

### User Story 5 - A read-only repository records the lineage break (Priority: P2)

A read-only repository tracks a ref. The ref still has the same name, but it now resolves to a
commit that does not descend from the imported one. Infrahub imports the new commit as it does
today and records the lineage break. It performs no reset.

**Why this priority**: Read-only is today the only repository type that reports nothing at all.
It shares the consequence with the others but not the failure, so it can ship after P1.

**Independent Test**: Force-push a **branch** that a read-only repository tracks, on a live remote.
Update the commit. Assert that the import happened, that the record was written and that no reset
ran.

A moved **tag** cannot be used for this scenario, and the reason is worse than it first looks.
Both read-only fetch paths run `--prune --tags --prune-tags` without `--force`. Against a
force-moved tag git does not quietly skip it: it rejects the update with
`! [rejected] <tag> -> <tag> (would clobber existing tag)` **and exits 1**. `InfrahubRepositoryBase.fetch`
turns that into a `GitCommandError` and raises, so the repository goes to an error status on every
cycle, and `InfrahubReadOnlyRepository.update_latest_commit` fails outright. The local tag never
moves, so no lineage break is ever observed either.

IFC-2874 fixes that missing flag and is out of scope here, so the scenario uses a force-pushed
branch.

**Acceptance Scenarios**:

1. **Given** a read-only repository whose tracked ref is unchanged but resolves to a commit that
   does not descend from the imported commit, **When** the commit is updated, **Then** the import
   proceeds as it does today.
2. **Given** the same repository, **When** the commit is updated, **Then** the record is written and
   no reset is performed.
3. **Given** a read-only repository whose tracked ref was itself changed, **When** the commit is
   updated, **Then** no record is written.

---

### User Story 6 - A deliberate change of target is not a rewrite (Priority: P2)

An operator re-points a read-only repository to a new tag, or edits a repository's configured
default branch. Lineage breaks, but nothing was rewritten. Infrahub reconciles the repository and
reports nothing.

**Why this priority**: Without this, routine work produces noise. The rewrite record loses its
meaning if it also fires on deliberate re-targeting.

**Independent Test**: Change the tracked ref of a read-only repository to a different tag. Change
the configured default branch of a read-write repository. Assert that no record is written in
either case.

**Acceptance Scenarios**:

1. **Given** a read-only repository whose tracked ref is changed to a different tag, **When** the
   commit is updated, **Then** no record is written.
2. **Given** a read-write repository whose configured default branch is edited, **When** the next
   cycle runs, **Then** no record is written.

---

### Edge Cases

- **A worker offline during the reconciliation.** It converges on first contact under FR-005. The
  broadcast it missed carried no correctness weight.
- **A worker that has never seen the repository.** It clones from the remote and is correct by
  construction.
- **Infrahub's own unpushed merge commit.** The merge path pushes the merge commit before it
  records it and resets the destination worktree when either step fails, so this state does not
  arise and no guard against it is needed.
- **A rewrite of a branch that is not the trunk notifies nobody.** It writes a record and emits no
  signal. This is deliberate. By the time the record is written the branch is reset, the workers
  have converged and the re-import has run, so nothing is outstanding and there is no action to
  take.
- **Repeated rewrites of the same branch.** The record keeps the last event only. The count shows
  that the record is not the whole story. A full history is deliberately not kept. A branch
  rewritten four times therefore answers "what was discarded the last time", not "which of the four
  rewrites discarded commit X". The better way to answer that question is to ask whether commit X
  still resolves.
- **A rewritten trunk leaves feature branches semantically stale.** Those branches also diverge
  from the new trunk on the remote. The existing conflict check reports this correctly, and only
  when each branch next moves. There is no local storage impact on the other branches, because one
  object database is shared and each branch reference holds its own objects alive.
- **A trunk reconciliation that fails badly enough to force re-initialisation** discards every
  local branch worktree and commit worktree on that worker, because the trunk worktree is the
  primary clone. The state is recoverable but not contained. This failure must be loud rather than
  retried blindly.
- **Re-deriving content at a discarded commit.** This is not guaranteed and varies by worker. It is
  a pre-existing limitation, tracked separately. This work corrects the claim in the documentation,
  not the behaviour.
- **A branch whose status refuses a commit.** A branch that needs a rebase, is being merged,
  failed a merge, is merged or is being deleted is excluded before reconciliation is reached.
  Synchronisation already excluded the merged and deleted ones; the others made the cycle fail
  on the commit write.
- **A deliberate change of tracking target.** Re-pointing a read-only repository to a new tag, or
  editing a repository's configured default branch, breaks lineage without rewriting anything. It
  is reconciled and not reported. User Story 6 covers it.
- **A tracked ref that disappears from the remote.** This is an absent ref, not a lineage break. It
  keeps its current behaviour and writes no record.
- **A remote rewound onto an ancestor of the imported commit.** A force push, or a ref moved
  backwards, can leave the remote head inside the history Infrahub already recorded. No write path
  records a commit the remote never carried, so the remote discarded content here exactly as a
  rewrite does. It is reconciled and recorded like any other rewrite, on every worker: a worktree
  the remote head is an ancestor of was rewound too, and FR-001b resets it.
- **A plain push that the synchronisation has not imported yet.** The check before the graph merge
  compares each remote head with the graph commit for equality (FR-005d). It therefore refuses a
  merge after a plain push to the source branch, or to the trunk of a repository whose branch
  records a commit other than the commit of its trunk, not only after a rewrite. A branch created
  from an older trunk is held too, even when it changed no file of that repository. The branch stays
  open, and the merge goes through once the next cycle imports the head. Contract section 9 says why
  the rule is equality and not ancestry.
- **A delivery that IFC-3220 holds while the trunk moves.** IFC-3220 FR-023 forbids an import of a
  branch while a delivery for that branch is pending, so the graph keeps the old trunk commit. When
  the remote trunk moves in that time, the check before the graph merge (FR-005d) finds a remote
  head the graph does not record. It refuses every merge of a branch that records a commit other
  than the commit of the trunk of that repository, until the delivery is done. IFC-3220 expects the
  opposite: in its User Story 2, scenario 2 queues a second merge behind the pending one, and
  scenario 3 replays onto a remote trunk that advanced. The two rules conflict. This spec does not
  decide which one wins. The decision is open and belongs to IFC-3220
  (`dev/specs/ifc-3220-writeback-failure-handling/spec.md`).
- **The commit Infrahub imported is no longer present in the local object database.** Ancestry
  cannot be tested. The branch is treated as diverged, which is the safe classification, and the
  record names the imported commit as the previous commit.

## Requirements *(mandatory)*

The requirement identifiers match the source PRD. FR-015 and FR-016 of the PRD are out of scope
here. See "Out of Scope".

### Functional Requirements

#### Detection

- **FR-001**: The system MUST classify a tracked ref's remote head against the imported commit by
  ancestry. The classification MUST distinguish unchanged, fast-forward and diverged. Equality
  alone MUST NOT be used.
- **FR-001a**: The system MUST treat a remote head that is an ancestor of the imported commit as a
  lineage break, and MUST NOT treat it as unchanged or as a fast-forward. No write path records a
  commit the remote never carried, so such a remote was rewound and content was discarded. The
  branch MUST be reconciled and recorded like any other rewrite.
- **FR-001b**: The system MUST keep two comparisons apart. Whether the history was rewritten is
  decided from the commit **recorded in the graph** for that branch. Whether a given worker's clone
  must move is decided from **that worker's own branch worktree**. The first drives the record and
  the signal. The second drives the reset. A worktree that already is the remote head, or is an
  ancestor of it, MUST NOT be reset. A worktree the remote head is an ancestor of MUST be reset,
  because the remote was rewound and nothing leaves a commit there that exists nowhere else.
- **FR-001c**: A worker whose clone is stale MUST reset even when the graph already holds the
  remote's commit, and MUST record nothing when it does. Without this, every worker except the one
  that ran the reconciliation keeps the discarded history. Recording from it would produce one
  record per worker instead of one per event.
- **FR-002**: The system MUST distinguish a lineage break under an unchanged tracking target from a
  lineage break caused by the tracking target itself changing. Only the first is a rewrite.
- **FR-003**: The system MUST NOT describe a divergent history as a merge conflict. This applies to
  every error, log line and status.

#### Reconciliation

- **FR-004**: On a rewritten branch the system MUST reset to the remote history and re-import. The
  divergence itself MUST NOT be the failure. The reset MUST happen, and the import MUST be
  attempted on the new commit. An import that then fails on the content of that commit is an
  ordinary import failure. FR-018 governs it.
- **FR-005**: Every worker MUST enforce reset-on-divergence on its own clone before it advances a
  branch worktree **from the remote**. Convergence MUST NOT depend on receiving a notification.
  This covers the synchronisation collector and the convergence handler.
- **FR-005a**: The merge path MUST fetch and compare both the source branch and the destination
  branch against the remote before it merges. The merge path reads its source commit from the local
  branch ref and advances the destination worktree from local state, without contacting the remote,
  so FR-005 does not reach it. A branch whose clone is not the remote head is decided by its graph
  commit:
  - When the graph commit equals the remote head, only this clone is stale. The merge path MUST move
    the branch onto that head and merge, whether the clone is behind, ahead or diverged.
  - When the graph commit differs and the clone is ahead or diverged, the rewrite is not reconciled
    yet. The merge path MUST refuse the merge with a typed error naming a divergent remote history.
    It MUST NOT reconcile that branch itself.
  - When the graph commit differs and the destination clone is on or behind its remote head, the
    remote would reject a push onto an older trunk, and the record of a merge onto a head the graph
    never imported would hide that head. The merge path MUST refuse the merge with the same typed
    error.
  - When the graph commit differs and the source clone is on or behind its remote head, the merge
    path MUST move the source onto the graph commit when the remote history holds that commit, and
    MUST merge the source as it is otherwise. In that last case the Git merge can hold a source that
    differs from the one the graph merged, which is an accepted risk. When the merge does not use
    the remote head of the source, the merge path MUST log a warning that names the commit it uses,
    the remote head, and that the commits after it stay on the source branch.
- **FR-005b**: The system MUST NOT push a commit the remote has already discarded. Merging a stale
  source branch into the trunk and pushing the result restores commits a rewrite removed. When a
  rewrite exists to remove a leaked credential, that restores the credential.
- **FR-005c**: The merge path MUST NOT reset a diverged branch and then merge it while the graph
  commit of that branch differs from the remote head. Doing so writes the merge commit to the graph,
  so the next synchronisation cycle sees the graph and the remote agree and classifies the branch
  unchanged. The rewrite is then never recorded, the trunk signal never fires, and the rewritten
  content is never re-imported. Resetting the source also merges content that was never imported at
  all.
- **FR-005d**: The Git merge runs after the graph merge, when the source branch is merged and is
  never synchronised again, so a refusal there cannot clear by a retry. The branch merge MUST
  therefore compare, before the graph merge, the remote heads of the source branch and of the trunk
  of every repository whose merge runs in Git with the commits the graph records, and MUST refuse
  the merge while one differs. A repository whose source branch records the commit that its trunk
  records has nothing to merge in Git: the system MUST NOT run its Git merge, and MUST compare only
  the remote head of its source branch. That refusal leaves the branch open, and the merge can run
  again after the synchronisation imports the head. A remote that refuses the credentials of a
  repository that needs a Git merge MUST block the merge, because that Git merge would fail the same
  way after the graph merge. Any other failure to read a remote, and a remote not read before the
  total deadline of the check, MUST be logged as a warning and MUST NOT block the merge. A refusal
  of the Git merge itself, after a remote moved between the two checks, MUST say that the branch is
  merged in Infrahub and not in Git, and how to finish the merge in Git. The user finishes that
  merge in Git. The delivery queue of IFC-3220 does not recover it. After a rewrite of the source or
  of the trunk, its FR-020 and FR-022 only mark such a delivery unreplayable, with a named cause.
  After a plain push to the trunk between the two checks, IFC-3220 specifies no recovery.
- **FR-006**: The worker-convergence broadcast MUST cover every branch reconciled in a cycle. It
  MUST be sent before a failed branch aborts the flow.
- **FR-007**: A worker that reconciles itself MUST NOT record the commit and MUST NOT emit the
  report. Both belong to the worker that performed the synchronisation.
- **FR-008**: The system MUST NOT force-push to the remote under any circumstance. Reconciliation
  is inbound only.
- **FR-009**: Read-only repositories MUST be subject to FR-001, FR-002, FR-003 and to the recording
  requirements below. They MUST NOT be reset. They resolve commits directly and never diverge in
  the sense that FR-004 repairs.

#### Recording

- **FR-010**: The system MUST record, per repository and per branch, the commit previously
  imported, the commit reconciled onto, the time of the reconciliation, and a cumulative count of
  reconciliations for that branch.
- **FR-011**: The record MUST be written only when FR-002 identifies a rewrite. It MUST overwrite
  the previous record rather than accumulate. The system MUST NOT clear it.
- **FR-012**: The record MUST NOT appear in a branch diff or in a proposed change. It MUST NOT be
  able to produce a merge conflict.
- **FR-013**: The record MUST NOT be folded into the repository synchronisation status. That status
  stays free to be redefined independently.
- **FR-014**: A rewrite of the configured default branch MUST emit at most one outbound signal per
  event, and MUST NOT emit more than one. At least one consumer MUST be able to receive it. A
  rewrite of any other branch MUST NOT emit one. The guarantee is one-sided: the record write and
  the emit are separate operations, so a record that lands while its emit fails is never retried.

#### Truthfulness of the error path

- **FR-017**: When a pull fails for a reason the system cannot classify, the message MUST NOT claim
  a merge conflict unless the system observed one. No path runs `git pull`, so a pull never stops on
  diverged branches. The merge guard carries the diverged case: its `RepositoryDivergentHistoryError`
  MUST have its own message naming a divergent history.

#### Failure handling and observability

- **FR-018**: A reconciliation that fails on the repository's configured default branch MUST be
  logged at error level and MUST be recorded against the repository. The system MUST NOT retry it
  automatically within the same cycle. A failed trunk reconciliation can force a re-initialisation
  that discards every local branch worktree and commit worktree on that worker, because the trunk
  worktree is the primary clone. That blast radius is recoverable but not contained, so the failure
  must be loud.
- **FR-018a**: A failure on one repository MUST NOT stop any other repository from synchronising in
  the same cycle. "Loud" under FR-018 means visible and recorded, never propagated out of the
  synchronisation flow. Propagating it would recreate, at repository level, the outage FR-006
  removes at branch level.
- **FR-019**: Each reconciliation MUST log the repository, the branch, the commit that was
  discarded and the commit that replaced it. Until the visibility work of INFP-671 ships, this log
  line is the only way an operator learns that a reconciliation happened.

### Key Entities *(include if feature involves data)*

- **`CoreGenericRepository`**: gains four branch-local attributes. They record the previous commit,
  the reconciled commit, the reconciliation time and the per-branch count. Branch-local makes each
  value per branch, invisible to branch diffs and proposed changes, and never a merge conflict.
  This is the pattern the recorded commit, the synchronisation status and the internal status
  already use. All four are optional with no default, so no existing repository needs backfilling.
- **`CoreRepository`**: reconciled. Its configured default branch is treated like any other tracked
  branch.
- **`CoreReadOnlyRepository`**: detected and recorded, never reconciled. It resolves a commit and
  creates a commit worktree instead of pulling a branch. The divergence failure this work removes
  cannot occur there.
- **Ref classification**: a typed value with five cases. Unchanged, fast-forward, rewrite,
  re-target and remote-absent. It is a type and not a boolean, so that "diverged" and
  "re-targeted" cannot collapse into each other at a call site. Both reconcile the same way, and
  only a rewrite is recorded and signalled.
- **Trunk-rewrite signal**: one outbound event per rewrite of the configured default branch.
- **Repository operational status**: unchanged. It describes whether the remote is reachable, which
  is a different phase.
- **Repository synchronisation status**: unchanged, and deliberately so. See FR-013.

No new node kind is introduced.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A rewritten non-default branch returns to a healthy synchronised state with zero user
  actions.
- **SC-002**: A rewritten default branch returns to a healthy state with zero user actions. It
  produces at most one record and at most one signal, however many synchronisation cycles elapse,
  and never more than one. The guarantee is one-sided on purpose: the record write and the emit are
  separate operations, so a record that lands while its emit fails is never retried, because the
  next cycle sees the graph and the remote agree. Closing that needs an outbox, which is more
  machinery than a rare event is worth.
- **SC-003**: No message that describes a rewritten history uses the word "conflict".
- **SC-004**: After a reconciliation, every worker's view of the branch matches the remote. This
  includes workers that received no broadcast and workers added afterwards.
- **SC-005**: A rewritten branch never prevents another branch of the same repository from
  converging.
- **SC-006**: To determine why content at an earlier commit can no longer be re-derived, the
  repository's own stored state is enough. It is readable through the repository API on the branch
  in question. No access to worker logs and no access to the orchestrator is needed. The baseline
  today needs both, at roughly two hours of Solution Architecture time per incident. This work
  delivers the stored state. The human-facing surface that presents it belongs to INFP-671, which
  is out of scope here.
- **SC-007**: Re-pointing a repository at a different branch, tag or commit on purpose produces no
  rewrite report.

## Assumptions

- The remote is the source of truth for repository content. Infrahub reflecting a rewritten history
  is correct behaviour and not data loss.
- Rewriting the history of a feature branch is ordinary practice and must be absorbed quietly.
  Rewriting the trunk of a synchronised repository is abnormal and must be reported.
- Losing the ability to re-derive content at a superseded commit is acceptable. This work does not
  make it worse.
- The writeback delivery queue of the writeback PRD does not exist yet. The PRD requirements that
  read it therefore ship with that work. See "Out of Scope".

## Dependencies

- **The merge ordering of IFC-1449**, on `develop`. `InfrahubRepository.merge` pushes the merge
  commit before it records it and resets the destination worktree when either step fails. Every
  step here that resets a worktree relies on it: without it a rejected push would leave a merge
  commit on one worker alone for the reset to discard.
- The Gogs-backed live-remote test harness, which is already on `develop`, including its two
  server-side `pre-receive` hook helpers.
- The existing hard-reset primitive that pins a branch worktree to a named commit.
- The existing worker-convergence broadcast and its handler.

## Out of Scope

- **PRD FR-015 and FR-016**, which cover what a rewrite does to an outstanding writeback delivery.
  They ship with the writeback work of epic IFC-3220. The delivery queue they read does not exist
  yet, and the condition is unreachable without it.
- **Display of any of this.** The repository page, the branch list and the status vocabulary belong
  to INFP-671.
- **Rewinding schema already applied to a branch.** No provenance exists in the graph that would
  make it possible. Repository-owned definitions and objects carry a lineage link back to the
  repository that created them, so a reconciling import deletes what disappeared. Schema carries no
  such link, because the repository loads schema through the same public endpoint, with the same
  payload, as a person running the CLI. This is documented as a limitation.
- **Pruning orphaned commit worktrees**, and the per-worker inconsistency in re-deriving historical
  content. Both are pre-existing, neither is caused by this work, and both are tracked separately.
  This work changes their rate by making rewrites routine, which is why they are named here.
- **The fetch-flag inconsistency** on force-moved tags. The read-only fetch paths omit `--force`,
  so git rejects the tag update and exits 1: the repository errors on every cycle and stays pinned
  to the stale commit. IFC-2874 covers it.
- **The branch-support inconsistency** between read-only and read-write repositories on their
  tracked ref and commit attributes.
- **Pausing synchronisation, and pinning a repository to a chosen commit.** INFP-672 covers both.
- **Changing the meaning of the repository synchronisation status.** See FR-013.

## Decisions Taken During Specification

These were settled without asking, and they are closed. The review history is in
[critiques/](critiques/).

1. **PRD open question on FR-015 and FR-016**: both defer to epic IFC-3220. The delivery queue they
   read does not exist yet, and the Jira epic already states this.
2. **FR-017 is added on top of the PRD.** The PRD's FR-003 forbids the word "conflict" for a
   divergent history. The current error classifier maps the divergent-branches text of Git to a
   conflict message. Removing the divergence case alone would leave the same wrong message for any
   future unclassified pull failure. FR-017 states the message contract so that a test can hold it.
