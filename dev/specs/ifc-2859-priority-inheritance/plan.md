# Implementation Plan: Priority Inheritance for Task Trees

**Branch**: `priority-work-queues-ifc-2859` | **Date**: 2026-07-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `dev/specs/ifc-2859-priority-inheritance/spec.md`

## Summary

Give `InfrahubContext` an optional `priority` field, resolve the effective priority at both dispatch entry points of the workflow adapter as a strict chain (explicit override → context priority → catalogue default), and stamp the resolved value into the context injected into every child run so entire task trees run at the priority of their root. Includes a verified one-time audit passing the in-scope context at the 4 sub-dispatch sites that omit it. Zero behavior change in outcomes: nothing dispatches non-medium until classification lands, every run still lands in the same queue as today, and no-signal dispatches still send no explicit queue name — the only payload difference is the stamped `priority` inside the injected context.

Technical approach (full details in [research.md](research.md)): `priority: WorkflowPriority | None = None` on `InfrahubContext` (D1, import-cycle verified); a pure `resolve_priority()` function shared by both adapters (D2); stamping via `context.model_copy(update=...)` — copy, never mutate (D3); explicit queue routing only when a non-default signal exists, so no-signal dispatches keep `work_queue_name=None` (D4); audit classification verified per-site — 4 fixes, 7 documented exemptions (D5); local adapter mirrors resolve + stamp for test parity (D6). Resolve + stamp + route lives in one shared `prepare_dispatch` helper beside `resolve_priority` so the three entry points cannot drift (critique E1).

## Technical Context

**Language/Version**: Python 3.14 (backend only)

**Primary Dependencies**: Prefect 3.7.5 (existing), Pydantic 2.12 — no new dependencies

**Storage**: None — no database schema or migration changes; priority travels inside the serialized flow-run parameters that already carry the context

**Testing**: pytest 9.0 — unit (`backend/tests/unit/`) and integration (`backend/tests/integration/services/adapters/workflow/` on `TestWorkerInfrahubAsync`)

**Target Platform**: Linux server (Infrahub backend + task worker containers)

**Project Type**: Backend service extension (task execution layer)

**Performance Goals**: No new hot-path cost — resolution is an in-process pure function; no additional orchestrator API calls on any dispatch path

**Constraints**: Zero behavior change (SC-002); backward-compatible context payloads (FR-001); priority must not leak into event or SDK request contexts (FR-005); call-site-only audit — no flow or class signature changes (FR-004)

**Scale/Scope**: ~7 backend source files touched (1 model, 3 adapter files, 4 call-site fixes across 3 task modules), 1 knowledge doc updated

## Constitution Check

*GATE: evaluated against `.specify/memory/constitution.md` v1.0.0.*

| Principle | Assessment |
|-----------|------------|
| I. Schema-Driven Integrity | ✅ N/A — no node/attribute/relationship schema involvement; no generated files touched |
| II. Branch-Safe by Default | ✅ N/A — priority routing is branch-agnostic infrastructure; no database queries added or modified |
| III. Type Safety & Explicit Contracts | ✅ `priority` is the typed `WorkflowPriority` enum end-to-end; `resolve_priority` is fully type-hinted; no untyped dicts |
| IV. Test Discipline | ✅ Unit tests for pure logic (model field, resolution matrix, local-adapter stamping); integration tests for queue routing on the existing Prefect harness; no mocks |
| V. Query Performance & Efficiency | ✅ No Cypher/database queries; no extra Prefect API calls on any dispatch path |
| VI. Security & Input Boundaries | ✅ No user input, no API surface, no auth changes; priority remains internal plumbing typed as an enum |
| VII. Simplicity & Maintainability | ⚠️ Justified violation — inheritance plumbing with no production caller dispatching non-medium is nominally YAGNI. Same justification as the foundation slice: committed follow-up under INFP-635; restated in Complexity Tracking and to be restated in the PR |

**Post-design re-check**: no new violations introduced; the single ⚠️ is tracked below.

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-2859-priority-inheritance/
├── plan.md              # This file
├── research.md          # Phase 0 output — decisions D1-D7, per-site audit verification
├── data-model.md        # Phase 1 output — entity change
├── quickstart.md        # Phase 1 output — validation guide
├── contracts/
│   └── workflow-adapter.md  # Updated internal adapter interface contract
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/infrahub/
├── context.py                          # + InfrahubContext.priority (D1)
├── services/adapters/workflow/
│   ├── __init__.py                     # + resolve_priority() pure function (D2)
│   ├── worker.py                       # resolve + stamp + route on both entry points (D3, D4)
│   └── local.py                        # resolve + stamp, no routing (D6)
├── git/tasks.py                        # audit: pass context at :930, :1041 (D5)
├── proposed_change/tasks.py            # audit: pass context at :990 (D5)
└── profiles/tasks.py                   # audit: pass context at :113 (D5)

backend/tests/
├── unit/
│   ├── test_context.py                 # NEW or extended — priority default, old-payload compat, conversion boundaries
│   └── services/adapters/workflow/     # resolve_priority matrix; local adapter stamping
└── integration/services/adapters/workflow/
    └── test_workflow_priority.py       # extended — inheritance at depth 1 and 2, exact inheritance, no-signal unchanged

dev/knowledge/backend/
└── async-tasks.md                      # + priority inheritance section (documentation gate)
```

**Structure Decision**: All changes extend existing modules in the task-execution layer; the only new symbol is the `resolve_priority` function beside the adapter interface it serves. Test files mirror source structure. No new packages, no frontend, no SDK.

## Design Overview

### 1. Context field (`context.py`) — research D1

`InfrahubContext.priority: WorkflowPriority | None = None`. Optional, absent by default; pre-upgrade payloads deserialize to `None` (FR-001). `to_event_context()` and `to_request_context()` are untouched (FR-005).

### 2. Resolution (`services/adapters/workflow/__init__.py`) — research D2

```python
def resolve_priority(priority, context, workflow) -> WorkflowPriority:
    # 1. explicit argument, if given
    # 2. context.priority, if context is an InfrahubContext with priority set
    # 3. workflow.default_priority
```

Pure function, no collaborators — shared by both adapters so behavior is identical (FR-002, FR-006). `EventContext` and `None` contexts contribute nothing.

### 3. Stamp + route (`worker.py`) — research D3, D4

On both `execute_workflow` and `submit_workflow`:

- `effective = resolve_priority(priority, context, workflow)`
- If the context is an `InfrahubContext`: inject `context.model_copy(update={"priority": effective})` — unconditional stamp, copy-not-mutate (FR-003).
- `work_queue_name = effective.queue_name` only when the explicit argument or the context supplied the priority; otherwise `None` (deployment default). Queue outcomes are unchanged everywhere (SC-002); the injected context payload does gain the stamped `priority` field on every dispatch that carries an `InfrahubContext` — that is the point of FR-003, not a regression.
- Both entry points call a shared `prepare_dispatch(workflow, context, priority)` helper (returns the stamped context and `work_queue_name`) so worker and local adapters cannot drift (critique E1).

### 4. Local adapter parity (`local.py`) — research D6

Same resolve + stamp before `inject_context_parameter`; still no queue routing. Inheritance is observable in local execution and unit-testable without a Prefect server (FR-006).

### 5. Call-site audit — research D5

Pass the in-scope context at the 4 verified sites (`git/tasks.py:930,1041`, `proposed_change/tasks.py:990`, `profiles/tasks.py:113`). The 7 exemptions (3 roots, 4 without a context in scope) are documented in research.md as the record of where the inheritance chain stops today (SC-003).

### 6. Documentation gate

`dev/knowledge/backend/async-tasks.md` gains a "Priority inheritance" subsection (context field, resolution chain, stamping semantics, audit exemptions) in the same PR.

## Testing Plan

| Level | Location | Coverage |
|-------|----------|----------|
| Unit | context model tests | `priority` defaults to `None`; payload without the field deserializes cleanly (FR-001); `to_event_context()` / `to_request_context()` expose no priority (FR-005) |
| Unit | adapter tests | `resolve_priority` full precedence matrix — explicit×context×default combinations including `EventContext` and `None` contexts (FR-002); local adapter injects a context stamped with the resolved priority, caller's context unmutated (FR-003, FR-006) |
| Integration | `test_workflow_priority.py` (extended) | Root dispatched with explicit `high` → child dispatched context-only lands in `high`; grandchild (depth 2) lands in `high` (SC-001); low root + catalogue-high child workflow runs `low` — exact inheritance; explicit override mid-tree re-roots its subtree; no-signal dispatch still lands in `medium` with no explicit `work_queue_name` (SC-002) |

Not tested: Prefect's native queue-priority ordering under load — upstream behavior assumed correct (unchanged from foundation slice).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Constitution VII (YAGNI): inheritance has no production caller dispatching non-medium in this slice | The seam completes the foundation — classification (committed work under INFP-635) only delivers user-visible expedition if whole trees inherit; landing inheritance with classification would couple infrastructure to a behavior change | Waiting for classification would make that slice both risky (behavior + plumbing at once) and unreviewable against a zero-change baseline |
