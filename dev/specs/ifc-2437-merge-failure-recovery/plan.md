# Implementation Plan: Merge Failure Recovery

**Branch**: `ifc-2437-merge-failure-recovery` | **Date**: 2026-06-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `dev/specs/ifc-2437-merge-failure-recovery/spec.md`

## Summary

Block writes to the default branch for the full duration of a merge, deterministically
detect when a merge has died (worker killed mid-merge), keep the default branch protected
after a failure until an administrator recovers it, and provide an `infrahub recover` CLI
command that rolls back the partial graph merge and resets the branch (and any associated
proposed change) to `OPEN`.

**Technical approach** (grounded in the current codebase):

- The `MergeLocker` "all_branches" global lock is acquired in `merge_branch` *around the entire*
  `_do_merge_branch` body (`backend/infrahub/core/branch/tasks.py:297`). It is held across the
  graph merge and schema migrations — i.e. for the full `MERGING` window — and its token encodes
  `timestamp::worker_id` (`backend/infrahub/lock.py`). This means **one signal** covers the whole
  failure window: *a branch in `MERGING` whose merge-lock holder is no longer in the active-worker
  set*. No second sub-phase status is needed (the earlier two-status `MERGING`/`MERGING_GRAPH`
  design is superseded — see research R1).
- Failure detection reuses the **exact mechanism the existing `clean_up_deadlocks` task already
  uses** (`backend/infrahub/locks/tasks.py`): parse the lock token, compare `worker_id` against
  `service.component.list_workers(...)` active set. The predicate is `status==MERGING` AND
  worker-dead AND `now − merge_started_at > grace_period` (a small configurable margin — cheap
  insurance against a transient heartbeat blip; a long merge does *not* stall the heartbeat, verified
  locally). The authoritative detector is a new recurring Prefect `INTERNAL` workflow
  (`cron="* * * * *"`, `concurrency_limit=1`, `ConcurrencyLimitStrategy.CANCEL_NEW`) modeled on
  `CLEAN_UP_DEADLOCKS`.
- Detection records a durable new `BranchStatus.MERGE_FAILED` on the source branch (the source of
  truth, in Neo4j). The write/merge block is enforced through a **shared `merge:protected` cache
  key** that every worker reads via `BranchStatusChecker` (one cache `GET` per write): set when a
  merge begins (before any graph write), updated to `MERGE_FAILED` by the detector, deleted on
  recovery/success. Because all workers read the same shared key, the block is **immediately
  consistent** — no propagation window, no per-transition status broadcast — so SC-001 holds
  literally and the range rollback never clobbers an interleaved write. The durable DB status is
  reloaded at startup and the recurring scan reconciles the key against it (self-healing across a
  restart or cache flush); if the cache is unreachable the gate logs and falls back to the durable
  DB branch status (so a cache outage blocks writes only when a merge is genuinely in progress,
  rather than freezing every default-branch write) (research R11).
- Recovery reverses a failed merge with a **single range rollback** over the default branch keyed on
  the persisted `merge_started_at`: reopen edges with `to >= merge_at`, delete edges with
  `from >= merge_at`, clean orphaned vertices, and restore `previous_*` metadata for the
  reverted-edge vertices where `updated_at >= merge_at`. This reverses graph merge **and** schema
  migrations in one uniform pass (IPAM never ran — see reorder below); it needs no
  `get_affected_node_uuids` list. Correctness rests on the default-branch write-block (R11): from
  `merge_at` until recovery the only target-branch writes are this merge's own, so deleting/reopening
  everything `>= merge_at` is exactly correct (research R8). No dual recovery path, no `MERGING_GRAPH`
  sub-state, no IPAM backstop.
- Vertex `updated_at`/`updated_by` are the source of truth on the default branch (metadata queries,
  ordering, filtering), so the metadata restore must be correct: the `updated_at >= merge_at` filter
  selects exactly the merge-bumped vertices (robust to partial failure — only the metadata query/
  migrations bump `updated_at`, and they run after the edge writes), and **schema-migration queries
  co-write `previous_*`** so migration collateral is restorable. The **IPAM reorder (submit after
  `MERGED`) is MANDATORY** — IPAM doesn't snapshot `previous_*`, so reordering keeps it out of the
  failed-merge window entirely (research R12).
- The range query is written as **per-edge-type subqueries** so Neo4j's per-type relationship indexes
  apply, and it requires **new `from`/`to` RANGE indexes** on the edge types (and possibly an
  `updated_at` node index for the metadata-restore selection) — a database index change gated by
  "Ask First" (a new graph migration + `IndexItem` entries).

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: FastAPI, Neo4j Python driver (Neo4j 5.28), Pydantic 2.10, Prefect
(workflow scheduling), Typer / `AsyncTyper` (CLI), Redis **or** NATS (distributed lock + cache,
selected by `config.SETTINGS.cache`)
**Storage**: Neo4j. Branch status and the new merge timestamp persist on the `:Branch` node
(`Branch` is a `StandardNode`); they survive process and worker death.
**Testing**: pytest — unit (`backend/tests/unit/`), component (`backend/tests/component/`, real
DB via TestContainers), functional (`backend/tests/functional/`), and integration_docker
(`backend/tests/integration_docker/`, full stack — required for the SIGKILL cross-process test).
**Target Platform**: Linux server (containerized: API server + task/git-agent workers).
**Project Type**: Backend service + admin CLI + Python SDK enum touch. No frontend work.
**Performance Goals**: Time-to-detection bounded by the scan interval (≈1 minute, matching
`CLEAN_UP_DEADLOCKS`). Detection adds one cheap Cypher lookup + one cache read per tick.
**Constraints**: Protection MUST survive restarts and be cleared *only* by successful recovery.
The recurring scan MUST be single-flighted across workers. Detection MUST NOT misclassify a
slow-but-healthy merge (worker still alive, still holds the lock).
**Scale/Scope**: At most one `MERGE_FAILED` branch can exist at a time (merges serialized by the
global merge lock; new merges/rebases blocked while one is in progress or failed).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

This is a backend + CLI feature with no UI; the frontend principles do not apply. Gates derived
from `.specify/memory/constitution.md`:

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | PASS (with approval) | No edits to generated files. `BranchStatus` is a hand-maintained enum (`core/branch/enums.py`) plus its SDK mirror (`python_sdk/infrahub_sdk/branch.py`); GraphQL exposure is automatic via `Enum.from_enum`. No user-data schema change, but the range rollback needs **new `from`/`to` (and possibly `updated_at`) graph indexes** (`IndexItem` + a graph migration) — a database index change gated by AGENTS.md "Ask First"; flagged for approval before implementation. |
| II. Branch-Safe by Default | PASS | Recovery rollback is target-branch + timestamp scoped (`from=$at`/`to=$at` on `$target_branch`) and uses soft-delete edge semantics already present in `RollbackQuery`. The new protection is branch-aware (only default + failed source blocked; unrelated branches writable). Merge behavior is the subject of the feature and is tested incl. cross-process. |
| III. Type Safety & Explicit Contracts | PASS | All new code typed (`str \| None`). `RecoveryReport` is a frozen dataclass. No new external GraphQL/REST contract beyond the auto-serialized enum value. |
| IV. Test Discipline | PASS | Unit (detection predicate, status checker), component (recovery rollback against a hand-set marker, write/merge/delete blocking), functional (end-to-end recover flow + scan), integration_docker (SIGKILL mid-merge → scan marks `MERGE_FAILED` while idle → `infrahub recover` → re-merge). Reuse existing schema fixtures. |
| V. Query Performance & Efficiency | PASS | The write gate adds **one cache `GET`** (`merge:protected`) per mutation — a single sub-ms round-trip before any transaction, no new per-write database query on the happy path (a branch-status query is issued only in the degraded cache-unreachable fallback). Detection scan = one parameterized Cypher lookup for `status=MERGING` branches + a cache read of the merge-lock token + key reconciliation; returns only `name`, `status`, timestamp. No N+1. The range rollback is written as per-edge-type subqueries to use relationship range indexes (new `from`/`to` indexes added) and batches `IN TRANSACTIONS OF 500 ROWS`. Recovery is a rare, operator-invoked operation, not a hot path. |
| VI. Security & Input Boundaries | PASS | `infrahub recover` is an admin CLI requiring DB access (same trust level as `infrahub db` commands). User-facing write-rejection messages name `infrahub recover` and "contact an administrator" without leaking internals. All Cypher parameterized. No secrets. |
| VII. Simplicity & Maintainability | PASS | Reuses: existing `MergeLocker` lock + token format, the `clean_up_deadlocks` liveness pattern, the Prefect `INTERNAL` cron-workflow pattern, `BranchStatusChecker` as the write chokepoint, the existing `RollbackQuery` (extended to a range query) + the `previous_*` snapshot mechanism, and the `AsyncTyper` CLI pattern (`cli/db.py`). One new status, one new persisted field, one new recurring workflow, one new CLI command, one new recovery component. No new dependencies. |

**Result**: PASS. No Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-2437-merge-failure-recovery/
├── plan.md              # This file
├── research.md          # Phase 0 — design decisions (rewritten for the single-state design)
├── data-model.md        # Phase 1 — BranchStatus + Branch field + recovery entities
├── quickstart.md        # Phase 1 — operator/dev verification walkthrough
├── contracts/
│   └── internal-api.md   # Phase 1 — internal Python interfaces (no new REST/GraphQL)
├── checklists/
│   └── requirements.md   # Spec-quality checklist (already current, 2026-06-04)
└── tasks.md             # Phase 2 — produced later by /speckit-tasks (does NOT exist yet)
```

### Source Code (repository root)

```text
backend/infrahub/
├── core/
│   ├── branch/
│   │   ├── enums.py                 # ADD BranchStatus.MERGE_FAILED
│   │   ├── models.py                # ADD Branch.merge_started_at (written once at MERGING, not cleared); NO delete() guard
│   │   └── tasks.py                 # write merge_started_at + set merge:protected key on OPEN→MERGING; delete key on MERGED/rollback; MANDATORY reorder IPAM submit after MERGED
│   ├── merge/
│   │   ├── branch_merger.py         # (timestamp + cache-key wiring, if not done in tasks.py)
│   │   ├── merge_locker.py          # (read-side) helper to inspect the merge-lock holder
│   │   ├── write_blocker.py         # NEW (US1): MergeWriteBlocker — owns the merge:protected cache key (set/get/delete + parse)
│   │   └── failure_recovery.py      # NEW (US2/US3): detection predicate + recovery (range rollback, branch/PC reset, key update→MERGE_FAILED via MergeWriteBlocker + scan reconcile)
│   ├── migrations/                  # MODIFY migration queries that bump updated_at/by to co-write previous_* (restorable on recovery)
│   ├── query/
│   │   └── rollback.py              # MODIFY: range rollback (from/to >= merge_at) per-edge-type subqueries + metadata restore for reverted-edge vertices where updated_at >= merge_at
│   └── graph/
│       └── index.py                 # ADD from/to (and possibly updated_at) RANGE IndexItem entries (Ask First) + graph migration
├── branch/
│   └── status_checker.py            # ADD MERGE_FAILED handling; gates read merge:protected key via MergeWriteBlocker (gains MergeWriteBlocker + db deps; check becomes async; cache-unreachable → DB fallback)
├── graphql/
│   └── middleware.py                # MERGE_FAILED grants no mutation exception (incl. BranchDelete) — FR-014 at the mutation gate
├── locks/
│   └── tasks.py                     # (reference: clean_up_deadlocks liveness pattern reused)
├── tasks/
│   └── recurring.py / merge_watcher # NEW recurring scan flow (module for the INTERNAL workflow)
├── workflows/
│   └── catalogue.py                 # ADD MERGE_WATCHER WorkflowDefinition to WORKFLOWS
├── core/initialization.py           # ADD startup detection call (API + git-agent both run initialization())
├── config.py                        # ADD merge-failure grace-period setting (default ~2-3 min)
├── cli/
│   ├── __init__.py                  # register `recover` command/typer
│   └── recover.py                   # NEW: `infrahub recover` (auto-detect, confirm, --yes)
└── exceptions.py                    # ADD failure-merge write/merge rejection error(s) if needed

python_sdk/infrahub_sdk/
└── branch.py                        # ADD MERGE_FAILED to the SDK BranchStatus enum (submodule)

backend/tests/
├── unit/                            # detection predicate, status-checker gates
├── component/core/merge/            # recovery rollback + write/merge/delete blocking (real DB)
├── functional/                      # end-to-end recover + scan-marks-failed
└── integration_docker/             # SIGKILL mid-merge → idle scan → recover → re-merge

changelog/                          # towncrier fragment
```

**Structure Decision**: Backend monolith with the standard Infrahub layout. New logic lives in a
dedicated `core/merge/failure_recovery.py` component built with constructor-injected
collaborators (`db`, `DiffMerger`/`DiffRepository`, lock registry, component service) per
`dev/rules/backend-component-design.md`, exposing a small surface: a detection entry point used
by the recurring scan / startup / on-write fast paths, and a recovery entry point used by the CLI.
Status enforcement extends the existing `BranchStatusChecker` rather than adding a parallel gate.

## Complexity Tracking

No constitution violations. Section intentionally empty.
