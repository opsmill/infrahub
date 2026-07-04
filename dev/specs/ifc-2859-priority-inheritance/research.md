# Research: Priority Inheritance for Task Trees

**Feature**: [spec.md](spec.md) | **Date**: 2026-07-04

All decisions below were verified against the codebase on branch `priority-work-queues-ifc-2859` (foundation slice present).

## D1 — Priority field lives on `InfrahubContext`

**Decision**: Add `priority: WorkflowPriority | None = None` to `InfrahubContext` (`backend/infrahub/context.py`).

**Rationale**: `InfrahubContext` is the one object that already travels the whole task tree — it is injected as a flow parameter by both adapters (`inject_context_parameter` in `backend/infrahub/workers/utils.py`) and re-passed as `context=context` at 47 of the 85 dispatch call sites. An optional field with `None` default is backward compatible: pre-upgrade serialized contexts (flow-run parameters of in-flight runs) deserialize with `priority=None` and resolve to the catalogue default.

**Import safety (verified)**: `infrahub.workflows.constants` imports only `infrahub.utils` — importing `WorkflowPriority` from `context.py` creates no import cycle.

**Alternatives considered**: (a) Prefect runtime lookup of the parent flow run's `work_queue_name` at dispatch — rejected: adds a per-dispatch API call (violates the foundation's no-hot-path-cost constraint) and couples inheritance to Prefect runtime internals. (b) A separate `contextvar` — rejected: does not survive the process boundary between parent and child flow runs.

## D2 — Effective-priority resolution is one pure function shared by both adapters

**Decision**: A module-level pure function in `backend/infrahub/services/adapters/workflow/__init__.py`:

```python
def resolve_priority(
    priority: WorkflowPriority | None,
    context: InfrahubContext | EventContext | None,
    workflow: WorkflowDefinition,
) -> WorkflowPriority:
    # explicit override → context priority (InfrahubContext only) → catalogue default
```

**Rationale**: The precedence chain (FR-002) is pure decision logic — a function of its arguments with no collaborators, so per the backend component-design rule it needs no class or injection; both adapters call it, keeping worker/local behavior identical (FR-006). `EventContext` contributes no priority (FR-005): resolution treats it the same as `None`.

**Alternatives considered**: A `PriorityResolver` component with constructor injection — rejected as ceremony: no dependencies to inject, single pure computation.

## D3 — Stamping via `model_copy`, never mutating the caller's context

**Decision**: When the dispatched context is an `InfrahubContext`, each adapter stamps the resolved effective priority into a copy — `context.model_copy(update={"priority": effective})` — and injects the copy into the flow parameters. The caller's context object is never mutated.

**Rationale**: FR-003 requires descendants at depth ≥ 2 to inherit even when their parent was routed by catalogue default, so the stamp must happen on every dispatch that carries an `InfrahubContext`, with the *resolved* value (which is always non-`None` given a workflow's catalogue default exists). Copy-not-mutate avoids aliasing surprises when a caller dispatches several sub-workflows with different explicit overrides from the same context object.

**Interaction with `inject_context_parameter` (verified)**: when a flow declares only an `EventContext` parameter, the utility converts via `to_event_context()`, which does not carry priority — exactly the FR-005 boundary. No change to the utility is needed; stamping happens on the context object handed to it.

## D4 — Queue routing: explicit only when a non-default signal exists

**Decision**: `work_queue_name` is set to `effective.queue_name` when the explicit `priority` argument or the context's priority provided the value; when both are absent (effective == catalogue default), keep today's exact path: `work_queue_name=None`, the run inherits the deployment's queue.

**Rationale**: The deployment's queue already *is* the catalogue default's queue (foundation slice FR-003), so routing explicitly in that case would be redundant while changing the dispatch payload of every existing call — the zero-behavior-change guarantee (SC-002) is cleanest when the no-signal path stays byte-identical. Stamping (D3) still happens unconditionally, so descendants inherit the default correctly.

**Alternatives considered**: Always pass `effective.queue_name` — functionally equivalent (same queue) but touches every dispatch payload for no benefit; rejected to keep SC-002 trivially auditable.

## D5 — Audit classification of the 11 context-less dispatch sites (verified per-site)

**Decision**: Fix 4 sites; exempt 7.

Fix (in-flow, context in the enclosing signature):

| Site | Enclosing flow | Context in scope |
|------|----------------|------------------|
| `backend/infrahub/git/tasks.py:930` | `trigger_repository_user_checks_definitions` | yes |
| `backend/infrahub/git/tasks.py:1041` | `trigger_internal_checks` | yes |
| `backend/infrahub/proposed_change/tasks.py:990` | `validate_artifacts_generation` | yes |
| `backend/infrahub/profiles/tasks.py:113` | `profile_refresh_process` | yes (`EventContext`) |

Exempt — tree roots (no user context; per spec User Story 2, scenario 2): `backend/infrahub/cli/tasks.py:52`, `backend/infrahub/graphql/mutations/diff.py:105`, `backend/infrahub/graphql/mutations/profile.py:98`.

Exempt — no context in scope; passing one would require changing a flow or class signature, which is out of FR-004's call-site-only scope: `backend/infrahub/profiles/tasks.py:51` (`objects_profiles_refresh_multiple` has no context parameter), `backend/infrahub/core/merge/repository_merge_dispatcher.py:65,92` and `backend/infrahub/core/diff/branch_differ.py:159` (methods on classes that hold no context).

**Known limitation (accepted)**: inheritance depth is bounded by existing flow signatures — a child flow that declares no `InfrahubContext` parameter is routed correctly itself (depth-1, via the stamped context at its dispatch site) but cannot forward priority further. Changing flow signatures is explicitly out of scope; the exempted sites above are the record of where the chain stops today.

## D6 — Local adapter parity

**Decision**: `WorkflowLocalExecution` performs the same resolve + stamp before `inject_context_parameter`, and continues to do no queue routing.

**Rationale**: FR-006 — unit tests exercise inheritance through the local adapter without a Prefect server; a flow executed locally observes the same stamped context it would receive from the worker adapter.

## D7 — Testing approach

- **Unit** (`backend/tests/unit/`): context model round-trip (old payload without `priority` deserializes to `None`; `to_event_context()`/`to_request_context()` carry no priority); `resolve_priority` across the full precedence matrix (explicit/context/default × set/unset); local adapter stamps the resolved priority into the injected context.
- **Integration** (`backend/tests/integration/services/adapters/workflow/test_workflow_priority.py`, existing harness `TestWorkerInfrahubAsync`): parent dispatched with explicit high → sub-workflow dispatched with context only lands in `high` (assert `flow_run.work_queue_name`), verified at depth 2; low root with a catalogue-high child workflow stays low (test-only workflow definitions); no-signal dispatch still lands in `medium` unchanged.
