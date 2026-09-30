# Data Model: Git history-rewrite reconciliation

**Feature**: `dev/specs/ifc-3210-history-rewrite-reconciliation`
**Date**: 2026-09-29

> **Governance**: everything in the "Schema changes" section is an "Ask First" change under
> `AGENTS.md`. It is a database schema change, and the attributes surface on three GraphQL node
> kinds. The design below is complete, but it needs a maintainer's sign-off before implementation.

---

## Schema changes

### Four attributes on `CoreGenericRepository`

Declared in `backend/infrahub/core/schema/definitions/core/repository.py`, on the generic only.
`CoreRepository` and `CoreReadOnlyRepository` inherit them and must not override them.

| Name | Kind | Optional | Default | Branch support | Meaning |
|---|---|---|---|---|---|
| `last_rewrite_previous_commit` | `Text` | yes | none | `LOCAL` | The commit Infrahub had imported on this branch before the reconciliation. |
| `last_rewrite_commit` | `Text` | yes | none | `LOCAL` | The commit Infrahub reconciled onto. |
| `last_rewrite_at` | `DateTime` | yes | none | `LOCAL` | When the reconciliation completed. |
| `rewrite_count` | `Number` | yes | none | `LOCAL` | How many reconciliations are visible on this branch, cumulative. See "What LOCAL does not do" below: a branch inherits the count of the branch it forked from. |

Order weights place them after `sync_status` and before the relationships, so the repository form
groups the synchronisation state together.

#### Why each choice

- **`LOCAL`**: a LOCAL attribute never reaches a branch diff and can never produce a merge conflict.
  The diff query selects `branch_support IN [aware, agnostic]`, and the bulk merge touches only
  `aware`. This satisfies FR-012 by declaration. It also makes the value per branch, which FR-010
  requires.
- **Optional with no default**: no existing repository needs a value, so no data migration and no
  `GRAPH_VERSION` bump are needed.
- **Four scalars, not one structured value**: a structured value would be a large attribute kind, it
  would not be server-side queryable, and it would not sort or validate. The branch-list and
  cross-branch status work of INFP-671 both need to query these server-side.
- **`Number` for the count, not `Text`**: it sorts and validates. Note the GraphQL convention in
  this codebase: number attributes use `BigInt` in queries and mutations, not `Int`.

#### Invariants

1. The four values are written together, in one mutation, or not at all.
2. `last_rewrite_previous_commit` and `last_rewrite_commit` are never equal. A reconciliation that
   would write equal values is a bug in the classifier, and the recorder rejects it.
3. `rewrite_count` only increases. It is read, incremented by one, and written back inside the
   repository lock.
4. The system never clears any of the four (FR-011). Nothing in the product resets them.
5. A `RETARGET` classification writes none of them (FR-002, SC-007).
6. A worker that reset itself from its own pull path writes none of them (FR-007).

#### What LOCAL does not do

**LOCAL isolates writes, diffs and merges. It does not isolate reads.**
The branch read path resolves a branch against its origin branch as of `branched_from`
(`core/branch/models.py::Branch.get_branches_and_times_to_query_global` on the production path,
`get_branches_and_times_to_query` for the non-global variant), so a read on a branch falls back to
the branch it forked from. A branch created after the default branch was reconciled therefore reads
the default branch's four values, and its own first reconciliation increments a count it inherited.

**A rebase does the same thing, later.** `Branch.rebase` moves `branched_from` forward to the
rebase time, so a branch that had no record of its own starts reading whatever the default branch
recorded in the meantime.

This is not a defect to fix here. It is exactly how the `commit` attribute beside it already
behaves, and it is the right answer for `commit`: a new branch starts at the trunk's commit. The
same inheritance is defensible for the record, because a branch forked from a rewritten history did
inherit that rewrite.

**Clearing the four values when a branch is created is rejected.** It would add a write to every
branch creation, on a path that has nothing to do with git repositories, to fix a reading that is
arguably correct. Principle VII.

**What it costs, stated plainly**: `rewrite_count` means "reconciliations visible on this branch",
not "reconciliations of this branch". `last_rewrite_at` on a young branch can predate the branch.
A test asserts the inheritance so nobody discovers it in production.

**`commit` inherits the same way, and that one is a defect.** `git_branch_create` never writes the
new branch's commit, so a branch reads the trunk's value as of its fork point. The classifier would
then compare a branch's remote head against an unrelated trunk commit. Branch creation writes the
commit, which is a task of its own.

#### What they do not do

- They are not folded into `sync_status` (FR-013). `sync_status` keeps its current meaning and stays
  free to be redefined by INFP-671.
- They do not change `operational_status`, which describes whether the remote is reachable.
- They introduce no new node kind and no new relationship.

### The read-only asymmetry

`CoreReadOnlyRepository` overrides `commit` and `ref` to `AWARE`. The four new attributes are not
overridden, so they stay `LOCAL` on that kind as well. A read-only repository therefore carries a
diff-invisible rewrite record beside a diff-visible `commit`.

This is deliberate. FR-012 is unconditional, and correcting the `commit` and `ref` overrides is
listed out of scope in `spec.md`. A branch-safety test asserts the absence of the four attributes
from a diff on both repository kinds, so the asymmetry cannot regress silently.

---

## New in-process types

These are backend types, not schema. They carry no persistence.

### `RefClassification`

A `StrEnum` in `backend/infrahub/git/divergence/models.py`.

| Member | Meaning |
|---|---|
| `UNCHANGED` | The remote head equals the imported commit. |
| `FAST_FORWARD` | The imported commit is an ancestor of the remote head. |
| `LOCAL_AHEAD` | The remote head is an ancestor of the imported commit. The local copy holds commits the remote does not. |
| `REWRITE` | Neither commit is an ancestor of the other, and the tracking target did not change. |
| `RETARGET` | Neither commit is an ancestor of the other, and the tracking target changed. |
| `REMOTE_ABSENT` | The remote carries no such ref any more. |

It is an enum and not a boolean because Principle III requires that `REWRITE` and `RETARGET` cannot
collapse into each other at a call site.

**`LOCAL_AHEAD` is load-bearing, not a completeness exercise.** A branch left ahead of its remote is
a state the product reaches today: after a rejected push the local branch sits ahead of `origin/`,
`compare_local_remote` flags it every cycle, and `pull` returns `True` with no change. Without this
member, "neither is an ancestor" would swallow that case, classify it `REWRITE`, and reset the
branch onto the remote — discarding the very commit PR #10465 exists to protect. `LOCAL_AHEAD`
resets nothing and records nothing, so the current behaviour is preserved exactly.

It also closes a documented defect on its own: `dev/knowledge/backend/git-integration.md` lists "a
branch left ahead of its remote is re-reported every cycle" under Known limitations. A branch
classified `LOCAL_AHEAD` needs no pull, so the once-a-minute log line stops.

### `RefDivergence`

A frozen dataclass. What one classification decided, for one branch.

| Field | Type | Meaning |
|---|---|---|
| `branch_name` | `str` | The remote branch, or the tracked ref for a read-only repository. |
| `infrahub_branch_name` | `str` | The Infrahub branch the remote branch maps onto. |
| `imported_commit` | `str \| None` | What Infrahub had. `None` when the branch was never imported. |
| `remote_head` | `str \| None` | What the remote publishes now. `None` when the remote carries no such ref. |
| `classification` | `RefClassification` | The decision. |

Validation:

- `REWRITE`, `RETARGET` and `LOCAL_AHEAD` all require both commits to be set.
- A branch with no imported commit can only be `UNCHANGED` or `FAST_FORWARD`.
- A `None` `remote_head` can only be `REMOTE_ABSENT`, or `UNCHANGED` when the branch was never
  imported either.

### `ReconciledBranch`

A frozen dataclass. One branch a synchronisation cycle advanced, and the commit it advanced to.
This is what the widened broadcast carries and what the recorder consumes.

| Field | Type | Meaning |
|---|---|---|
| `infrahub_branch_name` | `str` | The Infrahub branch. |
| `infrahub_branch_id` | `str` | The branch UUID, not the database element id. A worker missing the worktree creates it under whatever it is given. |
| `commit` | `str` | The commit the cycle pinned. |
| `divergence` | `RefDivergence \| None` | Set when the branch was reconciled from a rewrite, `None` for an ordinary fast-forward. |

---

## Message change

### `RefreshGitFetch`

In `backend/infrahub/message_bus/messages/refresh_git_fetch.py`. One new optional field.

| Field | Type | Status | Meaning |
|---|---|---|---|
| `branches` | `tuple[BranchCommitPair, ...] \| None` | new, optional | Every branch this message converges, with the commit each is pinned to. |

`BranchCommitPair` carries `infrahub_branch_name`, `infrahub_branch_id` and `commit`.

The existing `infrahub_branch_name`, `infrahub_branch_id` and `commit` fields stay, and a coalesced
message still populates them from its first pair. The first two are required, so a message that
left them empty could not be constructed by a worker running the previous code. Five emission sites
use them and are untouched by this epic. The handler prefers `branches` when present and falls back
to the single-branch fields otherwise.

Under one lock acquisition and one fetch, the handler resets each pair in turn. This is why the
list is coalesced rather than sent as N messages: the repository lock is contended by merges and
by other synchronisations.

---

## New event

### `RepositoryHistoryRewrittenEvent`

In `backend/infrahub/events/repository_action.py`, beside `CommitUpdatedEvent`.

- `event_name`: `infrahub.repository.history_rewritten`
- New `EventType` member in `backend/infrahub/core/constants/__init__.py`, which puts it in the
  `event_type` enum of `CoreStandardWebhook` and `CoreCustomWebhook`.

| Payload field | Type | Meaning |
|---|---|---|
| `repository_id` | `str` | The repository. |
| `repository_name` | `str` | Its name. |
| `previous_commit` | `str` | The commit Infrahub had. |
| `commit` | `str` | The commit it reconciled onto. |
| `rewrite_count` | `int` | The new cumulative count for this branch. |

Resource labels follow `CommitUpdatedEvent`: `prefect.resource.id` is
`infrahub.repository.<repository_id>`, plus the repository name, the repository id and the branch
name.

**Emission rule** (FR-014): exactly one per rewrite of the repository's configured default branch.
No emission for any other branch. Emitted by the recorder, after a successful record.

**Exactly once across cycles** (SC-002): after the reset and the re-import, the recorded commit
equals the remote head, so the next cycle classifies `UNCHANGED`. The single emission follows from
the classification, not from a guard.

---

## Cache key

### The re-target suppression marker

Written by `graphql/mutations/repository.py::InfrahubRepositoryMutation.mutate_update`, read and
deleted by the component that calls the detector. See `research.md` R4 for why this shape was
chosen, and why the recorder must not be the reader.

| Property | Value |
|---|---|
| Key | Repository id plus Infrahub branch name, under a namespace of its own. |
| Value | The new tracking target, for diagnostics only. |
| Time to live | One hour. |
| Written when | `CoreRepository.default_branch` changes. Read-write repositories only: a read-only re-point travels in band on the workflow model. The write lands after the update succeeds and before any workflow is submitted. |
| Read by | The detector's caller in the sync path, `collect_pending_imports`, and nothing else. |
| Read when | Before every classification, not only before a `REWRITE`. |
| Effect | Makes `target_changed` true, so the detector returns `RETARGET`. The branch is still reset onto the remote head; only the record is skipped. |
| Consumed | Yes, but only after the commit write for that branch succeeds. Deleting at classification time would lose the marker to a failure in the reset, the write or the import, and the next cycle would record a false rewrite and fire a false trunk webhook. |

**The recorder must not read this key.** It returns early on any classification other than
`REWRITE`, so on a `RETARGET` it would never reach the read and never consume the marker. The
marker would then survive its full hour and suppress the next genuine rewrite of that branch.

---

## What is not changed

| Thing | Why |
|---|---|
| `operational_status` | It describes whether the remote is reachable. That is a different phase. |
| `sync_status` | FR-013 keeps it out of the record. INFP-671 may redefine it. |
| `internal_status` | Unrelated to reconciliation. |
| `commit` on any kind | The reconciled commit is recorded the way every other commit is. |
| `NodeMutationOrigin` | No new member. Not because the trigger builders would need changing, they match `live` explicitly and ignore a new value for free, but because the SDK mutation that writes the record always stamps `live`. See `research.md` R6. |
| The SDK (`python_sdk`) | The recorder writes through the SDK node API, so no submodule change and no second PR. |
