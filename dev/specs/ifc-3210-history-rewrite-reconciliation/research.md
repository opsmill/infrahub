# Research: Git history-rewrite reconciliation

**Feature**: `dev/specs/ifc-3210-history-rewrite-reconciliation`
**Branch**: `history-rewrite-reconciliation-ifc-3210`
**Branches from**: `develop`
**Date**: 2026-09-29, re-checked against `develop` on 2026-10-01

Every claim below is checked against `develop`.

The merge path matters most to this design. `git/repository.py::InfrahubRepository.merge` pushes
the merge commit before it records it, and resets the destination worktree to its pre-merge commit
when either step fails. That ordering arrived with IFC-1449.

---

## R0. Current behaviour, confirmed on `develop`

| Claim | Where | Confirmed |
|---|---|---|
| The periodic sync is a cron flow, once a minute | `git/tasks.py::sync_remote_repositories`, `workflows/catalogue.py::GIT_REPOSITORIES_SYNC` | Yes |
| The sync calls the syncer, which calls the collector | `git/sync.py::RepositorySyncer.sync` → `git/repository.py::InfrahubRepository.collect_pending_imports` | Yes |
| The remote comparison uses equality only | `git/base.py::InfrahubRepositoryBase.compare_local_remote` compares `remote_branches[b].commit != local_branches[b].commit` | Yes |
| The pull sets no rebase and no fast-forward strategy | `git/base.py::InfrahubRepositoryBase.pull` calls `repo.remotes.origin.pull(<remote branch>)`; `workers/infrahub_async.py::set_git_global_config` sets neither `pull.rebase` nor `pull.ff` | Yes |
| A diverged remote is reported as a conflict | `git/base.py::InfrahubRepositoryBase._raise_enriched_error_static` maps Git's divergent-branches text to "there are conflicts that must be resolved" | Yes |
| One test asserts that text | `backend/tests/component/git/test_git_repository.py::test_pull_branch_conflict` | Yes |
| A second test asserts it | `backend/tests/integration/git/test_repository.py` | **No, and it is not what it looks like.** That file parametrises `"Need to specify how to reconcile"` in `test_repository_operational_status`, but that string is the **stderr the test injects** into `GitCommandError`, not a message it asserts. The test asserts `operational_status` only. Git still emits that text, so the parameter must stay as it is. Changing it would make the classifier fall through to its generic branch, which yields the same `ERROR`, so the test would stay green while testing nothing. |
| The sync broadcast covers the trunk only | `git/tasks.py::sync_repository_from_origin` sends one `RefreshGitFetch` for `staging_branch or registry.default_branch` | Yes |
| A failed branch suppresses that broadcast | `git/repository.py::InfrahubRepository.raise_if_branches_failed` raises inside `RepositorySyncer.sync`; `sync_repository_from_origin` catches `RepositoryError` **after** the sync call and **before** the send, so the send never runs | Yes |
| The broadcast handler fetches, then resets or pulls | `message_bus/operations/git/repository.py::fetch` | Yes |
| The hard-reset primitive exists | `git/base.py::InfrahubRepositoryBase.reset_to_commit`; it does not contact the remote | Yes |
| No helper does "fetch, then reset to origin/" | Searched `git/`; none | Yes |
| The periodic sync skips read-only repositories | `sync_remote_repositories` passes `kind=InfrahubKind.REPOSITORY` to `git/utils.py::get_repositories_commit_per_branch` | Yes |
| Read-only resolves `origin/{ref}` directly | `git/repository.py::InfrahubReadOnlyRepository.get_commit_value` and `.update_latest_commit` | Yes |
| `operational_status` is branch-agnostic and flaps | Schema `core/schema/definitions/core/repository.py` marks it `AGNOSTIC`; `git/base.py::InfrahubRepositoryBase.fetch` sets it back to `ONLINE` at the start of every cycle | Yes |

### Branch support on the repository kinds

Read from `core/schema/definitions/core/repository.py`.

| Kind | Attribute | Branch support |
|---|---|---|
| `CoreGenericRepository` | `commit` | LOCAL |
| `CoreGenericRepository` | `sync_status` | LOCAL |
| `CoreGenericRepository` | `internal_status` | LOCAL |
| `CoreGenericRepository` | `operational_status` | AGNOSTIC |
| `CoreGenericRepository` | `name`, `description`, `location` | AGNOSTIC |
| `CoreRepository` | `commit` | LOCAL (overrides the generic with the same value) |
| `CoreRepository` | `default_branch` | not overridden, so AGNOSTIC from the node |
| `CoreReadOnlyRepository` | `commit` | **AWARE** |
| `CoreReadOnlyRepository` | `ref` | **AWARE** |

`dev/knowledge/backend/git-integration.md` stated that `commit` is LOCAL on all repository types.
That is wrong for `CoreReadOnlyRepository`, and this change corrects the table there.

---

## R1. The ancestry test

**Decision**: use `git merge-base --is-ancestor <imported_commit> <remote_head>`, reached through
GitPython's `Repo.is_ancestor(ancestor_rev, rev)`.

**Rationale**: it is one plumbing call per changed ref, it is exactly the question FR-001 asks, and
it needs no extra network round trip because the fetch already brought the objects in. The full
classification is:

| Imported commit vs remote head | Classification |
|---|---|
| Equal | `UNCHANGED` |
| Imported is an ancestor of remote head | `FAST_FORWARD` |
| The remote head does not contain the imported commit, tracking target unchanged | `REWRITE` |
| The remote head does not contain the imported commit, tracking target changed | `RETARGET` |
| The remote carries no such ref | `REMOTE_ABSENT` |
| Imported commit is not present locally, tracking target unchanged | `REWRITE` (safe classification, see below) |
| Imported commit is not present locally, tracking target changed | `RETARGET` |

**A remote head behind the imported commit is a rewound remote.** The imported commit comes from
the graph, and an audit of every `update_commit_value` write site found no path that records a
commit the remote lacks. `create_locally` records straight after a clone. `pull` records a commit
the fetch brought in. `reset_to_commit` records the SHA it pinned. The synchronisation's
new-branch path pushes first, and a rejected push raises into `failed_imports` before the record
is reached. `merge` pushes before it records and resets the worktree when either step fails. The
read-only paths record what they read from the remote. So the remote head sitting on an ancestor
of the imported commit has one cause: the remote was rewound, by a force push or a ref moved
backwards. It discards content exactly as a rewrite does, so it is reconciled and recorded.

**The worktree comparison reaches the same conclusion.** A worktree ahead of `origin/` used to
mean a commit a rejected push had left behind, which `git-integration.md` lists under Known
limitations and `compare_local_remote` flags every cycle. `merge` now pushes before it records and
resets the destination when either step fails, and `rebase` delegates to `merge`, so that state no
longer arises and such a worktree has been rewound. The reset moves it onto the remote head, which
also removes the once-a-minute "update was detected but the commit remained the same after
pull()" log line.

**The missing-object case.** If the imported commit is no longer in the local object database, the
ancestry test cannot run. `Repo.is_ancestor` raises rather than answering. The branch is then
classified `REWRITE`, because the only other reading is that the local clone lost an object, and a
reset to the remote repairs both readings. The record names the imported commit as the previous
commit, which is still the true answer to "what did Infrahub hold".

**Alternatives rejected**:

- `git rev-list --count <a>..<b>` and read the counts. It answers the same question with more
  output to parse and no better failure mode.
- Ask the remote with `ls-remote` and compare. It answers equality only, which is the defect being
  removed.

---

## R2. Where the read-write detection runs

**Decision**: inside `git/repository.py::InfrahubRepository.collect_pending_imports`, over the
`updated_branches` list returned by `compare_local_remote`, after `fetch()` and before `pull()`.

**Rationale**: the fetch that precedes it has already brought the remote objects in, so the
ancestry test needs no network.

**The candidate set is a union, not just `compare_local_remote`.** That method compares each
worker's **local** heads against the remote, which is the right input for deciding a reset and the
wrong one for deciding a record. The collector adds branches whose **graph commit** differs from
the remote head. Without that second set a `default_branch` edit is never classified, because it
moves no ref, and a worker whose graph already matches the remote never records anything it should.
FR-001b is the rule; this is where it is applied. Classifying inside the collector keeps
the per-branch failure isolation that is already there: a branch that fails classification joins
`failed_imports` and the rest of the cycle continues.

**Alternatives rejected**:

- Classify inside `compare_local_remote` and change its return type. Its only production caller is
  `collect_pending_imports`, so this is not about protecting other callers; it is that the method
  answers "which refs differ" and the classification answers "why", and folding the second into the
  first gives one method two reasons to change. Its three test callers would also all need
  rewriting.
- Classify inside `pull()`. The pull is also the self-healing path of R3, and that path must not
  record or report (FR-007). Keeping the sync-side classification separate from the pull-side reset
  is what keeps FR-007 enforceable.

---

## R3. Where the self-healing reset runs

**Decision**: inside `git/base.py::InfrahubRepositoryBase.pull`, before the `origin.pull` call.
Hard-reset onto the remote head unless the worktree head already is it, is an ancestor of it, or
the remote carries no such ref.

A worktree ahead of its remote resets too. The state that argued against it, a commit left behind
by a rejected push, no longer arises: `merge` pushes before it records and resets the destination
when either step fails, and `rebase` delegates to `merge`.

**Rationale**: FR-005 requires convergence to hold for a worker that received no broadcast. Every
path that advances a branch worktree **from the remote** goes through `pull`: the sync collector,
and the `RefreshGitFetch` handler when no commit is pinned. Putting the rule there makes the
property true by construction for those paths rather than by broadcast coverage.

**It does not cover every path.** Two paths advance a destination worktree from purely local
state, with no fetch and no pull:

- `git/repository.py::InfrahubRepository.merge` runs `git merge` in the destination worktree.
- `git/base.py::InfrahubRepositoryBase.create_branch_in_git` branches from the local trunk.

A worker that missed the broadcast and then runs a merge builds on the discarded history. The
broadcast (FR-006) makes that unlikely, not impossible, and "unlikely" is what FR-005 exists to
replace.

**Both sides of the merge are exposed, and the source side is the dangerous one.** `merge` reads
the commit it merges from the local source ref (`get_commit_value(..., remote=False)`), and
`merge_git_repository` performs no fetch. A worker holding a stale source branch therefore merges
the **pre-rewrite** history into the trunk and pushes it, putting the discarded commits back on the
remote. If the rewrite existed to strip a leaked credential, the merge restores it. The destination
side only corrupts one worker's view; the source side corrupts the remote, for everyone.

FR-005a therefore covers both worktrees. **It refuses the merge rather than reconciling it**, and
FR-005c says why that distinction matters.

Reconciling inside the merge path looks tempting and destroys the evidence.
`InfrahubRepository.merge` pushes the merge commit before it records it on the destination, so a
reset-then-merge puts the merge commit on the remote and in the graph. The next cycle then compares
the graph against the remote, finds them equal, and classifies `UNCHANGED`. No record, no trunk
signal, no re-import of the rewritten content. Resetting the source is worse still: it pulls in
the rewritten history and merges objects the graph never imported.

Refusing keeps one owner for reconciliation. The synchronisation cycle resets, records, signals and
re-imports, in that order, under the repository lock. The merge fails with a typed error, the next
cycle reconciles, and the retry succeeds.

**Accepted residual risk**: the remote can be rewritten between the guard's fetch and the push that
follows. The guard narrows that window, it does not close it. FR-005b is a best-effort property,
not a guarantee.

Branch creation is left alone: a branch created from a stale trunk converges on its own first pull,
and creating it is not a merge of anything.

**What the pull-side reset must not do** (FR-007): it must not write the commit to the graph, must
not write the rewrite record, and must not emit the signal. `pull` already takes
`update_commit_value`, and the broadcast handler already passes `update_commit_value=False`. The
record and the signal are written by the recorder in the sync path, never here.

**Why an unconditional reset is safe.** `InfrahubRepository.merge` pushes the merge commit first,
records it second, and resets the destination worktree to its pre-merge commit when either step
fails. A rejected push therefore leaves no merge commit that exists on one worker's disk and
nowhere else, which is the one state a reset onto the remote head would have discarded. That
ordering arrived with IFC-1449 and it is what makes the pull-path and sync-path resets safe.

---

## R4. Telling a rewrite from a re-target

This is the hardest decision in the feature. FR-002 and SC-007 both depend on it.

**The problem**: a lineage break looks identical whether the remote history was rewritten or the
repository was re-pointed at a different target. The detector sees only two commits. The tracking
target that produced the imported commit is not stored anywhere.

**Decision**: the mutation that changes a tracking target writes a short-lived suppression marker in
the shared cache. The component that calls the detector reads it, passes the result as
`target_changed`, and deletes it after the commit write for that branch succeeds. Read-only repositories do not use it at all: their re-point
travels in band on the workflow model.

- Key: repository id plus Infrahub branch name.
- Read-only repositories write no marker. Their re-point travels in band on the workflow model,
  set from the comparison
  `graphql/mutations/repository.py::InfrahubRepositoryMutation.mutate_update` already makes.
- Writer, read-write: **this comparison does not exist yet.** The same method returns to
  `super().mutate_update` immediately for any kind other than read-only, so nothing there compares
  the old and new `default_branch` on `CoreRepository`. The comparison has to be added before that
  early return. It is a change to the mutation, not a reuse.
- Reader: **the detector's caller, and nothing else.** A present marker makes `target_changed` true,
  so the detector returns `RETARGET`. The branch is still reset onto the remote head; only the
  record is skipped. The delete happens after the commit write, not at the read.
- Scope: **read-write repositories only.** A read-only re-target is carried in band on the
  workflow model, because the mutation already computes the comparison. That removes the cache from
  the read-only path entirely: no expiry, no timing question, no lost marker.
- Time to live: one hour. The widened candidate selection below puts a re-targeted trunk in the
  classified set on the next cron cycle, so the marker is read within a minute. An hour is generous
  and short enough that a stale marker cannot suppress an unrelated rewrite days later.

**What makes the read-write marker readable.** A `default_branch` edit moves no git ref, so
`compare_local_remote` reports nothing for it, and there is no per-repository sync to submit:
`GIT_REPOSITORIES_SYNC` is one cron flow over every repository, with `concurrency_limit=1` and
`CANCEL_NEW`, so a submission is either cancelled or re-runs the fleet.

The answer is the candidate selection in R2: the collector considers branches whose **graph commit**
differs from the remote head, as well as those whose local head does. A `default_branch` edit
changes which remote branch feeds Infrahub's default branch, so the graph commit stops matching and
the next cycle classifies it. That selection is needed for FR-001b regardless, so the re-target
case costs nothing extra.

**Why the caller reads it and not the recorder.** The recorder writes nothing unless the
classification is already `REWRITE`, so on a `RETARGET` it would return before reaching the marker
and never consume it. The marker would then survive its full hour and suppress the *next*, genuine, rewrite
of that branch. Reading at classification time keeps `RETARGET` reachable in the detector's own
tests, and deleting after the commit write keeps a failed cycle retryable.

**Rationale**: the cache is how this codebase already coordinates repository state across workers,
and the read-write edit has no in-band channel to travel on. The marker is deleted once the commit
write lands, so it cannot suppress twice.

**Known failure mode, accepted and documented**: if the cache is flushed between the mutation and
the reconciliation, a deliberate re-target is recorded as a rewrite. That costs more than a wrong
row. The count on the branch goes one too high, and the trunk signal fires, so whatever a customer
has wired to that webhook receives a security-remediation notice for an ordinary configuration
change.

Two things keep the window small. The marker is deleted only after the commit write for that branch
succeeds, so a cycle that fails anywhere earlier retries with the marker still in place. And the
widened candidate set classifies a re-targeted trunk on the next cycle, within a minute of the
edit.

The read and the delete are separate operations, because the cache has no atomic get-and-delete.
`GIT_REPOSITORIES_SYNC` runs with `concurrency_limit=1` and `CANCEL_NEW`, so no second cycle enters
that window. A user edit does. A second re-target between the read and the delete writes a fresh
marker, the cycle deletes that newer marker, and the next cycle reports the second re-target as a
rewrite. Deleting only the value that was read would close it, and the cache API would have to grow
a compare-and-delete to do so. Accepted: the cost is the one in the risk table, for two deliberate
re-targets of the same repository inside one cycle.

**Alternatives rejected**:

- **A fifth attribute storing the tracking target that produced the imported commit.** It is exact,
  it needs no cache, and it is the strongest of the options. Rejected only because the PRD fixes
  the shape at four scalars and argues that decision explicitly. If that constraint is relaxed,
  this replaces the marker.
- **A temporal read of the graph**: ask for the tracking target as it was at the imported commit's
  `updated_at`. Exact for read-write, where `default_branch` and `commit` are written by different
  actors at different times. Wrong for read-only, where the same mutation writes `ref` and `commit`
  at the same timestamp, so the temporal read returns the new ref and never the old one.
  **It is a live alternative to the cache marker**, not a rejected one, because the read-only path
  no longer shares a mechanism with read-write: it carries its re-point in band. Replacing the
  marker with a temporal read on the read-write side would remove the cache entirely, along with
  its expiry, its sweep and its lost-marker path. It is left out of this design only because the
  marker is already specified and tested; it is the first thing to reach for if the marker proves
  awkward.
- **Infer from reachability**: decide it is a re-target when the imported commit is still reachable
  from some other ref on the remote. Rejected as wrong in a common case: a rebase of a branch whose
  old commits were already merged elsewhere leaves them reachable, and the rewrite would go
  unrecorded.

---

## R5. Widening the broadcast and moving it before the raise

**Decision**: collect one branch-and-commit pair per branch the cycle advanced, send one coalesced
`RefreshGitFetch` per repository carrying all of them, and send it before
`raise_if_branches_failed`.

**Two changes are needed, and they are separable.**

1. **Ordering.** `RepositorySyncer.sync` raises through `sync_git_repo_with_origin_and_tag_on_failure`,
   and `sync_repository_from_origin` catches that raise before it reaches the send. The syncer must
   return the reconciled branches to its caller, and the caller must broadcast before it re-raises.
2. **Coverage.** `sync_repository_from_origin` sends one message for
   `staging_branch or registry.default_branch` only. It must send for every branch the cycle
   advanced.

**Coalescing.** The handler takes the repository lock and fetches once per message. That lock is
contended by merges and by other syncs. One message per cycle carrying N pairs is one lock hold
instead of N. It needs a new field on `RefreshGitFetch`.

PR #10669 is **not** precedent for this. Its refs check sends one `RefreshGitFetch` per moved ref,
inside a loop, and adds no field to the message. The coalescing here is new, which is why the
message change needs a validator: the single-branch fields must always equal the first entry of
`branches`, or a worker on the previous code converges a branch the message was not about.

**Message shape**: add an optional list of branch-and-commit pairs. Keep the existing single-branch
fields, because five other emission sites use them and rewriting all six is outside this epic.
The handler prefers the list when it is present.

**Alternatives rejected**:

- One message per reconciled branch. Correct but it multiplies lock holds on the most contended
  lock in the git subsystem.
- Replace the single-branch fields outright. It touches five call sites that have nothing to do
  with this epic and makes the change harder to review and to revert.

---

## R6. How the record is written

**Decision**: a new `HistoryRewriteRecorder` in `backend/infrahub/git/` writes the four attributes
through the SDK node API, on the Infrahub branch the reconciliation targeted. It is the sole write
path for those attributes.

**Why not extend the existing commit write.** `git/base.py::InfrahubRepositoryBase.update_commit_value`
calls `InfrahubClient.repository_update_commit`, which runs a canned mutation from the SDK. Adding
four variables to it is a change in the `python_sdk` submodule, which needs its own PR merged
upstream before the pointer can move here. A separate write from the backend keeps this epic inside
one repository.

**Event consequence, per ADR 0016.** The write is an ordinary GraphQL mutation, so it emits a
`NodeUpdatedEvent` with origin `live`. Cross-node computed attributes, display labels and
human-friendly ids that read the repository node will therefore recompute on a rewrite. Webhooks
and user action rules will fire.

**Decision on the origin label**: do not add a new `NodeMutationOrigin` value for this bookkeeping.
A rewrite is rare and the extra event is one per reconciled branch.

The reason is not that the trigger builders would need revisiting. They match
`NodeMutationOrigin.LIVE` explicitly, so a new value is ignored by every one of them with no change
at all. The real cost is on the writing side: the record goes through an ordinary SDK mutation,
which always stamps `live`. Stamping anything else needs a way to carry the origin from the worker
through the GraphQL mutation, and no such channel exists. That is the work a new value would
actually buy, and it is not worth it for a rare write. Note it in the plan so a future
high-frequency writer of the same attributes revisits it.

**Idempotence for the trunk (SC-002).** The recorder writes only when the classification is
`REWRITE`. After the reset and the re-import, the recorded commit equals the remote head, so the
next cycle classifies `UNCHANGED` and writes nothing. No more than one record per event follows
from the classification, not from a guard. Fewer is possible: a failed record write is never
retried, because the commit is already in the graph.

---

## R7. The four attributes

**Decision**: four scalar attributes on `CoreGenericRepository`, all optional, all with no default,
all `BranchSupportType.LOCAL`.

**Why LOCAL and not AWARE.** LOCAL gives a per-branch value that never reaches a branch diff and
can never produce a merge conflict. The diff query selects only
`branch_support IN [aware, agnostic]`, and the bulk merge touches only `aware`. This is why nobody
has ever resolved a conflict on `sync_status`. It satisfies FR-012 directly.

**Why not AGNOSTIC.** AGNOSTIC is conflict-free but not diff-invisible: agnostic nodes still reach
the diff, forced to `UPDATED`. It would also make the record one value for the whole repository,
which contradicts FR-010's per-branch requirement.

**Why optional with no default.** Nothing needs backfilling, so no data migration is needed.

**The read-only anomaly.** `CoreReadOnlyRepository` sets `commit` to AWARE and adds an AWARE `ref`
of its own. The four
new attributes are declared on the generic and are **not** overridden on `CoreReadOnlyRepository`,
so they stay LOCAL there too. A read-only repository therefore gets a diff-invisible, never-merged
record while its `commit` beside it is diff-visible and merged. That asymmetry is deliberate: FR-012
is unconditional, and correcting the `commit` and `ref` overrides is explicitly out of scope.
A branch-safety test asserts the four attributes are absent from a diff on both kinds.

**Governance.** This is an "Ask First" change under `AGENTS.md` (database schema change, and the
attributes surface on three GraphQL node kinds). The design is complete; implementation needs a
maintainer's sign-off.

---

## R8. The trunk-rewrite signal and its consumer

**Decision**: a new `InfrahubEvent` subclass in `backend/infrahub/events/repository_action.py`, with
a new member in `core/constants/__init__.py::EventType`. The consumer is the webhook subsystem.

**Why that is a consumer and not a dead event.** `EventType.available_types()` feeds the `event_type`
enum on `CoreStandardWebhook` and `CoreCustomWebhook`
(`core/schema/definitions/core/webhook.py`). A new member therefore appears in the webhook event
selector with no further code. `webhook/models.py` builds an `EventTrigger` from that value, so a
webhook pointed at the new event receives one delivery per emission. That is wireable by an
operator and assertable in a test, which is what FR-014's "at least one consumer wired to receive
it" has to mean for the requirement to be testable.

**To confirm with Patrick.** The PRD leaves this open. Two alternatives he may prefer:

- A built-in notification or task-log surface, which would need new machinery this epic does not
  have.
- Defer the signal to the visibility work of INFP-671, which owns how repository state is shown.

**Precedent, and why it is not repeated.** `CommitUpdatedEvent` already exists and
`EventType.REPOSITORY_UPDATE_COMMIT` is already in the webhook enum, yet no `EventTrigger` in the
codebase lists it. The difference here is the acceptance test: the test wires a webhook to the new
event and asserts a single delivery per rewrite, so the wiring is held by a test rather than
assumed.

**Emission point**: the recorder, immediately after a successful record, and only when the
reconciled branch is the repository's configured default branch. The recorder is already the single
place that knows a rewrite happened and which branch it was, so no second classification is needed.

---

## R9. The error message

**Decision**: give the divergent-branches case its own typed exception and its own message. Keep the
conflict message for the case where a conflict was observed.

**Current behaviour**: `_raise_enriched_error_static` matches Git's
"Need to specify how to reconcile divergent branches" and returns "there are conflicts that must be
resolved". After this feature, the sync path never reaches that pull on a diverged branch, so the
message becomes unreachable. `InfrahubRepositoryBase.pull` holds the **only** `origin.pull` call in
the backend, so once the sync classifies a diverged branch and resets it instead of pulling, no
caller reaches the divergent-branches text at all. The classifier entry is corrected rather than
deleted because git still emits that text on any future caller, and leaving a wrong mapping in
place for the next one to find is how this defect arrived. FR-017 states the contract.

**Test consequences**:

- `backend/tests/component/git/test_git_repository.py::test_pull_branch_conflict` asserts the wrong
  text. It becomes a test of the new behaviour: a branch whose remote history diverged is reset to
  the remote head by `pull`, with no exception at all.
- `backend/tests/integration/git/test_repository.py::test_repository_operational_status`
  parametrises `"Need to specify how to reconcile"` against `ERROR`. **That parameter must not
  change.** It is the stderr the test injects into `GitCommandError`, and git still emits that
  text. Swapping it for Infrahub's new wording would send the classifier down its generic branch,
  which returns the same `ERROR`, so the test would keep passing while no longer exercising the
  divergent-branches case. Add an assertion on the message instead: it must not contain the word
  "conflict".

**The status flap**: on a diverged branch, `operational_status` goes to `ERROR` on every cycle and
`fetch()` sets it back to `ONLINE` on the next one, so it flaps once a minute. Removing the failure
removes the flap. Nothing else about `operational_status` changes: it describes whether the remote
is reachable, which is a different phase.

---

## R10. Read-only detection, and the overlap with PR #10669

**PR #10669 (IFC-3152, "detect upstream movement on read-only repository refs")** is merged into
`pog-repo-commit-visibility-ifc-3101`, which has not itself landed on `develop`. It is a different stack from this epic's
branch, which comes off `develop`. What it ships:

- `backend/infrahub/git/refs_check/`: a scheduled flow that lists a read-only repository's remote
  refs, compares each against the local view, and converges the pool when one moved.
- A gateway that reads local and remote heads, a scheduler that spaces checks, a claim that stops
  two runs overlapping, and typed result models.
- A config setting `git.read_only_refs_check_interval_mins`.
- `RepositoryBranchInfo.ref` and `RepositoryData.location`, so the per-branch tracked ref is
  available to the flow.

**What it does not do**: it compares heads by equality, not by ancestry. It writes no tracked
commit, performs no import, and records nothing. Its convergence deliberately pins every worker to
the commit Infrahub already tracks.

**Decision**: build on it, do not rebuild it. This epic adds the ancestry classification and the
record to the read-only path. It does not add a second remote-listing mechanism.

**Where it is now**: merged, but into `pog-repo-commit-visibility-ifc-3101`, not into `develop`.
Until that stack lands, none of it is available here.

**Consequence for sequencing**: the read-only slice (User Story 5) is slightly cheaper once #10669
reaches `develop`, because the scheduled flow already contacts the remote. `RefMovement.previous_head` is **not** the imported commit: it comes from `_resolve_local_head`, which reads the local clone from disk, and this design requires
the graph value. What #10669 does supply is `TrackedCommitReader`, which reads the graph, so the
classification takes its inputs from there and uses `_detect_movements` only as the "this ref
moved" trigger.

If #10669 is not on `develop` when the slice starts, the classification attaches to
`git/repository.py::InfrahubReadOnlyRepository.update_latest_commit` instead. The record and the
precondition are identical either way. The tasks name both attachment points.

**Other Patrick PRs checked**:

| PR | Ticket | Overlap with this epic |
|---|---|---|
| #10667 | IFC-3147, one status row per branch | None. It reads per-branch repository values for a GraphQL query. It does not touch the sync or pull paths. It is a natural reader of the four new attributes later, which is INFP-671's job, not this epic's. |
| #10530 | IFC-3101, commit visibility spec | None directly. It introduces `git/state/` and a bounded worker RPC. The four attributes are readable through its query surface once INFP-671 exposes them. |
| #10542 | IFC-3105, honour the default branch | **Adjacent and important.** It makes the repository trunk a resolved value rather than a silent fallback, changes `git/base.py` heavily, adds `git/remote_refs.py`, and rewrites `get_initialized_repo`. It removes the "warm path falls back to Infrahub's default branch" defect this epic's trunk handling would otherwise inherit. It is not a prerequisite, but a rebase conflict in `git/base.py` is likely. Flagged in the plan's risk list. |
| #10513 | INFP-671, cross-branch repository status | None. It is the display surface this epic's record will eventually feed. Explicitly out of scope here. |

---

## R11. The test harness

**Decision**: extend the Gogs-backed live-remote harness, which is already on `develop`. Add one
force-push helper beside the existing `_push_commit_to_remote`.

**What exists on `develop`** (`backend/tests/integration/git/conftest.py`,
`test_git_live_remote.py`):

- A Gogs container fixture with an API token and repository creation.
- `_push_commit_to_remote`: makes a commit inside the remote container and pushes it.
- `_install_remote_branch_rejection_hook` / `_remove_remote_branch_rejection_hook`: a server-side
  `pre-receive` hook that rejects updates, used to simulate branch protection. Nothing in this
  design needs them, but a task that wants to simulate remote-side policy has them.
- Config-reset fixtures for merge and branch-name settings.

**What is missing**: a force-push helper. A rewrite is a force-push, and the Gogs bare repository
accepts one only when the branch is not protected. The helper commits a divergent history in the
container and pushes it with `--force`.

**Every test in this plan uses testcontainers.** Unit tests for the classifier and the recorder run
without a database. Component and integration tests run against testcontainers-provisioned
services. No test uses an external or locally-running Neo4j.

---

## R12. Documentation corrections

Three statements in `dev/knowledge/backend/` are wrong or incomplete today, independently of this
feature. Tasks cover all three.

1. `git-integration.md`, "Repository state and branch support": the table says `commit`,
   `sync_status` and `internal_status` are LOCAL. On `CoreReadOnlyRepository`, `commit` and `ref`
   are AWARE, so they do reach diffs and merges.
2. `git-integration.md`, "How the workers converge": it does not say that the periodic sync's
   broadcast covers only the trunk or the staging branch, nor that a failed branch suppresses it.
   That is the property FR-006 changes, so it must be stated before and after.
3. `merge-failure-recovery.md`, "Key Files": it attributes the merge-start logic to
   `core/branch/tasks.py::_do_merge_branch`. That logic now lives in `core/merge/orchestrator.py`.

Two of the four "Volatile section" notes in `git-integration.md` need rewriting. The one under
"How git errors are classified" describes this feature as planned. The one on the merge ordering
describes push-before-graph-write as intended, and it shipped with IFC-1449, so the section it sits
in, "The writeback direction has no reconciliation", is stale around it. Its first bullet still
states that `InfrahubRepository.merge` writes the new commit to the graph before pushing. Its third
bullet, "Re-running the merge no-ops", still describes a local merge commit that stays on disk
after a rejected push, which the reset now removes, so a retry re-derives the merge and reaches the
push again. The paragraph below the bullets still says a merge commit "exists on exactly one
worker's disk". Only the second bullet, "Nothing ever re-pushes", stays accurate.
**Leave the other two alone.** They cover the trunk fallback (PR #10542) and the persisted
writeback state (IFC-3220). Rewriting those would claim two other fixes shipped.
