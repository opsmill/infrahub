# Implementation Plan: Git history-rewrite reconciliation

**Branch**: `history-rewrite-reconciliation-ifc-3210` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

**Branches from**: `develop`

**Input**: Jira epic IFC-3210. PRD: Notion `992228b83025825990bc011568cc2f4b`, Confluence 896466945.

## Summary

Infrahub compares a tracked ref's remote head to the imported commit by equality. It therefore
cannot tell a fast-forward from a rewritten history. A rewritten branch fails to pull, the failure
is reported as a merge conflict that does not exist, the branch stays stuck, and the failure
suppresses the worker-convergence broadcast for the whole repository.

This plan replaces the equality test with an ancestry classification, resets a diverged branch to
the remote instead of failing, moves the same reset into every worker's own pull path so
convergence does not depend on a broadcast, widens the broadcast to cover every reconciled branch
and sends it before a failed branch aborts the cycle, and records the event as four branch-local
attributes on the repository generic. A rewrite of the configured default branch also emits one
event that a webhook can subscribe to.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, Pydantic 2.12, GitPython, Prefect, `infrahub_sdk`

**Storage**: Neo4j through the Infrahub schema layer. Git worktrees on each worker's own disk.

**Testing**: pytest 9.0. Unit tests without a database. Component and integration tests through
testcontainers. The Gogs-backed live-remote harness, already on `develop`.

**Target Platform**: Linux server, multi-worker

**Project Type**: backend service

**Performance Goals**: the detection cost is one ancestry test per changed ref per cycle. Changed
refs are already the exception. The reconciliation cost is one reset and one re-import per
rewritten branch, both of which already exist as operations.

**Constraints**: the repository lock is the most contended lock in the git subsystem. The widened
broadcast must stay at one message and one lock hold per repository per cycle.

**Scale/Scope**: thirteen existing backend modules touched, plus one new package of seven files
(`models`, `detector`, `gateway`, `recorder`, `store`, `suppression`, `__init__`). Beyond the tree
below that is `events/__init__.py`, which exports the new event, `exceptions.py`, which gains the
divergent-history error, and `git/models.py`, which gains the in-band re-point flag. No frontend
work. The task count is in the table at the end of [tasks.md](tasks.md).

## Constitution Check

*GATE: passed before Phase 0 research, re-checked after Phase 1 design.*

| Principle | Assessment |
|---|---|
| **I. Schema-Driven Integrity** | Pass. The four attributes are declared in the schema layer. The generated schema, protocols and GraphQL schema are regenerated, never hand-edited. |
| **II. Branch-Safe by Default** | Pass, and it is the central design decision. `BranchSupportType.LOCAL` makes the record per branch, diff-invisible and never merged. The principle requires that merge behaviour be specified and tested rather than assumed, so a dedicated branch-safety test asserts it. |
| **III. Type Safety & Explicit Contracts** | Pass. The detector returns a six-member enum, not a boolean, so that `REWRITE`, `RETARGET` and `LOCAL_AHEAD` cannot collapse at a call site. The last of those is the one that would discard a user's unpushed commit if it collapsed into `REWRITE`. The message change and the new event are Pydantic models. |
| **IV. Test Discipline** | Pass. Three modules are unit-testable without a database, which is what makes the no-mocking rule practical. Every other test uses testcontainers. |
| **V. Query Performance** | Pass. One extra graph read per rewritten branch, on a rare path. No new query pattern. |
| **VI. Security & Input Boundaries** | Pass. No new mutation, no new permission. Read access to the record follows read access to the repository. |
| **VII. Simplicity & Maintainability** | Pass with one note. No new node kind, no new state machine, no new persistence mechanism. Four alternatives were rejected on this principle: a structured attribute, a rewrite log with retention, a resolved or acknowledged lifecycle, and pinning orphaned commits to preserve re-derivation. The note is the cache-based suppression marker of `research.md` R4, which is new coordination state. Its justification and its accepted failure mode are recorded there. |

### Governance gates crossed

| Gate | Status |
|---|---|
| Database schema or migration change | **Yes.** Four branch-local attributes on the repository generic. Optional with no default, so no data migration and no `GRAPH_VERSION` bump. **Needs sign-off.** |
| GraphQL schema modification | **Yes.** Two of them. The four attributes surface on three repository node kinds, and the new `EventType` member is added to the `event_type` enum of `CoreStandardWebhook` and `CoreCustomWebhook` through `EventType.available_types()`. Both **need sign-off**. |
| New dependency | No |
| CI/CD workflow change | No |
| Authentication or authorization change | No. No new mutation. The record is readable by anyone who can read the repository. |

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-3210-history-rewrite-reconciliation/
├── spec.md
├── plan.md                      # this file
├── research.md
├── data-model.md
├── quickstart.md
├── alignment-check.md
├── contracts/
│   ├── repository_rewrite.graphql
│   └── internal-interfaces.md
├── checklists/
│   └── requirements.md
├── critiques/
│   └── critique-20260929-1530.md
└── tasks.md                     # written by the tasks phase
```

### Source code

```text
backend/infrahub/
├── git/
│   ├── divergence/                      # NEW
│   │   ├── __init__.py
│   │   ├── models.py                    # RefClassification, RefDivergence, ReconciledBranch
│   │   ├── detector.py                  # RemoteDivergenceDetector
│   │   ├── gateway.py                   # the ancestry question, the only git code here
│   │   ├── recorder.py                  # HistoryRewriteRecorder
│   │   ├── store.py                     # the SDK-backed RepositoryRecordStore
│   │   └── suppression.py               # the re-target marker, read and consume
│   ├── base.py                          # pull(): reset only when neither head is an ancestor
│   ├── repository.py                    # collect_pending_imports(): classify updated branches
│   ├── sync.py                          # RepositorySyncer.sync(): return the outcome
│   └── tasks.py                         # broadcast every reconciled branch, before the raise
├── core/schema/definitions/core/
│   └── repository.py                    # the four attributes
├── core/constants/__init__.py           # the new EventType member
├── events/repository_action.py          # RepositoryHistoryRewrittenEvent
├── graphql/mutations/repository.py      # write the suppression marker
├── message_bus/
│   ├── messages/refresh_git_fetch.py    # the branches field
│   └── operations/git/repository.py     # the handler reads the list
└── core/schema/generated/               # regenerated, never hand-edited

backend/tests/
├── unit/git/divergence/                 # detector, recorder, models. No database.
├── unit/message_bus/                    # the handler's fan-out over N pairs
├── component/git/                       # the sync path, the pull path, branch safety
└── integration/git/                     # the Gogs live-remote scenarios
```

**Structure Decision**: the new code lives in one package, `backend/infrahub/git/divergence/`, with
the git calls isolated behind a gateway. This mirrors the shape PR #10669 uses for
`backend/infrahub/git/refs_check/`, so a reviewer who has read one can read the other. The
detector, the recorder and the models import no git library, which is what makes them unit-testable
without a database.

## Delivery order

Each slice is independently testable and delivers value on its own.

| Slice | User story | Depends on |
|---|---|---|
| **A. Classify** | Foundation for US1 | Nothing |
| **B. Reconcile in the sync path** | US1 | A |
| **C. Broadcast every branch, before the raise** | US3 | B |
| **D. Self-heal in the pull path** | US2 | A |
| **E. Record the event** | US1 | A, and schema sign-off |
| **F. Signal a rewritten trunk** | US4 | E |
| **G. Read-only detection** | US5 | A, E, H |
| **H. Re-target suppression** | US6 | E |
| **I. Documentation** | — | B, C, D, E |

### Why every reset in this plan is safe

Slices B, C and D reset a branch onto the remote head. The one state that would make such a reset
lossy is a merge commit that exists on a single worker's disk and nowhere else.

`InfrahubRepository.merge` no longer leaves that state. It pushes the merge commit, then records
it, and resets the destination worktree to its pre-merge commit when either step fails. A rejected
push leaves the destination either at its pre-merge state, where a later attempt re-derives the
merge, or trailing the remote, which the periodic synchronisation repairs. That ordering arrived
with IFC-1449.

`LOCAL_AHEAD` carries its own weight on top of that. A branch merely ahead of its remote classifies
`LOCAL_AHEAD` and no slice resets it, so an unpushed commit from any other source is preserved too.
Keep the row: it is a correctness rule in the detector, not a workaround for the merge path.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| **PR #10542 (IFC-3105) rewrites `git/base.py`.** | A rebase conflict in `pull` and in the error classifier, the two places slice D and slice A touch. | Patrick owns both branches. Agree the merge order before slice D starts. #10542 removes the trunk fallback this epic would otherwise inherit, so landing it first is the better order. |
| **The suppression marker is lost.** | A deliberate re-target is recorded as a rewrite, the count goes one too high, **and the trunk signal fires**, so whatever a customer has wired to that webhook receives a security-remediation notice for an ordinary configuration change. | Accepted and documented. The reconciliation is identical either way. A test covers the marker being present; a second test covers it being absent, and asserts the record is written, so the behaviour is stated rather than assumed. |
| **The widened broadcast increases lock contention.** | Slower merges and syncs under load. | One coalesced message per repository per cycle, one lock hold, one fetch. A unit test asserts the fan-out over N pairs happens inside one acquisition. |
| **PR #10669 changes the read-only attachment point.** | Slice G attaches in one of two places. | Both attachment points are named in `contracts/internal-interfaces.md` section 7. The record and the precondition are identical either way. |
| **The record write emits a live node event.** | Computed attributes, display labels and human-friendly ids that read the repository node recompute on a rewrite. Webhooks and action rules fire. | Accepted. A rewrite is rare. No new `NodeMutationOrigin` member: the trigger builders already match `live` explicitly and would ignore a new value for free, but the record goes through an SDK mutation that always stamps `live`, and no channel carries an origin from the worker through GraphQL. See `research.md` R6 and ADR 0016. Revisit if a high-frequency writer of the same attributes appears. |
| **A rewritten trunk re-imports every object, unprompted.** | On a large repository that is the most expensive operation in the git subsystem, and nobody asked for it. | Accepted. The alternative is leaving the branch stuck, which is the defect being removed. FR-018 makes a failure of that import loud rather than retried blindly, which is where the real risk sits. |

## Settled without asking

| # | Decision | Basis |
|---|---|---|
| 1 | PRD FR-015 and FR-016 defer to epic IFC-3220. | The Jira epic already states it. The delivery queue they read does not exist. |
| 2 | The suppression marker is a cache key. | A fifth attribute and a temporal graph read both remain live alternatives that would remove the cache. `research.md` R4 says what each costs. |
| 3 | The recorder writes through the SDK node API, not through an extended SDK helper. | Keeps the epic inside one repository. `research.md` R6. |
| 4 | `RefreshGitFetch` gains an optional list and keeps its single-branch fields. | Five unrelated emission sites use them. `research.md` R5. |
| 5 | FR-017 is added on top of the PRD. | Removing the divergence case alone leaves the wrong message reachable from every other pull caller. `spec.md`, "Decisions Taken During Specification". |

## Complexity Tracking

| Violation | Why needed | Simpler alternative rejected because |
|---|---|---|
| A cache-based suppression marker, which is new coordination state (Principle VII). | FR-002 and SC-007 need the tracking target that produced the imported commit. Nothing stores it. | A fifth attribute stores a value the repository node already holds, and the PRD fixes the shape at four scalars. A temporal graph read is exact for read-write but wrong for read-only, where the same mutation writes `ref` and `commit` at one timestamp. Inferring from reachability is wrong whenever a rebased branch's old commits were already merged elsewhere. |
