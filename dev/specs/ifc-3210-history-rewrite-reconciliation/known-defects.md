# Known defects in this spec set

**Date**: 2026-09-30
**Status**: open, not fixed
**Source**: fourth code-aware review pass (cubic, 275 repo learnings, 5 custom agents)

This design went through four review passes: one document critique and three code-aware runs. The
first three rounds' findings were fixed and are recorded in
[critiques/critique-20260929-1530.md](critiques/critique-20260929-1530.md). This file holds what
the fourth round found. **None of it is fixed.**

The decision to stop fixing was deliberate. The counts were 12, 14, 23, 18. Each round went a
layer deeper rather than mopping up the last one, and the fourth round found the most fundamental
problem of all. Grinding further would keep trading review cycles for a design that needs two
decisions from a person, not more editing.

Read the two blockers before anything else. They are not defects to work around; they are
unresolved design questions.

---

## Blockers

### B1. The detector's `imported_commit` is never defined, and neither candidate works

**Where**: the whole design. `contracts/internal-interfaces.md` section 1, `research.md` R1 and R2.

The detector compares `imported_commit` against `remote_head`. No document says where
`imported_commit` comes from in the sync path. Both available sources break something, because the
periodic cron runs on **any** worker and `compare_local_remote` compares that worker's own local
refs.

| Source | What breaks |
|---|---|
| The worker's local branch head | A worker that missed the broadcast classifies `REWRITE` again on the next cycle. It writes a second record, increments the count and fires the trunk signal a second time. Breaks SC-002 ("exactly one record and one signal however many cycles elapse") and FR-014. |
| The commit recorded in the graph | After the first reconciliation the graph already holds the new commit, so the classification is `UNCHANGED`, which the contract table maps to "no reset". That worker's clone stays on the discarded history for ever. |

**The likely resolution, not yet designed.** These are two different questions that the spec
conflates into one comparison:

- *Has the history been rewritten?* — graph commit against remote head. Drives the record and the
  signal. Belongs to whichever worker runs the sync.
- *Does this worker's clone need to move?* — local worktree head against remote head. Drives the
  reset. Belongs to every worker independently.

Splitting them probably fixes B1 and makes FR-005 fall out naturally. It also changes the
classification contract, the recorder's placement and several tests, so it is a design change and
not an edit.

### B2. The merge guard covers the destination but not the source

**Where**: `spec.md` FR-005a, task T032.

FR-005a was added in the third round to stop a worker merging onto a destination worktree whose
history the remote discarded. It does not cover the **source** side.
`InfrahubRepository.merge` reads the source commit from the local branch ref
(`get_commit_value(..., remote=False)`), and `merge_git_repository` performs no fetch.

So a worker that missed the broadcast for a rewritten feature branch merges the **old source
history** into the trunk and pushes it. Commits a rebase removed are put back on the remote. If the
rebase existed to remove a leaked credential, this restores it.

That makes B2 the most serious finding in four rounds. FR-005a needs to cover both sides of a
merge, or the merge path needs to refuse to run on any branch it has not just verified against the
remote.

---

## Correctness gaps

### D1. Dropping the unconditional trunk broadcast removes today's healing early

Today `sync_repository_from_origin` sends the pinned trunk commit **every cycle**, even when
nothing changed. That is what heals a worker which missed an earlier broadcast, within a minute.

The contract's "when the cycle advanced no branch, no message is sent" removes it. That change sits
in Phase 4, which is not gated. Its replacement — the pull-path self-heal — is Phase 5, which is
gated on PR #10465. Between the two, a stale worker stays stale and its merges fail on a
non-fast-forward push. No document names this as a behaviour change.

### D2. The read-only test cannot pass as written

User Story 5's independent test, T058 and the quickstart all force-move a **tag** that a read-only
repository tracks. Both read-only fetch paths leave an existing moved tag alone: the plain
`fetch()`, and `--tags` without `--force`. So no lineage break is ever observed.

`spec.md` "Out of Scope" names IFC-2874 as the fix for exactly this, and puts it outside this work.
Either the scenario becomes a force-pushed tracked branch, or IFC-2874 becomes a dependency.

### D3. Slice C is called gate-free but performs a hard reset

`plan.md` says slices other than B and D need no #10465 gate because they "never reset anything".
Slice C does: T024 makes the convergence handler run `reset_to_commit` for every pair on every
other worker, where today it does so for the trunk only. `InfrahubRepository.rebase` merges into
non-trunk branches and pushes, so without #10465 an unpushed merge commit can sit on a
feature-branch worktree that the widened broadcast would discard.

### D4. The commit-only re-point is suppressed in one file out of three

`contracts/internal-interfaces.md` section 8 lists a change of `CoreReadOnlyRepository.commit` as a
marker trigger, because SC-007 covers "branch, tag **or commit**". Task T060 writes the marker only
for a `ref` change, and the "Written when" row in `data-model.md` also omits `commit`. A
commit-only re-point therefore records a false rewrite. The third round's log claims this was
fixed; it was fixed in one file.

### D5. The read-only side has no defined "imported" commit

`update_latest_commit` resolves only the new head. `import_read_only_repository_last_commit` calls
`init` without a commit, so nothing loads the previously imported one. The mutation also submits
`pull_read_only` concurrently, and that flow can write the new commit to the graph first. Which
commit plays the "imported" role on the read-only path is undefined and depends on timing. This is
B1 again, in the read-only path.

### D6. The record write loses its per-branch isolation in the task

`contracts/internal-interfaces.md` section 2 requires the record write to be isolated per branch,
because `collect_pending_imports` lets graph errors propagate. Task T042 places the call without
saying so. An SDK error from the store would abort collection for every branch and skip the
broadcast.

---

## Sequencing contradictions

### S1. The MVP claim contradicts its own gate

"Implementation strategy" says Phases 1 to 3 fix the reported bug without PR #10465. T015's reset —
the step that actually reconciles a rewritten branch — is gated on #10465 by the gate table,
`plan.md` and T015's own text. The increment either needs the gate or does not fix the bug.

### S2. A Phase 3 test asserts Phase 5 behaviour

T019 rewrites `test_pull_branch_conflict` to expect `pull` to reset a diverged branch without
raising. That reset is built by T032, in gated Phase 5. In Phase 3 `pull` still raises, so T019
fails. T036 also duplicates the same assertion.

### S3. Wrong count of gated items

"T032 to T038, plus the reset inside T015. Six items." T032 to T038 is seven tasks, so the total is
eight.

---

## Contract and reference errors

### C1. The missing-object row is unreachable and ignores the marker

The classification table says first match wins, but the missing-object row sits **after** the
ancestry rows, which cannot run when the object is missing. The row also maps to `REWRITE`
regardless of `target_changed`, so a deliberate re-target with a missing object records a false
rewrite and consumes its marker.

### C2. Four task references are wrong after the last renumber

| Where | Says | Should be |
|---|---|---|
| `contracts/internal-interfaces.md` §1 | T013 sends the branch to `failed_imports` | T014 |
| `contracts/internal-interfaces.md` §2 | the reset path of T014 writes the commit | T015 |
| `contracts/internal-interfaces.md` §2 | the unit tests of T040 | T044 |
| `alignment-check.md` F7 | the E2E task is T069 | T074 |

This is the third round in a row that prose references drifted after tasks were renumbered. The
renumbering script rewires ranges and bare ids inside `tasks.md` only; references in the other six
files are not touched.

### C3. R12 still tells an implementer to rewrite four volatile notes

Task T070 correctly limits the rewrite to the single note under "How git errors are classified".
`research.md` R12 still names all four, and the other three belong to PR #10542, IFC-3220 and
PR #10465. Following R12 would claim three other people's fixes shipped.

### C4. The handler unit test needs a refactor nobody planned

T029 asks for a fan-out unit test with a fake lock registry and no mocks. The `fetch` handler reads
the module-global `lock.registry` and calls `get_initialized_repo(get_client())`. Injecting those
collaborators is a change to the handler that T024 does not include.

---

## What to do with this

1. **B1 and B2 need a decision before implementation starts.** B1 changes the classification
   contract. B2 is a security-relevant hole in a requirement added two rounds ago.
2. The rest can be absorbed during implementation, provided this file travels with the spec.
3. The four wrong task references in C2 will keep recurring until the renumbering step also
   rewrites references in the sibling files, or until tasks stop being renumbered.

## Honest note on the review history

Four passes, 48 findings fixed, 18 still open. The trend in the counts (12, 14, 23, 18) shows the
reviewer going deeper rather than the design converging. The fourth pass found the most fundamental
problem in the whole design, which suggests a fifth would find more.

Three of the four design holes in the previous round, and both blockers here, share one cause: the
design was written by reading functions in isolation instead of following which code calls which.
"Every path goes through `pull`", "the recorder can run after the import", "the merge destination
is the only stale worktree" — each is the kind of claim a call-graph check disproves in minutes.
