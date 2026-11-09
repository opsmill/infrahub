# Implementation Plan: Batch Python Computed-Attribute Recompute

**Branch**: `batch-python-recompute-infp-608` | **Date**: 2026-07-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/004-batch-python-recompute/spec.md`

## Summary

Replace the per-node Python computed-attribute recompute path (one Prefect task per node: repository init + read + transform + one `InfrahubUpdateComputedAttribute` GraphQL mutation each) with a batched pass inside the existing `computed_attribute_process_transform` flow: initialize the transform repository once per batch, run the per-node read+transform concurrently with per-node failure isolation, and persist all values through the existing shared bulk recompute writer (`BulkRecomputeDispatcher` → `BulkRecomputeWriter`), whose skip-unchanged gating stops no-op writes from emitting events and re-triggering the recompute machinery (the "echo storm"). Process flow runs must stay visible in branch-filtered task queries by carrying the branch tag from creation.

## Technical Context

**Language/Version**: Python 3.14 (backend)

**Primary Dependencies**: Prefect 3 (flows/automations via task-manager), infrahub_sdk (`InfrahubClient`, `InfrahubBatch`), Neo4j 2026.05 via internal `InfrahubDatabase`, existing `infrahub.core.recompute` package (bulk writer/dispatcher from the Jinja2 work)

**Storage**: Neo4j graph — writes go through `Node.save` inside the bulk writer's bounded transactions (100 nodes/txn default); no schema or migration changes

**Testing**: pytest — unit (`backend/tests/unit/computed_attribute/`), component (`backend/tests/component/`), functional with real git repo + transforms (`backend/tests/functional/computed_attributes/`), perf A/B via opsmill/infrahub-private-tests `TestMergeRecomputePython`. Two mandatory additions from critique: (E8) a functional/component assertion that a recompute's process run appears in a branch-filtered task query — visibility depends on tag mechanics that in-flow tag updates can clobber; (E9) a unit test with a recorder workflow adapter asserting an oversized fan-out (> submission limit) splits into ⌈N/limit⌉ submissions, ids partitioned exactly once, branch tag present on every submission

**Target Platform**: Infrahub task-workers (Linux containers), dev/CI/testcontainers stacks

**Project Type**: backend subsystem change (single package: `backend/infrahub/computed_attribute/`, touching `backend/infrahub/core/recompute/` consumers only via existing public builder)

**Performance Goals**: one source change affecting N readers settles in O(N) work — repo init 1×/batch, N reads + N transform execs (unavoidable, user code), ⌈N/100⌉ write transactions, 0 client-visible mutations, 0 echo re-dispatches; ≥99% reduction in flow-run count at scale

**Constraints**: behavior-preserving (byte-identical final values; identical per-node NodeUpdated events for real changes); merge fan-out scoping untouched; `InfrahubUpdateComputedAttribute` mutation remains public API (unused internally afterwards); per-submission chunking limit (`get_submission_chunk_size()`) unchanged

**Scale/Scope**: reference datasets — x-small (12 devices/type) for correctness+ratio, large (~100k nodes) where develop currently collapses (73k flow runs, bolt/FD exhaustion)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Schema-Driven Integrity** — PASS: no schema changes; read-only computed attribute semantics preserved.
- **II. Branch-Safe by Default** — PASS: batch persists via `registry.get_branch(branch_name)` through the existing writer; branch-deleted-mid-flight handled (abandon batch, no error). Branch tag on flow runs preserves per-branch task visibility (FR-006).
- **III. Type Safety & Explicit Contracts** — PASS: new helpers fully typed; flow signature (parameters) unchanged so Prefect deployment contract is stable.
- **IV. Test Discipline** — PASS: unit tests for partition/skip logic; component test characterizing fan-out; functional end-to-end with real repo; perf A/B for the headline claim. New behavior (failure isolation) gets dedicated tests.
- **V. Query Performance & Efficiency** — PASS (this feature is the principle in action): eliminates N+1 write pattern (N mutations → chunked bulk writes); reads stay per-node by necessity (per-node query with `update_group` subscriber registration is the reverse-index contract, FR-007).
- **VI. Security & Input Boundaries** — PASS: transform output validated (non-str rejected → skip) instead of being written blindly; no new input surfaces.
- **VII. Simplicity & Maintainability** — PASS: net code shrinks (per-node task + mutation constant deleted); reuses the existing writer rather than adding a second write path.

No violations → Complexity Tracking not needed.

## Project Structure

### Documentation (this feature)

```text
specs/004-batch-python-recompute/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/infrahub/computed_attribute/
└── tasks.py                     # process_transform flow: batch rewrite; delete per-node task + UPDATE_ATTRIBUTE constant

backend/infrahub/core/recompute/  # REUSED, not modified
├── bulk_write.py                # AttributeValueWrite, BulkRecomputeWriter (chunked txns, has_changes gating)
└── dispatch.py                  # build_bulk_recompute_dispatcher, BulkRecomputeDispatcher.dispatch

backend/tests/
├── unit/computed_attribute/test_tasks.py            # partition/skip unit tests
├── component/computed_attribute/                     # fan-out characterization
└── functional/computed_attributes/                   # end-to-end with real repo (existing, must stay green)
```

**Structure Decision**: single-file production change (`computed_attribute/tasks.py`) consuming the existing recompute package via its public builder; tests across the three existing tiers. No new modules.

## Failure & Rollback Semantics (from critique)

- **Mid-batch crash (E3)**: the writer commits per 100-node chunk; a crash leaves earlier chunks persisted, later ones stale. Accepted: recovery is the next trigger or a manual `RecomputeComputedAttribute` re-run — skip-unchanged makes redone work no-op-cheap. No flow-level retry is added.
- **Rollback (P5)**: single-file production change, no schema or data migration — rollback is a clean revert of the commit. A runtime kill-switch is deliberately not added (permanent config complexity for a transient de-risking need).
- **Skipped-node summary (P3/X1)**: the flow ends with one summary log line (`recompute complete: written=…, unchanged=…, skipped=…`) so partial failure is greppable/alertable until the recovery surface follow-up ships.
- **Known boundary (E7)**: per-changed-node event volume remains O(N); the echo is eliminated, event emission itself is unchanged and out of scope.
- **Shared-checkout invariant (E2)**: transform execution must not mutate the shared worktree; the per-node callables share one initialized repo under bounded concurrency — state the invariant in code.

## Complexity Tracking

Not applicable — no constitution violations.
