# Feature Specification: Multi-environment single-repo validation (Approach A)

**Feature Branch**: `multi-env-repo-tests`
**Created**: 2026-06-30
**Status**: Draft
**Input**: Validate the "Multi-environment Infrahub from a single Git repository" pattern (Approach A — read-only consumers) with automated tests, and reproduce the open multi-worker write-back defect (#9568) so it is caught and tracked.

## Overview

Teams want to run several Infrahub environments (dev / staging / prod) off **one** Git
repository, with one long-lived branch per environment and a git-native promotion path
between them — instead of a separate repository per environment. The recommended topology
for production ("Approach A") is: a **read-write development instance** pinned to a non-`main`
branch (e.g. `develop`), and **read-only consumer instances** pinned to their own branch,
receiving promoted changes through an explicit reimport.

This effort delivers automated confidence that Approach A behaves as documented, and a tracked
reproduction of the one defect known to break it in production — the silent loss of the git
write-back on multi-worker deployments (#9568). The audience is the engineering team adopting or
maintaining the pattern; "the system" under validation is Infrahub's git-integration behaviour.

## Clarifications

### Session 2026-07-01

- Q: For US2, use two real instances or a single instance with two repositories? → A: Two real
  instances (separate full stacks) sharing one Git remote — the faithful topology; the single-
  instance/two-repo form is explicitly rejected.
- Q: How should the full-stack multi-worker write-back reproduction (US1§2) express pass/fail? → A:
  Drop it — the #9568 signal comes solely from the deterministic prong (US1§1) that reconstructs the
  failing worker-clone state; no test runs a live multi-worker pool, and the full stack is used only
  for US2.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Multi-worker write-back defect is caught and tracked (Priority: P1)

A read-write development instance is configured with a non-`main` default branch and runs with
**more than one** worker (the realistic production scale, not the single-worker workaround). When a
change is merged inside Infrahub, the result must be written back to the environment branch on the
shared repository. Today this push is **silently lost on a subset of merges**, and Infrahub still
reports success. The team needs this defect demonstrably reproduced so it cannot regress unnoticed,
and so the demonstration flips to passing the moment the defect is fixed.

**Why this priority**: This is the active, unfixed defect that blocks the pattern from being
production-ready on multi-worker deployments. It is the most explicitly requested outcome, and the
reproduction has lasting value as a regression signal.

**Independent Test**: Reconstruct the failing worker-clone state (a clone holding only the local
primary branch plus remote-tracking refs, no local copy of the non-`main` default branch), perform a
write-back merge, and observe that the environment branch tip on the repository does not advance
while the operation reports success. Deterministic, zero-flake, and self-updating when the defect is
fixed.

**Acceptance Scenarios**:

1. **Given** a worker clone that holds only the local primary branch plus remote-tracking refs (the
   state of a worker that did not perform the initial import), **When** a merge writes back to the
   non-`main` default branch, **Then** the operation reports success but the branch tip on the
   repository does not advance. *(deterministic mechanism check)*
2. **Given** the defect is later fixed, **When** the same check runs, **Then** it passes without any
   change to the test.

---

### User Story 2 - Read-only consumer isolation and promotion (Priority: P1)

A read-only consumer instance is pinned to its own environment branch on the shared repository. It
must import only that branch onto its internal primary branch, remain isolated from the other
environments' branches, and pick up a promoted change only after an explicit, operator-initiated
reimport.

**Why this priority**: This is the core value of the pattern and the topology recommended for
production. Without it, "multiple isolated environments from one repository" is unproven.

**Independent Test**: Stand up a read-only consumer pinned to one branch alongside a development
instance working another branch on the same repository; assert the consumer sees only its branch,
that a promotion is invisible until reimport, and that reimport advances the consumer's recorded
commit. Delivers proof of per-environment isolation and controlled promotion.

**Acceptance Scenarios**:

1. **Given** a read-only consumer pinned to its environment branch, **When** it imports, **Then** its
   branch set contains only the internal primary branch — none of the other environments' branches.
2. **Given** the development instance advances its own branch on the shared repository, **When** the
   consumer is inspected, **Then** the consumer's recorded commit is unchanged (isolation holds).
3. **Given** a change is promoted onto the consumer's branch on the shared repository, **When** no
   reimport has occurred, **Then** the consumer's recorded commit is still the pre-promotion commit.
4. **Given** the same promoted change, **When** an explicit reimport is requested and awaited,
   **Then** the consumer's recorded commit advances to the promoted commit.

---

### User Story 3 - Non-`main` default branch imports without a phantom branch (Priority: P2)

The development instance configured with a non-`main` default branch must map that branch onto its
internal primary branch and must **not** create a duplicate standalone branch named after it.

**Why this priority**: This guards an already-fixed defect (#9600 / #9601). It is a regression guard
rather than new ground, so it ranks below the live defect and the core pattern — but the pattern is
not safe on a build that lacks the fix, so it must be locked in.

**Independent Test**: Configure a read-write instance with a non-`main` default branch, let it
import and run a periodic sync cycle, and assert the branch set is exactly the expected set with no
standalone branch matching the configured default. Delivers a regression guard for the fix.

**Acceptance Scenarios**:

1. **Given** a read-write instance whose default branch is non-`main`, **When** it imports and a
   post-activation sync cycle completes, **Then** the configured default branch maps onto the
   internal primary branch and no standalone branch named after the configured default exists.
2. **Given** the same instance, **When** a new commit lands on the configured default branch on the
   repository, **Then** the instance's recorded commit advances (the import is not frozen).

---

### User Story 4 - Resilience to git conflicts and branch divergence (Priority: P2)

Promotion, out-of-band pushes to a long-lived branch, and force-resets all create divergence and
conflicts on the shared repository. The pattern must degrade safely: a conflict on one branch must
not silently lose data, must not permanently poison that branch so it can never sync again, and must
surface as an error rather than hide. A genuine content conflict during a write-back merge must be
reported, not swallowed.

**Why this priority**: Conflicts and divergence are inevitable in a multi-environment, multi-writer
workflow. Whether they fail loud-and-recoverable or silent-and-permanent is the difference between a
pattern that is operable in production and one that strands an environment.

**Independent Test**: Induce divergence on a long-lived branch (out-of-band commit / force-reset) and
a genuine merge conflict, run the sync / write-back / merge paths, and assert each outcome is either
applied or surfaced as a failure — never silently dropped — and that a conflicted branch recovers
without manual worktree repair.

**Acceptance Scenarios**:

1. **Given** an instance's local copy of a long-lived branch has diverged from the shared repository
   (an out-of-band commit, or a force-reset of that branch), **When** the periodic sync pulls it,
   **Then** the divergence surfaces as an error for that branch and the branch recovers on a
   subsequent sync without manual worktree repair. *(current code is expected to leave the worktree
   in a permanent conflicted state — tracked as a known defect)*
2. **Given** the shared repository's default branch advanced out-of-band after an instance imported
   it, **When** an in-Infrahub merge writes back to that branch, **Then** the write-back either lands
   or is reported as failed — it is not silently dropped. *(distinct from the multi-worker
   write-back defect; current code silently drops the non-fast-forward push — tracked)*
3. **Given** an Infrahub branch whose changes genuinely conflict with the default branch, **When** it
   is merged, **Then** the conflict is surfaced as a failure and the worktree is left clean (the
   merge is aborted), not mid-conflict. *(regression guard for working behaviour)*
4. **Given** a failure confined to one branch, **When** the periodic sync runs, **Then** the other
   branches still import successfully. *(regression guard for per-branch failure isolation)*

---

### User Story 5 - The branch filter does not isolate fetch-time failures (Priority: P3)

Infrahub fetches the **entire** remote — every branch and tag — and only afterwards applies the
branch-name filter. A fetch-time problem on a ref the filter would exclude can therefore still break
the whole repository's sync. The pattern relies on the filter to bound which branches matter; this
story validates whether that boundary actually holds at fetch time.

**Why this priority**: This is a latent, surprising failure mode rather than a daily-workflow one,
and its precise triggering condition needs empirical confirmation — but if the filter is not a
blast-radius boundary, an unrelated, excluded branch can take a whole environment offline.

**Independent Test**: Introduce a fetch-time problem on a ref the filter excludes, then sync; assert
the in-filter branches still import. Delivers a clear answer on whether the filter isolates failures.

**Acceptance Scenarios**:

1. **Given** the filter excludes a branch, **When** the repository syncs, **Then** that branch is not
   imported as a standalone branch and is not required to be conflict-free for the sync to proceed.
2. **Given** a fetch-time problem on a ref excluded by the filter (e.g. a moved/clobbering tag),
   **When** the repository syncs, **Then** the in-filter branches still import successfully. *(current
   code fetches before filtering, so a fetch failure aborts the whole sync — tracked as a known
   defect, pending empirical confirmation of the exact triggering condition)*

---

### Edge Cases

- **Reimport before the promotion is visible**: a reimport requested before the promoted commit is
  present on the shared repository must not falsely advance the consumer's commit.
- **Merge before import settles**: merging an environment branch before its import has settled
  surfaces "branch not found"; the validation must await the branch's appearance, never assume it.
- **Default branch equals primary**: when the default branch is the primary branch, no mapping is
  required and the phantom-branch path must not trigger.
- **Legitimate no-op merge vs. silently dropped push**: a merge that correctly results in no change
  must be distinguished from a write-back that was silently lost — these are different mechanisms and
  must not be conflated.
- **Unreliable signals**: branch/commit assertions must not depend on the success return of the
  merge operation or on transient sync-status fields, both of which are known to be unreliable.
- **Out-of-band write to the default branch**: a direct push to the default branch on the shared
  repository between an instance's import and its write-back makes the write-back non-fast-forward —
  it must be surfaced or applied, never silently lost.
- **Force-reset of a long-lived branch**: resetting a long-lived branch to an unrelated history
  (e.g. `develop` reset to match `main`) creates a non-fast-forward divergence on the next pull.
- **Poisoned worktree after a conflicting pull**: a pull that conflicts must not leave the worktree
  mid-merge such that every subsequent sync of that branch fails on "unmerged files".
- **Fetch-time problem on an excluded ref**: a moved/clobbering tag or other fetch-time ref problem
  on a branch the filter excludes must not abort the sync of the in-filter branches.
- **Distinguishing the two silent-drop mechanisms**: a write-back lost because the executing worker
  lacks a local default branch (multi-worker) is a different cause from one lost to a
  non-fast-forward rejection; tests must not conflate them.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The validation MUST exercise Approach A topology as **two distinct Infrahub instances**
  (separate full stacks) — a read-write development instance on a non-`main` branch and a read-only
  consumer instance on its own branch — both backed by a single shared Git repository. A single
  instance hosting two repositories does not satisfy this requirement.
- **FR-002**: The validation MUST assert that the development instance imports its configured
  non-`main` default branch onto its internal primary branch with **no** duplicate standalone branch
  named after that default.
- **FR-003**: The validation MUST assert that the read-only consumer imports only its pinned branch
  and does not import the other environments' branches.
- **FR-004**: The validation MUST assert that a change promoted onto the consumer's branch is not
  reflected on the consumer until an explicit reimport, and that the reimport advances the consumer's
  recorded commit.
- **FR-005**: The validation MUST reproduce the multi-worker write-back defect by reconstructing the
  failing worker-clone state (a clone with the local primary branch plus remote-tracking refs but no
  local copy of the non-`main` default branch): a merge that should write back to the default branch
  is silently lost — the branch tip on the repository does not advance while the merge reports
  success. No test runs a live multi-worker pool.
- **FR-006**: The defect reproduction MUST be tracked so that it is expected-to-fail while the defect
  exists and automatically signals success once the defect is fixed, with no manual test change.
- **FR-007**: The validation MUST include a deterministic (zero-flake) reproduction of the
  write-back defect's mechanism that does not depend on which worker happens to handle the merge.
- **FR-008**: Branch- and commit-state assertions MUST rely on the authoritative branch list and the
  recorded commit, never on the merge operation's return value or transient sync-status fields.
- **FR-009**: Test progression MUST be driven by explicit triggers and observable-state polling, not
  fixed sleeps.
- **FR-010**: The heavy multi-instance reproduction MUST be runnable on demand and MUST be excluded
  from the default continuous-integration run; the deterministic mechanism check MUST run on every
  continuous-integration run.
- **FR-011**: The validation MUST mirror the repository's existing test conventions and harnesses
  rather than introduce a parallel testing framework.
- **FR-012**: The validation MUST cover divergence of a long-lived branch between an instance's clone
  and the shared repository (out-of-band commit or force-reset) and assert the outcome surfaces as an
  error and recovers on a later sync without manual worktree repair.
- **FR-013**: The validation MUST assert that a write-back blocked by a non-fast-forward remote (the
  default branch advanced out-of-band) is not silently dropped, and MUST keep this distinct from the
  multi-worker write-back loss.
- **FR-014**: The validation MUST assert that a genuine content conflict during an in-Infrahub merge
  surfaces as a failure with the worktree left clean.
- **FR-015**: The validation MUST assert that a failure confined to one branch does not prevent the
  other branches from importing.
- **FR-016**: The validation MUST assert whether a fetch-time problem on a ref excluded by the branch
  filter breaks the sync of in-filter branches; where current behaviour violates the desired
  isolation, the check is tracked as expected-to-fail.

### Key Entities *(include if feature involves data)*

- **Environment instance**: an Infrahub deployment dedicated to one environment (development or a
  read-only consumer), pinned to a single branch of the shared repository.
- **Shared Git repository**: one repository holding long-lived per-environment branches plus
  short-lived feature branches; the single source all instances read from.
- **Environment branch**: a long-lived branch (e.g. `develop`, `staging`, `main`) that maps onto an
  instance's internal primary branch.
- **Promotion**: advancing a change from one environment branch to the next on the shared repository.
- **Write-back**: the result of an in-Infrahub merge pushed back onto the repository's default branch.
- **Phantom branch**: an erroneous standalone branch duplicating the configured non-`main` default.
- **Divergence**: a state where an instance's local copy of a branch and the shared repository's copy
  have incompatible histories (an out-of-band commit or a force-reset), so a fast-forward is no longer
  possible.
- **Conflict**: overlapping changes that cannot be merged automatically, whether during a write-back
  merge or a branch pull.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every enumerated Approach A guarantee (consumer isolation, promotion-via-reimport,
  non-`main` import with no phantom) has a passing automated assertion — 100% coverage of the listed
  guarantees.
- **SC-002**: The multi-worker write-back defect is reproduced by a deterministic check (0% flake
  across repeated runs) that fails while the defect is present and passes once it is fixed.
- **SC-003**: The deterministic defect check and the regression guards run on every
  continuous-integration run within the normal integration-test time budget; the heavy multi-instance
  reproduction is opt-in and absent from the default run.
- **SC-004**: A reviewer can determine, from test results alone and without reading the test code,
  whether each documented Approach A guarantee holds and whether the write-back defect is still
  present.
- **SC-005**: When the write-back defect is fixed, its tracked reproductions turn to passing with no
  edits to the tests.
- **SC-006**: Every conflict/divergence scenario has an assertion that distinguishes a surfaced
  failure from a silent loss, and any scenario that exposes a suspected unfiled defect is tracked as
  expected-to-fail so it self-updates when fixed.

## Assumptions

- **Approach A only.** Read-only consumers are in scope; Approach B (all read-write, filtered,
  auto-synced consumers) is out of scope for this effort.
- **Two instances suffice.** A development instance plus one read-only consumer, as **two separate
  full stacks** sharing one remote; additional consumers (staging vs. prod) behave identically and
  are not separately modelled. The two-stack harness (a second stack + shared remote bind-mount) is
  accepted as in-scope work.
- **No live multi-worker pool.** #9568 is a multi-worker defect, but it is reproduced by
  reconstructing the failing worker-clone state deterministically rather than by running a real
  multi-worker pool (that full-stack demonstration was considered and dropped as too flaky to gate on).
- **The non-`main`-default import fix (#9601) is present** on the branch under validation; the
  no-phantom guarantee (User Story 3) is a regression guard for it.
- **The shared repository is a local Git remote provisioned for the validation**, with no dependency
  on an external Git host.
- **Out of scope, related but distinct**: artifact generation on a non-`main` default branch
  (#8749), and the merge-before-sync no-op write-back (#9499). The validation must not conflate the
  latter with the silently-dropped push under test.
- **Suspected unfiled defects to confirm.** Two behaviours surfaced from reading the code and are
  expected to fail today: (a) a divergent/conflicting branch pull leaves the worktree permanently
  conflicted (no abort/recover), and (b) the branch filter does not bound fetch-time failures (the
  whole repository is fetched before filtering). These are confirmed by the tests **first**; only a
  test-confirmed defect is then drafted as a GitHub issue using the issue-reporting skill, written to
  a **separate file per defect for the user's review** — never auto-submitted, and filed separately
  from the multi-worker write-back defect (#9568). The non-fast-forward write-back drop is already
  observable in the existing push-rejection behaviour.
