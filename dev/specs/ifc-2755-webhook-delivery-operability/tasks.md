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

- [X] T001 [P] Add towncrier changelog fragment `changelog/+ifc-2755-webhook-delivery-operability.added.md` describing the delivery operability feature (user-facing).
- [ ] T002 [P] Add a controllable HTTP-target test fixture (endpoint that can return success / 4xx / 5xx / timeout / TLS error / be unreachable) under `backend/tests/functional/webhook/conftest.py`, reusing existing webhook fixtures.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Promote `webhook_send` to a registered workflow and stand up the polymorphic task typing + `available_actions`. Mirrors the events GraphQL type derivation (interface + `resolve_type` + name→type map + manager registration).

**⚠️ CRITICAL**: No user story can be completed until this phase is done.

- [X] T003 Register `WEBHOOK_SEND` `WorkflowDefinition` and add it to `WORKFLOWS` in `backend/infrahub/workflows/catalogue.py`.
- [ ] T004 Invoke `webhook_send` as the registered deployment from `webhook_process` (via the `submit_workflow` path) so each delivery is a standalone resubmittable run, in `backend/infrahub/webhook/tasks/process.py` (depends on T003).
- [ ] T005 [P] Add supporting GraphQL types `HttpRequest`, `HttpResponse`, `DeliveryError`, `TaskAction`, and the `TaskActionName` enum (RESEND, CANCEL) in `backend/infrahub/graphql/types/task.py`.
- [ ] T006 Introduce `TaskNodeInterface` (move the current common `Task` fields onto it, add `available_actions`), convert `TaskNode` to `class Meta: interfaces = (TaskNodeInterface,)`, add `WebhookDeliveryTask` (adds `http_request`/`http_response`/`error`), define `TASK_TYPES = {WEBHOOK_SEND.name: WebhookDeliveryTask}` + `resolve_type`, and change `TaskNodes.node` to the interface, in `backend/infrahub/graphql/types/task.py` (depends on T005, T003).
- [ ] T007 Register the concrete task types so they are reachable via `resolve_type` (mirror `_load_event_types`) in `backend/infrahub/graphql/manager.py` (depends on T006).
- [X] T008 [P] Implement the `available_actions` computation as a dedicated pure function/module from `(workflow_name, prefect_state)` — RESEND iff terminal (incl. COMPLETED), CANCEL iff non-terminal, empty for non-webhook runs, each with `unavailability_reason` — unit-testable in isolation, in `backend/infrahub/graphql/queries/task_actions.py` (depends on T003).
- [ ] T009 Wire `available_actions` into the task serializer (`_serialize_node`) so every task node carries it, in `backend/infrahub/graphql/queries/task.py` (depends on T008, T006).
- [X] T010 [P] Unit test the `available_actions` gating matrix (terminal/non-terminal, webhook vs other) in `backend/tests/unit/webhook/test_available_actions.py` (depends on T008).
- [ ] T011 [P] Component test that `resolve_type` returns `WebhookDeliveryTask` for `webhook_send` runs and `TaskNode` otherwise, and that existing common-field selections still resolve, in `backend/tests/component/graphql/queries/test_task.py` (depends on T007).

**Checkpoint**: Tasks are polymorphically typed; webhook deliveries resolve to `WebhookDeliveryTask`; `available_actions` is populated; `webhook_send` is resubmittable. **Regenerate and commit the GraphQL schema + frontend types now** — the object→interface change alters `schema/schema.graphql` — and re-run regeneration at each subsequent increment so the generated-file CI gate stays green (don't defer all regen to Polish).

---

## Phase 3: User Story 1 - Inspect what a delivery sent and received (Priority: P1) 🎯 MVP

**Goal**: Operators see the payload, request (URL + redacted headers), response (status, body, latency) for any delivery, reflecting the last attempt.

**Independent Test**: Trigger a delivery to a test endpoint; open it; confirm payload/request/response/latency are shown and that env-sourced headers + the signature are masked while static/standard headers and the payload are verbatim.

### Implementation for User Story 1

- [X] T012 [P] [US1] Implement the `CapturedHeaders` redaction domain object (mask ENVIRONMENT-sourced headers + `webhook-signature`; keep standard, `webhook-id`, `webhook-timestamp`, and STATIC headers verbatim) in `backend/infrahub/webhook/capture.py`.
- [ ] T013 [US1] Expose per-header provenance (`HeaderKind`) from header assembly so capture can redact by kind rather than re-guessing the flat dict, in `backend/infrahub/webhook/models.py` (depends on T012).
- [ ] T014 [P] [US1] Implement captured request/response models and the `CapturedHttp` artifact builder (one grouped `http` payload: request, response, error) in `backend/infrahub/webhook/capture.py`.
- [ ] T015 [US1] Write the redacted `http` artifact (key `infrahub-webhook-http`, last attempt) on both success and failure inside the `webhook_send` body, in `backend/infrahub/webhook/tasks/process.py` (depends on T014, T013).
- [ ] T016 [US1] Read the `http` artifact back (mirror `read_progress`: `read_artifacts(ArtifactFilter(key), FlowRunFilter(id))`) in `backend/infrahub/task_manager/flow_run/reader.py`.
- [ ] T017 [US1] Project the captured artifact onto `http_request`/`http_response`/`error` in the serializer, gated on the GraphQL selection; payload continues to come from `parameters`, in `backend/infrahub/graphql/queries/task.py` (depends on T016, T006).
- [X] T018 [P] [US1] Unit test `CapturedHeaders` redaction (env + signature masked; standard/static + payload verbatim; no raw secret) in `backend/tests/unit/webhook/test_captured_headers.py`.
- [ ] T019 [P] [US1] Functional test that capture is present on success and failure, reflects the last attempt, and persists no raw secret, in `backend/tests/functional/webhook/test_capture.py` (depends on T015, T016).
- [ ] T020 [P] [US1] Extend the task-list and task-details queries with `available_actions` and `... on WebhookDeliveryTask { http_request http_response error }` in `frontend/app/src/entities/tasks/api/get-task-list-from-api.ts` and `get-task-details-from-api.ts`.
- [ ] T021 [US1] Regenerate frontend GraphQL types (`cd frontend/app && pnpm codegen`) (depends on T020 and backend schema types T006).
- [ ] T022 [US1] Render the webhook delivery section (payload from `parameters`, request incl. target URL, response, latency, HTTP status, last-attempt timestamp) polymorphically by `__typename` in `frontend/app/src/entities/tasks/ui/task-item-details.tsx` (depends on T021).
- [ ] T023 [P] [US1] Frontend unit test for the delivery detail rendering (request/response/redacted headers shown) in `frontend/app/src/entities/tasks/ui/task-item-details.test.tsx` (depends on T022).
- [ ] T050 [US1] Playwright E2E (constitution Principle IV): open a webhook delivery, assert payload/request/response/latency are shown and env-sourced headers + signature are masked, in `frontend/app/tests/e2e/webhook-delivery-inspect.spec.ts` (depends on T022). _(added post-analysis; executes within US1)_

**Checkpoint**: A delivery's request/response/payload are fully inspectable in the UI with secrets masked — MVP deliverable.

---

## Phase 4: User Story 2 - Understand why a delivery failed (Priority: P2)

**Goal**: Failed deliveries show a classified reason + remediation hint (no stacktrace); only transient classes are auto-retried.

**Independent Test**: Drive CONNECTION / 4xx / 5xx / TLS / TIMEOUT / CONFIG failures; confirm correct classification, remediation hint, no stacktrace, and that only TIMEOUT/CONNECTION/5xx are retried.

### Implementation for User Story 2

- [X] T024 [P] [US2] Implement the pure `WebhookFailureClassifier.classify(exc, response) -> ClassifiedFailure` (CONFIG/CONNECTION/TLS/TIMEOUT/HTTP_CLIENT_ERROR/HTTP_SERVER_ERROR/UNKNOWN, each with remediation + `transient` flag) in `backend/infrahub/webhook/classifier.py`.
- [ ] T025 [US2] Use the classifier in the `webhook_send` body: catch expected delivery failures and re-raise a clean `WebhookDeliveryFailed(message)` (no stacktrace); let unexpected errors propagate as a genuine crash, in `backend/infrahub/webhook/tasks/process.py` (depends on T024, T015).
- [ ] T026 [US2] Add a `retry_condition_fn` (transient-only) reusing the classifier on the `webhook_send` flow, keeping the fixed 120s delay / 3 attempts, in `backend/infrahub/webhook/tasks/process.py` (depends on T024).
- [ ] T027 [US2] Include the classified error (`status_class`, `message`, `remediation`) in the `http` artifact and map it onto `DeliveryError` in the serializer, in `backend/infrahub/webhook/capture.py` and `backend/infrahub/graphql/queries/task.py` (depends on T024, T017).
- [X] T028 [P] [US2] Unit test the classifier across every class and the transient predicate (using the typed HTTP adapter exceptions + status codes) in `backend/tests/unit/webhook/test_classifier.py`.
- [ ] T029 [P] [US2] Functional test that each failure class surfaces a clean reason, only transient classes retry, the final reason reflects the settling attempt, and per-attempt progress remains visible in the run logs across retries, in `backend/tests/functional/webhook/test_classification.py` (depends on T025, T026).
- [ ] T030 [US2] Frontend: render the classified reason + remediation hint (badge + hint) for failed deliveries in `frontend/app/src/entities/tasks/ui/task-item-details.tsx` (depends on T021).
- [ ] T051 [US2] Playwright E2E (constitution Principle IV): open a failed delivery, assert the classified reason + remediation hint are shown and no stacktrace appears, in `frontend/app/tests/e2e/webhook-delivery-failure.spec.ts` (depends on T030). _(added post-analysis; executes within US2)_

**Checkpoint**: Failures are actionable — classified reason + remediation, smart retry — independently testable.

---

## Phase 5: User Story 3 - Resend a delivery (Priority: P3)

**Goal**: Resend a settled delivery (any terminal state, incl. succeeded) — replays the frozen payload against current config with a fresh signature, as a new run; confirm on every resend.

**Independent Test**: Fail a delivery against a down endpoint; bring it up; resend → new delivery with same payload succeeds; original unchanged. Resend a succeeded delivery → confirmation calls out re-delivery. Resend unavailable while in progress.

### Implementation for User Story 3

- [ ] T031 [US3] Read a flow run's frozen `parameters` by id (for resubmit) in `backend/infrahub/task_manager/flow_run/reader.py`.
- [ ] T032 [US3] Implement the generic `InfrahubTaskResend(id)` mutation (validate target is a terminal `WEBHOOK_SEND` run; retention not-found → clean "delivery no longer available"; resubmit `WEBHOOK_SEND` with the frozen params; authorize via object-level update permission on the target webhook node; re-validate availability at execution) in `backend/infrahub/graphql/mutations/task.py` (depends on T031, T003, T008).
- [ ] T033 [US3] Register `InfrahubTaskResend` as a field on `InfrahubBaseMutation` in `backend/infrahub/graphql/schema.py` (depends on T032).
- [ ] T034 [P] [US3] Functional test: resend authz, terminal-only gating (incl. COMPLETED allowed), retention not-found, and that resubmit creates a new run carrying the same payload with the original left immutable, in `backend/tests/functional/webhook/test_resend.py` (depends on T032, T033).
- [ ] T035 [P] [US3] Frontend resend mutation (api → domain → `useResendDelivery` hook) in `frontend/app/src/entities/tasks/api/`, `domain/`, and `ui/queries/`.
- [ ] T036 [US3] Implement the shared `<TaskActions task>` component (reads `available_actions`; `ModalConfirm` with confirm-on-every-resend and a succeeded-delivery re-delivery callout; toast feedback) in `frontend/app/src/entities/tasks/ui/task-actions.tsx` (depends on T035).
- [ ] T037 [US3] Render `<TaskActions>` in the delivery row (compact + tooltip for unavailable reason) and the detail panel (labeled), in `frontend/app/src/entities/tasks/ui/task-items.tsx` and `task-item-details.tsx` (depends on T036).
- [ ] T038 [US3] Playwright E2E: resend a failed delivery → a new delivery succeeds; resend a succeeded delivery → confirmation calls out re-delivery, in `frontend/app/tests/e2e/webhook-delivery-resend.spec.ts` (depends on T037).

**Checkpoint**: Resend works from the row and detail panel, gated server-side, confirmed every time.

---

## Phase 6: User Story 4 - Cancel an in-progress delivery (Priority: P4)

**Goal**: Cancel a non-terminal delivery, stopping further auto-retries; best-effort for an in-flight request; settled deliveries cannot be cancelled.

**Independent Test**: Send a delivery to a slow/failing endpoint so it enters AwaitingRetry; cancel → transitions to cancelled, no further attempts; Cancel disabled on settled deliveries; a cancelled delivery is then resendable.

### Implementation for User Story 4

- [ ] T039 [US4] Implement the generic `InfrahubTaskCancel(id)` mutation (validate target is a non-terminal `WEBHOOK_SEND` run; set state to CANCELLING with force; authorize via object-level webhook update permission; re-validate availability at execution) in `backend/infrahub/graphql/mutations/task.py` (depends on T003, T008).
- [ ] T040 [US4] Register `InfrahubTaskCancel` as a field on `InfrahubBaseMutation` in `backend/infrahub/graphql/schema.py` (depends on T039).
- [ ] T041 [P] [US4] Functional test: cancel flips a non-terminal run to cancelling without recalling an in-flight attempt, is rejected on settled runs, enforces authz, and a cancelled delivery is resendable, in `backend/tests/functional/webhook/test_cancel.py` (depends on T039, T040).
- [ ] T042 [P] [US4] Frontend cancel mutation (api → domain → `useCancelDelivery` hook) in `frontend/app/src/entities/tasks/api/`, `domain/`, and `ui/queries/`.
- [ ] T043 [US4] Wire CANCEL into the shared `<TaskActions>` (confirm + toast) so it renders in the row and detail panel, in `frontend/app/src/entities/tasks/ui/task-actions.tsx` (depends on T036, T042).
- [ ] T044 [US4] Playwright E2E: cancel an awaiting-retry delivery → no further attempts; then resend it, in `frontend/app/tests/e2e/webhook-delivery-cancel.spec.ts` (depends on T043).

**Checkpoint**: All four stories independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T045 [P] Regenerate backend generated files and the GraphQL schema (`uv run invoke backend.generate`; `uv run invoke schema.generate-graphqlschema`) and commit the diffs.
- [ ] T046 [P] User documentation for webhook delivery operability (inspection, classified failures, resend, cancel) under `docs/`, and a backend knowledge note under `dev/knowledge/backend/`.
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

Foundational → US1 (inspect) → US2 (classify) → US3 (resend) → US4 (cancel). Each adds operator value without breaking prior stories. Regenerate schema/types and run `/pre-ci` before each push.

### Notes

- `[P]` = different files, no incomplete dependency.
- No source docstring/comment may reference ticket IDs or other code symbols (project rule); IDs live here and in commits only.
- Commit after each task or logical group; never push without explicit approval.
