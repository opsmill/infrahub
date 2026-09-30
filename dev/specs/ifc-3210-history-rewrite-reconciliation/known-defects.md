# Review findings and how they were resolved

**Date**: 2026-09-30
**Status**: the eighteen findings of the fourth review pass are closed. Nothing is open.
**History**: four review passes, 66 findings fixed. See
[critiques/critique-20260929-1530.md](critiques/critique-20260929-1530.md).

This file was written when the fourth pass was handed over unfixed. It has since been worked
through. It is kept as the record of what that pass found and how each item was resolved, so a
reviewer can check the reasoning rather than take it on trust.

---

## The two blockers, and how they were resolved

### B1. The detector's input was never defined

**What it was.** The detector compares `imported_commit` against the remote head, and no document
said where `imported_commit` came from. The cron runs on any worker and `compare_local_remote`
reads that worker's own refs, so both candidate sources broke something. The local worktree head
made a stale worker classify `REWRITE` again and fire the trunk signal twice. The graph commit made
every worker except the reconciling one classify `UNCHANGED`, reset nothing, and keep the discarded
history.

**Resolution.** The design was asking one question where it needed two, and they are now separate:

| Question | Inputs | Drives | Who runs it |
|---|---|---|---|
| Was the history rewritten? | the commit **recorded in the graph**, against the remote head | the record and the trunk signal | whichever worker runs the cycle |
| Does this clone need to move? | this worker's **branch worktree head**, against the remote head | the reset | every worker, independently |

Both then come out right with no guard. The reconciling worker sees a stale graph commit and
records once. Every other worker sees a stale worktree, resets, and records nothing.

FR-001b and FR-001c state it. `contracts/internal-interfaces.md` section 1 carries the table and
names where the graph commit comes from: `RepositoryData.branches`, already loaded once per cycle,
passed down rather than re-read. The `pull` contract in section 3 already compared the worktree, so
that half needed no change once the question was named.

### B2. The merge guard covered the destination but not the source

**What it was.** FR-005a stopped a worker merging *onto* a stale destination worktree. It said
nothing about the source. `merge` reads the commit it merges from the local source ref
(`get_commit_value(..., remote=False)`) and nothing fetches first, so a worker holding a stale
source branch merges the pre-rewrite history into the trunk and **pushes it**. Discarded commits
return to the remote for everyone. A rewrite that removed a leaked credential would restore it.

**Resolution.** FR-005a now covers both worktrees, and FR-005b states the property plainly: never
push what the remote already discarded. The merge task fetches and checks the source branch and the
destination branch before merging, and a live-remote test asserts the discarded commits do not
reappear on the remote.

---

## The other findings

| Was | Resolution |
|---|---|
| Dropping the unconditional trunk broadcast removed today's heal in an ungated phase, while its replacement sat in a gated one | The "no branch advanced, no message" rule now ships **with** the pull-path reset, not before it |
| The read-only test force-moved a tag, which neither read-only fetch path force-updates, so it could never pass | The scenario is a force-pushed **branch**. IFC-2874 stays out of scope |
| Slice C was called gate-free although the widened broadcast resets every branch on every worker | Slice C is gated too. The gate is now stated as "every step that resets a worktree" |
| The commit-only re-point was suppressed in one file out of three | `data-model.md` and the task now list `commit` as a marker trigger alongside `ref` |
| The read-only side had no defined "imported" commit, and a concurrent pull could overwrite it first | Same rule as B1. The graph commit travels on the workflow model, read before either workflow can overwrite it |
| The record write lost its per-branch isolation in the task | Its own task. A failed record joins `failed_imports` instead of aborting collection for every branch |
| The MVP claimed to ship without #10465 while its core step was gated on it | Corrected. What ships before #10465 is the classification and the corrected message, which change no worktree |
| A Phase 3 test asserted Phase 5 behaviour | That test now asserts the message only. The reset assertion lives in Phase 5, its only home |
| The gated count said six; the range was seven | Gates name **phases** now, not id ranges, so renumbering cannot make them wrong again |
| The missing-object row was unreachable and ignored the marker | Moved above the ancestry rows, and split on `target_changed` so a re-target with a collected object is not recorded as a rewrite |
| Four task references went stale after a renumber, for the third round running | Task ids are gone from the contract files and the alignment check. They are named by what they do |
| R12 told an implementer to rewrite four volatile notes | Limited to the one that belongs to this feature. The other three belong to #10542, IFC-3220 and #10465 |
| The handler unit test needed injected collaborators nobody had planned | Its own task, before the test |

---

## What is still open, and it is not a defect

Five decisions belong to a person, not to this document:

1. Which consumer receives the trunk-rewrite event.
2. Sign-off on the four schema attributes and their GraphQL fields ("Ask First" under `AGENTS.md`).
3. Merge order against PR #10542, which rewrites `git/base.py`.
4. Whether the read-only phase waits for PR #10669.
5. Confirmation of the reworded SC-006, where the epic asks for a repository view and also puts
   every display surface out of scope.

`plan.md` lists them with the reasoning.

---

## The one lesson worth keeping

Three of the four design holes across all passes, and both blockers, came from reasoning about a
function without following what calls it. "Every path goes through `pull`", "the recorder can run
after the import", "the merge destination is the only stale worktree" — each is a claim a
call-graph check disproves in minutes.

The second recurring failure was narrower and dumber: changing a decision in one file and leaving
it stated the old way in the other six. `AGENTS.md` already says to grep the whole spec directory
when a decision changes. Doing that from the start would have removed most of two review rounds.
