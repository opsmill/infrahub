---
description: "Task list for Webhook Delivery Operability"
---

# Tasks: Webhook Delivery Operability

**Input**: Design documents from `specs/ifc-2755-webhook-delivery-operability/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/graphql.md

**Tests**: Included — the Infrahub constitution (Principle IV, Test Discipline) requires tests for new features.

**Organization**: Tasks are grouped by user story. The typing foundation is a shared blocking prerequisite (Phase 2) consumed by every story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US4 maps to the spec user stories
- Paths are project-relative

## Path Conventions

Web application: backend under `backend/`, frontend under `frontend/app/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Lightweight — dependencies and stack already exist on the branch.

- [ ] T001 [P] Add towncrier changelog fragment `changelog/+ifc-2755-webhook-delivery-operability.added.md` describing the delivery operability feature (user-facing). This single fragment covers the whole feature, including the landed failure classification, per-attempt request logging with header redaction, traceback-suppressed classified failures, and retry/cancel; no slice ships its own fragment.
- [ ] T002 [P] Add a controllable HTTP-target test fixture (endpoint that can return success / 4xx / 5xx / timeout / TLS error / be unreachable) under `backend/tests/functional/webhook/conftest.py`, reusing existing webhook fixtures.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Register `webhook_send` as the user-facing delivery and expose `available_actions` generically on every task. Polymorphic task typing (a `WebhookDeliveryTask` subtype) is deferred to US1, where the delivery-specific `http_request`/`http_response`/`error` fields it carries are first needed; `available_actions` is exposed directly on `TaskNode` and does not require it.

- [X] T003 Register `WEBHOOK_SEND` `WorkflowDefinition` (`type=CORE`) and add it to `WORKFLOWS` in `backend/infrahub/workflows/catalogue.py`.
- [X] T004 Make `webhook_send` the user-facing, retryable delivery: it self-tags with the webhook node and branch, and `webhook_process` (internal orchestrator) stops tagging itself and passes `branch_name` to the inline call, in `backend/infrahub/webhook/tasks/process.py` (depends on T003). Supersedes the original `submit_workflow` detachment — `webhook_process` keeps its inline call and classified-failure settling; only the node tag moves to the delivery so the run that carries the frozen payload is the one surfaced and retried.
- [X] T005 [P] Add the `TaskAction` type and `TaskActionType` enum (RETRY, CANCEL) in `backend/infrahub/graphql/types/task.py`. The `HttpRequest`/`HttpResponse`/`DeliveryError` types are deferred to US1, where the captured request/response is displayed.
- [X] T006 (depends on T005) Polymorphic task typing: `TaskNodeInterface`, `WebhookDeliveryTask` (`http_request`/`http_response`), `TASK_TYPES` + `resolve_type`, and `TaskNodes.node` → interface, in `backend/infrahub/graphql/types/task.py`. The classified `error` sits on the interface (common to all tasks, per the 2026-07-02 clarification), not on the delivery type. Landed with one deviation from data-model.md (synced there): the deprecated `related_node`/`related_node_kind` accessors live on the interface, not on `TaskNode`, because existing consumers select them without inline fragments and FR-004 requires those selections to keep resolving.
- [X] T007 (depends on T006) Register the concrete task types so they are reachable via `resolve_type` (mirror `_load_event_types`) in `backend/infrahub/graphql/manager.py`.
- [X] T008 [P] Implement the `available_actions` computation as a dedicated pure function/module from `(workflow_name, prefect_state)` — RETRY iff terminal (incl. COMPLETED), CANCEL iff non-terminal, empty for non-webhook runs, each with `unavailability_reason` — unit-testable in isolation, in `backend/infrahub/graphql/queries/task_actions.py` (depends on T003).
- [X] T009 Wire `available_actions` into the task serializer (`_serialize_node`) so every task node carries it, in `backend/infrahub/graphql/queries/task.py` (depends on T008).
- [X] T010 [P] Unit test the `available_actions` gating matrix (terminal/non-terminal, webhook vs other) in `backend/tests/unit/graphql/queries/test_task_actions.py` (depends on T008).
- [X] T011 (depends on T007) Component test that `resolve_type` returns `WebhookDeliveryTask` for `webhook_send` runs and `TaskNode` otherwise, and that existing common-field selections still resolve, in `backend/tests/component/graphql/queries/test_task.py`. The pre-existing tests in that module double as the common-field backward-compat check; the delivery-specific fields resolve to null until the capture artifact lands (T014–T017).

**Checkpoint**: `webhook_send` is registered and resubmittable; the delivery run carries the node/branch tags; `available_actions` is populated on every task (empty for non-deliveries). The GraphQL schema is regenerated and committed at each increment so the generated-file CI gate stays green. Polymorphic typing and the delivery-specific display fields land in US1.

---

## Phase 3: User Story 1 - Inspect what a delivery sent and received (Priority: P1) 🎯 MVP

**Goal**: Operators see the payload, request (URL + redacted headers), response (status, body, latency) for any delivery, reflecting the last attempt.

**Independent Test**: Trigger a delivery to a test endpoint; open it; confirm payload/request/response/latency are shown and that env-sourced headers + the signature are masked while static/standard headers and the payload are verbatim.

### Implementation for User Story 1

- [X] T012 [P] [US1] Implement the header-redaction domain logic (mask ENVIRONMENT-sourced headers, `webhook-signature`, and well-known credential header names case-insensitively; keep standard and STATIC headers verbatim) in `backend/infrahub/webhook/models.py`. Landed as `Webhook.redact_headers` with sensitive header names normalized at definition — no separate `CapturedHeaders` object and no `capture.py` module; the capture tasks below reuse this redaction.
- [X] T013 [US1] Expose per-header provenance (`HeaderKind`) from header assembly so redaction reads the kind rather than re-guessing the flat dict, in `backend/infrahub/webhook/models.py` (depends on T012). Landed: `WebhookHeader` carries its kind at definition.
- [X] T014 [P] [US1] Implement captured request/response models and the `CapturedHttp` artifact builder (one grouped `http` payload: request, response, error) in `backend/infrahub/webhook/capture.py` (new module; reuses the T012 redaction from `models.py`). Landed: `capture.py` holds the pure `CapturedHttp` models plus `build_http_capture`; the artifact write is done through the client adapter (T015), so `capture.py` carries no Prefect I/O.
- [X] T015 [US1] Write the redacted `http` artifact (key `infrahub-webhook-http`, last attempt) on both success and failure inside the `webhook_send` body, in `backend/infrahub/webhook/tasks/process.py` (depends on T014, T013). Landed: written via `PrefectClientAdapter.create_artifact` behind a `FlowRunArtifactWriting` protocol (mirroring the read side); the artifact key and type live in `task_manager/flow_run/constants.py`.
- [X] T016 [US1] Read the `http` artifact back (mirror `read_progress`: `read_artifacts(ArtifactFilter(key), FlowRunFilter(id))`) in `backend/infrahub/task_manager/flow_run/reader.py`. Landed: `read_http` filters by key and keeps the most recent artifact per run, so the surfaced capture reflects the last attempt.
- [X] T017 [US1] Project the captured artifact onto `http_request`/`http_response`/`error` in the serializer, gated on the GraphQL selection; payload continues to come from `parameters`, in `backend/infrahub/graphql/queries/task.py` (depends on T016, T006). Landed: gated by `include_http` on the fetch options, derived from the selection of `http_request`/`http_response`/`error`.
- [X] T018 [P] [US1] Unit test the header redaction (env + signature + well-known credential headers masked; standard/static + payload verbatim; no raw secret) in `backend/tests/unit/webhook/test_models.py`. Landed alongside the `models.py` redaction rather than in a dedicated capture test module.
- [X] T019 [P] [US1] Functional test that capture is present on success and failure, reflects the last attempt, and persists no raw secret, in `backend/tests/functional/webhook/test_capture.py` (depends on T015, T016). Landed; a component test also covers the adapter write/read round-trip in `backend/tests/component/task_manager/test_prefect_client.py`.
- [ ] T020 [P] [US1] Extend the task-list and task-details queries with `available_actions` and `... on WebhookDeliveryTask { http_request http_response error }` in `frontend/app/src/entities/tasks/api/get-task-list-from-api.ts` and `get-task-details-from-api.ts`.
- [ ] T021 [US1] Regenerate frontend GraphQL types (`cd frontend/app && pnpm codegen`) (depends on T020 and backend schema types T006).
- [ ] T022 [US1] Render the webhook delivery section (payload from `parameters`, request incl. target URL, response, latency, HTTP status, last-attempt timestamp) polymorphically by `__typename` in `frontend/app/src/entities/tasks/ui/task-item-details.tsx` (depends on T021).
- [ ] T023 [P] [US1] Frontend unit test for the delivery detail rendering (request/response/redacted headers shown) in `frontend/app/src/entities/tasks/ui/task-item-details.test.tsx` (depends on T022).
- [ ] T050 [US1] Playwright E2E (constitution Principle IV): open a webhook delivery, assert payload/request/response/latency are shown and env-sourced headers + signature are masked, in `frontend/app/tests/e2e/webhook-delivery-inspect.spec.ts` (depends on T022). _(added post-analysis; executes within US1)_
- [X] T052 [US1] [Sync: Gap Report] Log the outgoing request on each delivery attempt — target URL, redacted headers, truncated payload at info (full payload at debug), and the attempt number N of M — via a logging helper in `backend/infrahub/webhook/tasks/process.py`, redaction from `backend/infrahub/webhook/models.py` (T012/T013). Interim log-channel visibility (spec FR-015a/FR-015b) delivered ahead of the persisted `http` artifact (T014–T017); landed (IFC-2832, IFC-2833).

**Checkpoint**: A delivery's request/response/payload are fully inspectable in the UI with secrets masked — MVP deliverable.

---

## Phase 4: User Story 2 - Understand why a delivery failed (Priority: P2)

**Goal**: Failed deliveries show a classified reason + remediation hint (no stacktrace in the view or the run logs); the bounded fixed-delay auto-retry applies uniformly (transient-only gating rejected — see T026).

**Independent Test**: Drive CONNECTION / 4xx / 5xx / TLS / TIMEOUT / CONFIG failures; confirm correct classification, a remediation hint matching the class, and no stacktrace in the delivery's logs.

### Implementation for User Story 2

- [X] T024 [P] [US2] Implement the pure `WebhookFailureClassifier.classify(exc, response) -> ClassifiedFailure` (CONFIG/CONNECTION/TLS/TIMEOUT/HTTP_CLIENT_ERROR/HTTP_SERVER_ERROR/UNKNOWN, each with remediation + `transient` flag) in `backend/infrahub/webhook/classifier.py`.
- [X] T025 [US2] Use the classifier in the `webhook_send` body: catch expected delivery failures and surface a clean classified reason without a stacktrace (the `webhook_process` flow settles them into a failed state); let unexpected errors propagate as a genuine crash, in `backend/infrahub/webhook/tasks/process.py` (depends on T024).
- [X] ~~T026 [US2] Add a `retry_condition_fn` (transient-only) reusing the classifier on the `webhook_send` flow, keeping the fixed 120s delay / 3 attempts, in `backend/infrahub/webhook/tasks/process.py` (depends on T024).~~ Descoped: retries stay flow-level and unconditional — a transient-only condition requires task-level `retry_condition_fn`, which we chose not to introduce. The `transient` flag was subsequently removed from `ClassifiedFailure`; each status class now owns its remediation hint directly. Spec FR-012 and SC-004 were rewritten to record this decision (Implementation Sync 2026-07-02).
- [X] T027 [US2] Include the classified error (`status_class`, `message`, `remediation`) in the `http` artifact and map it onto the interface-level `error` field (`TaskError`) in the serializer, in `backend/infrahub/webhook/capture.py` and `backend/infrahub/graphql/queries/task.py` (depends on T024, T017). Landed: `CapturedError` is written into the `http` artifact on a failed attempt and projected onto the `error` field.
- [X] T028 [P] [US2] Unit test the classifier across every class and the transient predicate (using the typed HTTP adapter exceptions + status codes) in `backend/tests/unit/webhook/test_classifier.py`.
- [ ] T029 [P] [US2] Functional test that each failure class surfaces a clean reason, the final reason reflects the settling attempt, and per-attempt progress remains visible in the run logs across retries, in `backend/tests/functional/webhook/test_classification.py` (depends on T025).
- [ ] T030 [US2] Frontend: render the classified reason + remediation hint (badge + hint) from the common `error` field — for any task, not via the delivery fragment — showing the section only when `error` is non-null, in `frontend/app/src/entities/tasks/ui/task-item-details.tsx` (depends on T021).
- [ ] T051 [US2] Playwright E2E (constitution Principle IV): open a failed delivery, assert the classified reason + remediation hint are shown and no stacktrace appears, in `frontend/app/tests/e2e/webhook-delivery-failure.spec.ts` (depends on T030). _(added post-analysis; executes within US2)_
- [X] T053 [US2] [Sync: Gap Report] Suppress the traceback for classified delivery failures in the run logs (spec FR-015c): a delivery error type carrying the classified failure, registered by type as suppressible, while unexpected errors keep their full traceback, in `backend/infrahub/webhook/classifier.py` (depends on T024, T025). Landed (IFC-2846).
- [X] T054 [US2] [Sync: Gap Report] Cover traceback suppression end-to-end in `backend/tests/component/webhook/test_traceback_suppression.py`, and transport-error precedence + per-status-class remediation in `backend/tests/unit/webhook/test_classifier.py` (depends on T053). Landed.

**Checkpoint**: Failures are actionable — classified reason + remediation, smart retry — independently testable.

---

## Phase 5: User Story 3 - Retry a delivery (Priority: P3)

**Goal**: Retry a settled delivery (any terminal state, incl. succeeded) — replays the frozen payload against current config with a fresh signature, as a new run; confirm on every retry.

**Independent Test**: Fail a delivery against a down endpoint; bring it up; retry → new delivery with same payload succeeds; original unchanged. Retry a succeeded delivery → confirmation calls out re-delivery. Retry unavailable while in progress.

### Implementation for User Story 3

- [X] T031 [US3] Read a settled delivery's frozen `parameters` by id for resubmit. Reuses the existing flow-run query (`FlowRunQueryCriteria(ids=[...])`) rather than a new reader method, so no change to `backend/infrahub/task_manager/flow_run/reader.py`.
- [X] T032 [US3] Implement the generic `InfrahubTaskRetry(id)` mutation (validate target is a terminal `WEBHOOK_SEND` run via `available_actions`; not-found → clean "no longer available"; resubmit `WEBHOOK_SEND` with the frozen params; authorize via object-level update permission on the target webhook node) in `backend/infrahub/graphql/mutations/task.py` (depends on T031, T003, T008).
- [X] T033 [US3] Register `InfrahubTaskRetry` as a field on `InfrahubBaseMutation` in `backend/infrahub/graphql/schema.py` (depends on T032).
- [X] T034 [P] [US3] Functional test: terminal-only gating, not-found, and that resubmit creates a new run carrying the same payload with the original left immutable, in `backend/tests/functional/webhook/test_retry.py` (depends on T032, T033). Authz-denied path remains to be added.
- [X] T035 [P] [US3] Frontend retry mutation (api → domain → `useRetryTaskMutation` hook) in `frontend/app/src/entities/tasks/api/retry-task-from-api.ts`, `domain/retry-task/`, and `ui/queries/retry-task.mutation.ts`.
- [X] T036 [US3] Implement the shared `<TaskActions task>` component (reads `available_actions`; `ModalConfirm` with the design's confirmation copy quoting the current state; toast feedback) in `frontend/app/src/entities/tasks/ui/task-actions.tsx` (depends on T035). The design uses one generic confirmation per state rather than a separate succeeded-delivery callout. `ModalConfirm` gained optional label/variant/icon props to serve both actions.
- [X] T037 [US3] Render `<TaskActions>` in the task detail header via `Content.CardTitle`'s `end` slot, in `frontend/app/src/pages/tasks/task-details.tsx` (depends on T036). The row-compact placement is deferred — the design only specifies the detail-header button, which shows the single available action (retry when terminal, cancel when not).
- [ ] T038 [US3] Playwright E2E: retry a failed delivery → a new run is created; retry confirmation quotes the current state, in `frontend/app/tests/e2e/webhook-delivery-retry.spec.ts` (depends on T037). Pending — needs a running full stack to validate. Component-level coverage is in `task-actions.test.tsx`.

**Checkpoint**: Retry works from the row and detail panel, gated server-side, confirmed every time.

---

## Phase 6: User Story 4 - Cancel an in-progress delivery (Priority: P4)

**Goal**: Cancel a non-terminal delivery, stopping further auto-retries; best-effort for an in-flight request; settled deliveries cannot be cancelled.

**Independent Test**: Send a delivery to a slow/failing endpoint so it enters AwaitingRetry; cancel → transitions to cancelled, no further attempts; Cancel disabled on settled deliveries; a cancelled delivery is then retryable.

### Implementation for User Story 4

- [X] T039 [US4] Implement the generic `InfrahubTaskCancel(id)` mutation (validate target is a non-terminal `WEBHOOK_SEND` run via `available_actions`; set state to CANCELLING; authorize via object-level webhook update permission) in `backend/infrahub/graphql/mutations/task.py` (depends on T003, T008). Shares the load/authorize preamble with the retry mutation.
- [X] T040 [US4] Register `InfrahubTaskCancel` as a field on `InfrahubBaseMutation` in `backend/infrahub/graphql/schema.py` (depends on T039).
- [X] T041 [P] [US4] Functional test: cancel of a non-terminal delivery, settled-delivery rejection, authz-denied, and not-found, in `backend/tests/functional/webhook/test_cancel.py` (depends on T039, T040).
- [X] T042 [P] [US4] Frontend cancel mutation (api → domain → `useCancelTaskMutation` hook) in `frontend/app/src/entities/tasks/api/cancel-task-from-api.ts`, `domain/cancel-task/`, and `ui/queries/cancel-task.mutation.ts`.
- [X] T043 [US4] Wire CANCEL into the shared `<TaskActions>` (destructive confirmation + toast) so it renders in the detail header, in `frontend/app/src/entities/tasks/ui/task-actions.tsx` (depends on T036, T042).
- [ ] T044 [US4] Playwright E2E: cancel a non-terminal delivery → destructive confirmation, no further attempts, in `frontend/app/tests/e2e/webhook-delivery-cancel.spec.ts` (depends on T043). Pending — needs a running full stack to validate. Component-level coverage is in `task-actions.test.tsx`.

**Checkpoint**: All four stories independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T045 [P] Regenerate backend generated files and the GraphQL schema (`uv run invoke backend.generate`; `uv run invoke schema.generate-graphqlschema`) and commit the diffs.
- [ ] T046 [P] User documentation for webhook delivery operability (inspection, classified failures, retry, cancel) under `docs/`, and a backend knowledge note under `dev/knowledge/backend/`. Partially landed: retry/cancel, delivery logging + redaction, and traceback suppression are documented in `docs/docs/webhooks/overview.mdx`, `dev/knowledge/backend/webhooks.md`, and `dev/knowledge/backend/async-tasks.md`; the inspection (captured request/response display) documentation remains for US1.
- [ ] T047 [P] Reference-doc regeneration if events/message-bus reference is affected (`uv run invoke docs.generate`).
- [ ] T048 Run `/pre-ci` (format, lint, `ty` type check, generated-file + `docs.validate` checks) and fix any drift.
- [ ] T049 Run `quickstart.md` validation end-to-end across all four user stories.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup; **blocks all user stories**. T003→T004; T005→T006→T007; T003→T008→T009; T010/T011 after their targets.
- **US1 (Phase 3)**: depends on Foundational. The MVP.
- **US2 (Phase 4)**: depends on Foundational; builds on US1's capture (T027 needs T017; T025 needs T015).
- **US3 (Phase 5)**: depends on Foundational; T032 needs `available_actions` (T008) and `WEBHOOK_SEND` (T003).
- **US4 (Phase 6)**: depends on Foundational; shares `<TaskActions>` (T036 from US3) — if US4 runs before US3, create `<TaskActions>` in US4 instead.
- **Polish (Phase 7)**: after the desired stories are complete.

### Story Independence

- US1 is fully independent (capture + display).
- US2 layers onto US1's capture but is independently testable (drive failures, assert classification).
- US3 and US4 are independent of US1/US2 at the backend (mutations + gating), and share one frontend action component; whichever lands first creates `<TaskActions>`.

### Within Each Story

Models/pure components → flow/serializer wiring → tests → frontend query → codegen → UI → E2E.

## Parallel Opportunities

- **Setup**: T001, T002 in parallel.
- **Foundational**: T005 ∥ T008 (different concerns); T010 ∥ T011 after their targets.
- **US1**: T012 ∥ T014 (redaction vs artifact builder); T018 ∥ T019 ∥ T023 (tests, different files).
- **US2**: T024 first; T028 ∥ T029 after wiring.
- **US3/US4**: backend mutation tests (T034, T041) ∥ frontend mutation wiring (T035, T042).
- **Polish**: T045 ∥ T046 ∥ T047.

## Parallel Example: User Story 1

```bash
# Independent backend components:
Task: "CapturedHeaders redaction in backend/infrahub/webhook/capture.py"     # T012
Task: "CapturedHttp artifact builder in backend/infrahub/webhook/capture.py" # T014

# After capture + read-back wired, run the tests in parallel:
Task: "Unit test CapturedHeaders redaction (T018)"
Task: "Functional test capture on success/failure (T019)"
Task: "Frontend unit test delivery detail rendering (T023)"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 Setup → 2. Phase 2 Foundational (typing + `WEBHOOK_SEND` + `available_actions`) → 3. Phase 3 US1.
4. **STOP and VALIDATE**: deliveries are inspectable with secrets masked. Demo.

### Incremental Delivery

Foundational → US1 (inspect) → US2 (classify) → US3 (retry) → US4 (cancel). Each adds operator value without breaking prior stories. Regenerate schema/types and run `/pre-ci` before each push.

### Notes

- `[P]` = different files, no incomplete dependency.
- No source docstring/comment may reference ticket IDs or other code symbols (project rule); IDs live here and in commits only.
- Commit after each task or logical group; never push without explicit approval.
