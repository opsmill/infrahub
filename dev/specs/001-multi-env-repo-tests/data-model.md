# Phase 1 Data Model: test topology & defect-state

This feature adds tests, not product data; the "model" here is the **test topology** (the entities a
test constructs) and the **defect-state model** (how a tracked defect maps to a test outcome).

## Test topology entities

### SharedRemote
The single Git remote all instances read from.
- **fields**: path (local dir), bare (bool — true for the write-back remote), branches, tags.
- **branches**: `main` (primary), `develop` (== dev environment branch), `feature/*` (short-lived).
- **rules**: must be writable by the development instance's write-back (Decision 5). One remote per
  test scenario; never shared across scenarios (isolation between tests).

### EnvironmentInstance
An Infrahub instance pinned to one environment branch. US2 uses **two** of these as separate full
stacks sharing one remote (clarified 2026-07-01).
- **fields**: role (`development` | `consumer`), repo_kind (`CoreRepository` |
  `CoreReadOnlyRepository`), pin (`default_branch=develop` for development; `ref=<branch>` for
  consumer).
- **rules**: `default_branch`/`ref` set **at creation** (never updated after). Development instance
  writes back; consumer never writes back. No instance runs a multi-worker pool (the #9568 mechanism
  is reconstructed, not run live).

### EnvironmentBranch
A long-lived branch mapped onto an instance's internal primary branch.
- **mapping**: `branch == instance.default_branch && branch != primary` ⇒ maps to primary; else
  identity. A consumer pinned via `ref` imports only that branch onto primary.
- **invariant**: no standalone Infrahub branch named after a non-primary `default_branch` (no phantom).

### WorkerClone
The local clone state that a task-worker would have — **reconstructed directly** in the deterministic
prong (no live worker pool is run).
- **states**: `importer` (has local `<default>` branch) | `non-importer` (local primary +
  `origin/<default>` only). The non-importer state is the precondition for the write-back defect and
  is what the deterministic check builds by hand.

### PromotedChange / WriteBack
- **PromotedChange**: a commit advanced onto a consumer's branch on the SharedRemote; visible to the
  consumer only after an explicit reimport.
- **WriteBack**: the result of an in-Infrahub merge pushed to the SharedRemote's default branch.

## Defect-state model (test outcome mapping)

| Tracked behaviour | Spec ref | Current expectation | Test marker | Flips when |
|---|---|---|---|---|
| Multi-worker write-back drop | US1 | broken (confirmed) | `xfail(strict)` | #9568 fixed → XPASS surfaces |
| Divergent-pull recovery | US4§1 | **working (refuted defect)** | green guard | regression → fail |
| Non-ff write-back drop | US4§2 | broken (confirmed) | `xfail(strict)` | fixed → XPASS |
| Fetch-before-filter blast radius | US5§2 | broken (predicted) | `xfail(strict)` | fixed → XPASS |
| No phantom on non-main default | US3 | working | green | regression → fail |
| In-merge conflict surfaced + aborted | US4§3 | working | green | regression → fail |
| Per-branch failure isolation | US4§4 | working | green | regression → fail |
| Consumer isolation + promotion-via-reimport | US2 | working | green | regression → fail |
| Filter excludes a branch | US5§1 | working | green | regression → fail |

**Rule**: every `xfail(strict)` carries a behaviour-describing `reason` (no issue IDs in test
source). A predicted-broken behaviour is only drafted as an issue after its test actually fails as
predicted (Decision 7).
