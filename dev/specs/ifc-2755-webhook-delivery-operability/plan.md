# Implementation Plan: Webhook Delivery Operability

**Branch**: `pmi-20260624-speckit-end-of-webhooks` | **Date**: 2026-06-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/ifc-2755-webhook-delivery-operability/spec.md`

## Summary

Make a webhook delivery a first-class, inspectable, recoverable object in the Tasks tab, built entirely on Prefect primitives with no new Neo4j node and no migration. The delivery is the user-visible `webhook_send` run; the operability layer adds: (1) capture of the request/response as a redacted artifact on the run, (2) a pure failure classifier producing a clean reason + smart (transient-only) retry over the existing fixed-delay policy, (3) polymorphic GraphQL task typing (`WebhookDeliveryTask`) discriminated by the run's workflow name, mirroring the events type hierarchy, and (4) generic, task-id-addressable resend and cancel mutations gated by a server-computed `available_actions` capability on every task.

The structural split (orchestrator freezes payload → `webhook_send` carries its own fixed-delay bounded retries) already exists on the branch, along with the retry policy itself (3 attempts, ~120s fixed delay, retrying on every failure) and webhook-node-id tagging on the flow runs — see the Implementation Sync revision below. The one structural prerequisite uncovered in research and still outstanding is that `webhook_send` must be promoted to a registered workflow/deployment so it can be resubmitted by id and discriminated by name.

## Technical Context

**Language/Version**: Python 3.14 (backend), TypeScript 5.9 / React 19.2 (frontend)
**Primary Dependencies**: FastAPI, Graphene (GraphQL), Prefect (flow runs, artifacts, run state), httpx (via `InfrahubHTTP` adapter), Pydantic 2.12; frontend: Apollo + gql.tada, TanStack Query, `@infrahub/ui`, react-aria-components
**Storage**: No new persisted domain schema. Delivery data lives in Prefect (flow-run parameters, tags, artifacts, run state) subject to Prefect retention (~30 days). Neo4j unchanged.
**Testing**: pytest (unit/component/functional), Vitest (frontend unit), Playwright (frontend E2E)
**Target Platform**: Linux server (backend workers + API), browser (frontend)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: No additional per-task query cost beyond what the Tasks list already fetches — workflow-name resolution is already batched; the `http` artifact is read back in one batched call mirroring progress read-back, gated on GraphQL field selection.
**Constraints**: No raw secret ever persisted (redaction at capture time); no new Neo4j node; no migration; existing task queries must keep working unchanged.
**Scale/Scope**: Bounded by Prefect retention. Backend: ~1 new GraphQL interface + 1 concrete type + 2 mutations + 1 classifier + 1 capture/redaction component + 1 catalogue entry + retry condition. Frontend: extend task detail with a polymorphic section + 2 actions.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | PASS | No new Neo4j node, no migration. Only generated GraphQL schema changes (`schema/schema.graphql`, frontend codegen) — regenerated, not hand-edited. |
| II. Branch-Safe by Default | PASS | Deliveries are Prefect runs, not branch-versioned graph data. The delivery carries the originating branch as a tag; the task query already filters by branch. Resend re-tags from the original run's parameters. No cross-branch graph writes. |
| III. Type Safety & Explicit Contracts | PASS | New internal models are frozen dataclasses / Pydantic (`CapturedHeaders`, classifier result, captured request/response). GraphQL interface + concrete type defined before implementation (see contracts/). `str \| None` style. |
| IV. Test Discipline | PASS | Unit: classifier, header redaction, available-actions gating (pure logic, injected deps). Functional: capture on success/failure, resend resubmit, cancel state flip. Frontend E2E: resend + cancel happy paths. Reuse existing webhook + task fixtures. |
| V. Query Performance & Efficiency | PASS | Workflow-name resolution already batched in the task service. `http` artifact read back in one batched `read_artifacts` call (mirrors `read_progress`), only when the GraphQL selection requests delivery fields. `available_actions` derived from already-fetched run state — no extra query. |
| VI. Security & Input Boundaries | PASS | Redaction before artifact write (no raw secret persisted). Resend/cancel authorized at the API layer via object-level update permission on the target webhook node. Classified messages never leak stacktraces (FR-014 keeps genuine crashes distinct). Mutations require auth. |
| VII. Simplicity & Maintainability | PASS | Reuses Prefect primitives and the existing events polymorphic pattern instead of inventing parallels. No new global permission (reuses object permission). Fixed-delay retry (no new backoff machinery). One catalogue entry promotes an existing flow. |

**Result**: PASS, no violations. Complexity Tracking not required.

One design decision worth surfacing (resolved in research.md, not a violation): authorization reuses the **object-level update permission** on the target webhook node rather than introducing a new `MANAGE_WEBHOOKS` global permission, because no webhook global permission exists today and adding one would exceed the clarified scope ("no new permission model").

### Frontend principles (feature includes UI)

| Principle | Status | Notes |
|---|---|---|
| Reuse Before Reinvent | PASS | Reuses `DataViewer` (payload/response body), `PropertyList` (headers/metadata), `Badge` (status/reason), `ModalConfirm` (resend/cancel confirmation), `Button` (`isPending`). No new primitives. |
| Single State Owner | PASS | Task data owned by TanStack Query; confirmation modal open-state local `useState`; no mirrored server data. |
| Backend Authoritative | PASS | `available_actions` (availability + reason) computed server-side; the frontend only renders it and disables controls accordingly. No client-side re-derivation of gating rules. |
| Component Contracts Designed for All Callers | PASS | Task detail renders polymorphically by `__typename`; the webhook section is additive and does not break the generic task detail used by other task types. |
| E2E Happy Path | PASS | New Playwright tests for every user-facing story: inspect (US1), failure reason (US2), resend (US3), cancel (US4) — Principle IV requires E2E for all user-facing features, not only the mutating ones. |

### Shared Components Inventory (frontend)

| Need | Reusing | Source |
|---|---|---|
| Display payload / request body / response body (JSON) | `DataViewer` | `shared/components/data-viewer/data-viewer.tsx` |
| Key-value display for headers + delivery metadata | `PropertyList` | `shared/components/table/property-list.tsx` |
| Status / classified-reason pill | `Badge` | `shared/components/ui/badge.tsx` |
| Resend / cancel confirmation dialog | `ModalConfirm` | `shared/components/modals/modal-confirm.tsx` |
| Action buttons with pending state | `Button` | `@infrahub/ui` |
| Tooltip for disabled row actions (shows `unavailability_reason`) | `Tooltip` | `@infrahub/ui` |
| Shared resend/cancel control (row compact + detail labeled) | `TaskActions` (building new) | `entities/tasks/ui/task-actions.tsx` |
| Success / error feedback | `Alert` + `toast` | `shared/components/ui/alert.tsx` |
| Mutation wiring (3-layer api → domain → ui hook) | existing pattern | `entities/repository/...reimport-last-commit*` (reference) |
| Polymorphic GraphQL selection (`... on WebhookDeliveryTask`) | inline-fragment pattern | `entities/proposed-changes/api/get-proposed-change-thread-from-api.ts` (reference) |

`TaskActions` is a feature-level composition of existing primitives (`Button`, `ModalConfirm`, `Tooltip`, `toast`), not a new shared UI primitive — it reads `available_actions` and renders compact in the delivery row and labeled in the detail panel. No Complexity Tracking entry needed (no new primitive, no constitution deviation).

## Project Structure

### Documentation (this feature)

```text
specs/ifc-2755-webhook-delivery-operability/
├── plan.md              # This file
├── research.md          # Phase 0 output — decisions resolving design open points
├── data-model.md        # Phase 1 output — entities + GraphQL shape + state machine
├── quickstart.md        # Phase 1 output — how to validate each user story
├── contracts/
│   └── graphql.md       # GraphQL SDL for the task interface, WebhookDeliveryTask, mutations
├── checklists/
│   └── requirements.md  # Spec quality checklist (from /speckit-specify)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/infrahub/
├── webhook/
│   ├── tasks/process.py          # add retry_condition_fn (transient-only); write http capture in send body
│   ├── models.py                 # add CapturedHeaders redaction; captured request/response models
│   ├── classifier.py             # NEW — pure failure classifier (CONFIG/CONNECTION/TLS/TIMEOUT/4xx/5xx/UNKNOWN)
│   └── capture.py                # NEW — build + write the redacted http artifact on the run
├── workflows/
│   └── catalogue.py              # add WEBHOOK_SEND WorkflowDefinition; register in WORKFLOWS
├── graphql/
│   ├── types/task.py             # TaskNodeInterface; keep TaskNode; add WebhookDeliveryTask; available_actions; TASK_TYPES + resolve_type
│   ├── queries/task.py           # serializer: emit workflow discriminator + delivery fields (gated); compute available_actions
│   ├── mutations/task.py         # NEW — generic TaskResend, TaskCancel mutations (by task id)
│   ├── manager.py                # register concrete task types (mirror _load_event_types)
│   └── schema.py                 # wire the new mutations into InfrahubBaseMutation
└── task_manager/flow_run/        # reader: add read of the http artifact (mirror read_progress); read params by id for resend

backend/tests/
├── unit/webhook/                 # classifier, CapturedHeaders redaction, available-actions gating
├── functional/webhook/           # capture on success/failure, resend resubmit, cancel state flip
└── component/graphql/            # task typing resolve_type; mutation auth gating

frontend/app/src/
├── entities/tasks/
│   ├── api/                      # extend task-list AND task-details queries with available_actions + `... on WebhookDeliveryTask`; resend/cancel mutations
│   ├── domain/                   # resend/cancel domain fns (error mapping)
│   └── ui/
│       ├── task-actions.tsx      # NEW — shared <TaskActions task> (button + confirm modal + toast), reads available_actions
│       ├── task-items.tsx        # render <TaskActions> compact (icon + tooltip) in each delivery row
│       ├── task-item-details.tsx # polymorphic section: payload/request/response/reason + <TaskActions> labeled
│       └── queries/              # useResendDelivery / useCancelDelivery mutation hooks
└── (generated types regenerated via `pnpm codegen`)

changelog/
└── +ifc-2755-webhook-delivery-operability.added.md   # towncrier fragment
```

**Structure Decision**: Web application (backend + frontend). Backend changes concentrate in `webhook/`, `workflows/catalogue.py`, and `graphql/`; Prefect access goes through the existing `task_manager/flow_run` adapter. Frontend changes are additive within `entities/tasks/`. No new top-level modules.

## Phasing (maps to spec user stories)

The four spec user stories form the delivery order; the typing foundation is a shared enabler landed with US1.

- **Foundation (enabler, with US1)**: `TaskNodeInterface` + `resolve_type` + `TASK_TYPES`, `TaskNodes.node` object→interface, manager registration, register `WEBHOOK_SEND` in the catalogue.
- **US1 (P1) — Inspect request/response**: capture component + redaction, write `http` artifact in the send body, read-back in the serializer, `WebhookDeliveryTask` fields, frontend display section.
- **US2 (P2) — Classified failure + smart retry**: classifier component, `retry_condition_fn`, clean re-raise, surface reason + remediation hint.
- **US3 (P3) — Resend**: generic `TaskResend` mutation (read frozen params by run id, resubmit `WEBHOOK_SEND`), `available_actions` RESEND gating (any terminal state), confirm-on-every-resend UI via the shared `<TaskActions>` in both the delivery row and the detail panel.
- **US4 (P4) — Cancel**: generic `TaskCancel` mutation (state flip to CANCELLING), `available_actions` CANCEL gating (non-terminal), exposed through the same shared `<TaskActions>` in row + detail panel (disabled with tooltip reason when unavailable).

Both surfaces require `available_actions` (and, for the row, the `... on WebhookDeliveryTask` discriminant) on the **task-list** query, not just the detail query — the list query gains these fields as part of US1's foundation.

## Complexity Tracking

No constitution violations to justify.

## Revision: Implementation Sync — 2026-06-26

Reason: Reconcile the plan with foundation work merged ahead of the operability layer. Documentation-only sync; no constitution, `dev/guidelines/`, or `dev/adr/` conflict.

| Foundation piece | State |
|---|---|
| `webhook_send` flow split (#9672) | Landed |
| Fixed-delay bounded retry policy, 3 attempts / ~120s, retrying on all failures (#9676) | Landed |
| Webhook-node-id tagging on flow runs | Landed |
| Register `WEBHOOK_SEND` in the workflow catalogue (Phasing → Foundation) | Outstanding |
| Transient-only `retry_condition_fn` over the landed policy (Phasing → US2) | Outstanding |
| Capture/redaction, typing, classification, resend, cancel (US1–US4) | Outstanding |
