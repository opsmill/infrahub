# Phase 0 Research: Webhook Delivery Operability

All decisions are grounded in the current branch code (paths are project-relative). Three of these resolve open points from the design doc; the rest record the codebase-anchored approach for each subsystem.

## D1 — Promote `webhook_send` to a registered workflow

**Decision**: Add a `WEBHOOK_SEND` `WorkflowDefinition` to `backend/infrahub/workflows/catalogue.py` and register it in `WORKFLOWS`. `webhook_process` invokes it as a deployment via the existing `submit_workflow` path so each delivery is a standalone, resubmittable run.

**Rationale**: Today `webhook_send` is an inline `@flow(name="webhook-send")` in `backend/infrahub/webhook/tasks/process.py:45` called directly as a subflow (`process.py:154`); it is **not** in the catalogue (only `WEBHOOK_PROCESS`, `WEBHOOK_CONFIGURE`, `WEBHOOK_INVALIDATE_HEADERS` exist). Two features require it to be a registered workflow:
- **Retry** resubmits by workflow name with the frozen parameters (`run_deployment` / `submit_workflow` need a deployment, per `services/adapters/workflow/worker.py:86`).
- **Type discrimination** keys `TASK_TYPES` on the catalogue constant's `name` (`WEBHOOK_SEND.name → WebhookDeliveryTask`); the discriminant is the run's workflow name, already resolved into `EnrichedFlowRun.workflow_name` (`task_manager/flow_run/service.py:85`).

**Alternatives considered**: Keep `webhook_send` an inline subflow and retry by re-invoking `webhook_process` — rejected: that re-runs the transform and re-derives the payload (not a true frozen replay), and re-introduces the orchestrator parent the design deliberately drops for retries.

## D2 — Retry policy: fixed delay, transient-only (resolves spec Q1)

**Decision**: Keep the existing `retries=3, retry_delay_seconds=120` on the `webhook_send` flow and add a `retry_condition_fn` that retries only transient classes (TIMEOUT, CONNECTION, HTTP_SERVER_ERROR). No exponential backoff.

**Rationale**: The clarified spec (FR-012a) mandates fixed ~2-minute delay, transient-only, bounded to 3 attempts; exponential backoff is rejected because a long back-off parks many runs holding execution slots. The current flow already has the fixed delay (`process.py:31-32,48-49`) but retries on every exception. The only change is the condition function, reusing the classifier (D4) so the retry predicate and the surfaced reason agree.

**Alternatives considered**: Prefect `exponential_backoff` + jitter (design-doc original) — rejected per Q1.

## D3 — Capture as one redacted `http` artifact, last attempt (resolves both design open points)

**Decision**: Write a single grouped `http` artifact per run (request + response + error together), reflecting the **last attempt**. The payload is not in the artifact — it is read from the run's frozen parameters.

**Rationale**: The design doc left two open points: (a) one grouped artifact vs separate request/response artifacts, (b) per-attempt vs last-attempt. One artifact keyed per run mirrors the existing `progress` artifact read path exactly (`task_manager/flow_run/reader.py:108`, `read_artifacts(ArtifactFilter(...), FlowRunFilter(id=...))`), so read-back is one batched call and the serializer projection is trivial. Last-attempt matches the operator's mental model (the run shows AwaitingRetry between attempts; only the settling attempt's request/response is meaningful) and avoids unbounded artifact growth. The artifact is written from the `webhook_send` body so Prefect binds it to the visible run id regardless of trigger (event, retry, cron).

**Implementation note**: The existing `progress` artifact stores a float (`type="progress"`). The `http` artifact stores a JSON-serializable dict; use a result/JSON artifact with a fixed key (e.g. `infrahub-webhook-http`) so it is filterable like progress. Confirm artifact `data` accepts a dict at write time and round-trips on read.

**Alternatives considered**: Separate request/response artifacts (two reads, two keys) — rejected for no operator benefit; per-attempt capture (list artifact) — rejected as unbounded and not requested.

## D4 — Pure failure classifier (IFC-2754)

**Decision**: A pure, injected `WebhookFailureClassifier.classify(exc, response) -> ClassifiedFailure` mapping to one of `CONFIG · CONNECTION · TLS · TIMEOUT · HTTP_CLIENT_ERROR · HTTP_SERVER_ERROR · UNKNOWN`, each with a remediation hint. Invoked both in the send body (to build the clean failure message and capture) and by `retry_condition_fn`.

**Rationale**: The `InfrahubHTTP` adapter already raises typed exceptions that map cleanly:
- `HTTPServerSSLError` → TLS, `HTTPServerTimeoutError` → TIMEOUT, `HTTPServerError`/connect failures → CONNECTION (`services/adapters/http/httpx.py:97-106`).
- `response.raise_for_status()` (`webhook/tasks/process.py:41`) raises `httpx.HTTPStatusError`; classify by status → HTTP_CLIENT_ERROR (4xx) / HTTP_SERVER_ERROR (5xx).
- `WebhookHeaderResolutionError` and config-resolution failures → CONFIG.
- anything else → UNKNOWN (re-raised with trace as a genuine crash, per FR-014).

A pure function with injected inputs satisfies the no-mock testing rule and the SOLID/DI guideline. Expected delivery failures are caught and re-raised as a clean `WebhookDeliveryFailed(message)` (no stacktrace); unexpected errors propagate untouched so Prefect can mark a real CRASHED.

**Alternatives considered**: Inline `isinstance` ladder in the flow body — rejected: not unit-testable in isolation and not reusable by the retry condition.

## D5 — Header redaction via `CapturedHeaders` (IFC-2755)

**Decision**: A `CapturedHeaders` domain object redacts at capture time, before the artifact write. Masked: every `HeaderKind.ENVIRONMENT`-sourced custom header and the `webhook-signature` header. Verbatim: standard headers (`Accept`, `Content-Type`), `webhook-id`, `webhook-timestamp`, and `HeaderKind.STATIC` custom headers. The `shared_key` is never in the request (only its derived signature).

**Rationale**: `_build_headers` (`webhook/models.py:255-285`) is the single construction site; header provenance is known from `WebhookHeader.kind`. Redacting before the write guarantees no raw secret is ever persisted (SC-002, Principle VI). `webhook-id`/`webhook-timestamp` are signature inputs but not secret, so they stay verbatim to keep the capture diagnosable.

**Implementation note**: Capture needs the provenance of each header, which is lost once `_build_headers` returns a flat `dict[str, str]`. Have header assembly return (or expose) the resolved headers alongside their `HeaderKind` so `CapturedHeaders` can decide per key, rather than re-guessing from the flat dict.

**Alternatives considered**: Redact by key-name allowlist/denylist — rejected: brittle, misses arbitrary env-sourced custom header keys.

## D6 — Polymorphic task typing mirrors the events hierarchy (IFC-2755 part 1)

**Decision**: Introduce `TaskNodeInterface` carrying all current task fields plus `available_actions`. Keep `TaskNode` as the standard implementation (name unchanged). Add `WebhookDeliveryTask(interfaces=(TaskNodeInterface,))` with `http_request`, `http_response`, `error`. Discriminate via `resolve_type` against `TASK_TYPES = {WEBHOOK_SEND.name: WebhookDeliveryTask}`, fallback `TaskNode`. Register concrete types in the GraphQL manager. Change `TaskNodes.node` from object to interface.

**Rationale**: Directly mirrors the proven events pattern: `EventNodeInterface` + `resolve_type` keyed on a discriminant + `EVENT_TYPES` map + `_load_event_types` registration (`graphql/types/event.py:31-60,313-340`, `graphql/manager.py:245-247`). Current task types are `Task` (object), `TaskNode(Task)`, `TaskNodes.node` (`graphql/types/task.py:16,36,49`). The discriminant (`run.workflow_name`) is already serialized as the `workflow` field (`graphql/queries/task.py:59`). Object→interface on `node` is query-compatible: existing selections of common fields keep resolving; no SDK/fragment/`__typename` breakage because `TaskNode` keeps its name.

**Alternatives considered**: A `task_type` enum/field or a tag — rejected by the design: the workflow name is intrinsic to every run, so historical runs type correctly with no backfill and no extra stored field.

## D7 — Generic, task-id-addressable retry/cancel mutations (IFC-2119, IFC-2753; resolves spec Q on genericity)

**Decision**: Two new mutations, `InfrahubTaskRetry(id)` and `InfrahubTaskCancel(id)`, modeled on the custom (non-CRUD) `BranchCreate` mutation pattern (`graphql/mutations/branch.py:55-114`), registered as direct fields on `InfrahubBaseMutation` (`graphql/schema.py`). They accept a task id and dispatch by the run's workflow type. The mutation **interface** is generic; support is per task type — only `WEBHOOK_SEND` runs are actionable, anything else returns the action as unavailable.

- **Retry**: read the original run's frozen parameters by id (`read_flow_runs` with id filter → `flow_run.parameters`), then `submit_workflow(WEBHOOK_SEND, parameters=...)`. New standalone run; original left immutable.
- **Cancel**: `set_flow_run_state(id, State(type=CANCELLED), force=True)` via the retention client (`task_manager/flow_run/prefect_client.py:85`).

**Rationale**: Honors the clarified directive — the query/mutation surface is generic (not `CoreWebhookCancel`), but genericity is confined to the interface (FR-017). CRUD-schema mutations (`InfrahubMutationMixin`) are the wrong base; `BranchCreate` is the precedent for a bespoke action mutation. Retry retention failure (run purged) surfaces as a clear "not found" (FR-020); config-no-longer-resolves surfaces at runtime on the new run (FR-005-class CONFIG failure, US3 scenario 5).

**Alternatives considered**: Webhook-specific mutations — rejected by Q2/Q3 direction. A generic mutation that every task type implements — rejected: only webhook deliveries support the actions; others resolve unavailable.

## D8 — `available_actions` computed server-side from run state

**Decision**: Compute `available_actions` in the task serializer from the already-fetched run state + workflow type. For a `WEBHOOK_SEND` run: `RETRY` available iff terminal (COMPLETED/FAILED/CRASHED/CANCELLED); `CANCEL` available iff non-terminal (RUNNING/SCHEDULED/PENDING/AwaitingRetry). Each unavailable action carries a reason. Non-webhook runs get an empty list.

**Rationale**: Single source of truth server-side (FR-016, Principle "Backend Authoritative"). Derived from data the task query already loads — no extra round-trip (Principle V). Note the retry gate is **any terminal state including COMPLETED**, per spec Q (FR-018); a succeeded retry is allowed but the UI confirmation calls out re-delivery (FR-021). Mutations re-check availability at execution time and reject a stale action (FR-026).

## D9 — Authorization reuses object-level webhook permission

**Decision**: `TaskRetry`/`TaskCancel` on a webhook delivery authorize against the **object-level update permission on the target webhook node** (resolved from the run's `webhook_id` parameter/tag), via `active_permissions.raise_for_permission(...)` at the mutation layer.

**Rationale**: Research found no `MANAGE_WEBHOOKS` global permission; webhooks are governed by object permissions on the Standard/CustomWebhook nodes (`graphql/manager.py:542-556` maps both kinds to `InfrahubWebhookMutation`; no global permission gate). The clarified spec (FR-027) says "no new permission model", so reuse the existing object update permission rather than add a global one. Authorization is enforced at the API layer (Principle VI).

**Open implementation detail (defer to tasks)**: exact resolution of the webhook node id from a run and the precise permission-decision level (ALLOW_ALL vs branch-scoped) — both determinable during implementation, neither changes the design.

## Resolved unknowns summary

| Unknown | Resolution |
|---|---|
| `webhook_send` not resubmittable / not in catalogue | D1 — register `WEBHOOK_SEND`, invoke as deployment |
| Backoff strategy + attempt count | D2 — fixed 120s, transient-only, 3 attempts |
| One vs two capture artifacts; per-attempt vs last | D3 — one `http` artifact, last attempt |
| Failure taxonomy + retry predicate source | D4 — pure classifier shared by body + retry condition |
| Which headers to mask | D5 — env-sourced + signature masked; rest verbatim |
| Task polymorphism mechanism | D6 — interface + resolve_type on workflow name (mirror events) |
| Mutation shape (generic vs webhook-specific) | D7 — generic by task id, per-type support |
| Where action availability is decided | D8 — server-side from run state, no extra query |
| Authorization model | D9 — object-level webhook update permission, no new global permission |
