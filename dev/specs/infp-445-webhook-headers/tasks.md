# Tasks: Custom HTTP Headers for Webhooks

**Input**: Design documents from `/specs/infp-445-webhook-headers/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Included — the feature spec requires testing for all acceptance scenarios.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Phase 1: Setup (Schema Definitions)

**Purpose**: Define CoreKeyValue schema hierarchy and register in the core schema system

- [x] T001 Create `CoreKeyValue` generic schema and 3 node type schemas (`CoreKeyValueStatic`, `CoreKeyValuePassword`, `CoreKeyValueEnvironmentVariable`) in `backend/infrahub/core/schema/definitions/core/key_value.py`. Generic: `branch=BranchSupportType.AGNOSTIC`, attributes `name` (Text, unique), `key` (Text, required), `description` (Text, optional). Static node: `value` (Text). Password node: `value` (Password kind). EnvVar node: `value` (Text, regex `^[A-Za-z_][A-Za-z0-9_]*$`). All nodes `inherit_from=[InfrahubKind.KEYVALUE]`.
- [x] T002 Add `InfrahubKind` constants for `KEYVALUE`, `KEYVALUESTATIC`, `KEYVALUEPASSWORD`, `KEYVALUEENVIRONMENTVARIABLE` in `backend/infrahub/core/constants/__init__.py` (follow existing pattern for `WEBHOOK`, `STANDARDWEBHOOK`, etc.)
- [x] T003 Register new generic and node schemas in `backend/infrahub/core/schema/definitions/core/__init__.py` — add imports and entries to `core_models_mixed["generics"]` and `core_models_mixed["nodes"]`
- [x] T004 Add `headers` relationship to `core_webhook` generic in `backend/infrahub/core/schema/definitions/core/webhook.py` — `Rel(name="headers", peer=InfrahubKind.KEYVALUE, kind=RelKind.GENERIC, cardinality=Cardinality.MANY, optional=True, order_weight=6000)`
- [x] T005 Regenerate schema and protocol files: run `uv run invoke backend.generate` to update `backend/infrahub/core/schema/generated/` and `backend/infrahub/core/protocols.py`

**Checkpoint**: Schema definitions complete. CoreKeyValue types exist in the schema system. GraphQL CRUD auto-generated.

---

## Phase 2: Foundational (Webhook Model & Cache Extension)

**Purpose**: Extend the webhook runtime model and cache to carry custom header data. MUST complete before user story work.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T006 Add `HeaderConfig` Pydantic model and `custom_headers: list[HeaderConfig]` field to `Webhook` base model in `backend/infrahub/webhook/models.py`. `HeaderConfig` fields: `key: str` (HTTP header name), `value: str` (literal value or env var name), `header_type: str` (one of `"static"`, `"password"`, `"env"`). This automatically extends `to_cache()`/`from_cache()` via `model_dump()`.
- [x] T007 Extend `convert_node_to_webhook` task in `backend/infrahub/webhook/tasks/process.py` to fetch the webhook's `headers` relationship peers (batch query via `client.all()` or relationship traversal), build `list[HeaderConfig]` from each peer's `__typename`/kind, and pass to `Webhook` constructor. Handle all 3 node types mapping to appropriate `header_type`.
- [x] T008 Extend `StandardWebhook.from_object()`, `CustomWebhook.from_object()`, and `TransformWebhook.from_object()` in `backend/infrahub/webhook/models.py` to accept and forward `custom_headers` parameter.

**Checkpoint**: Foundation ready — webhooks carry header data through cache. User story implementation can begin.

---

## Phase 3: User Story 1 — Attach Authentication Headers to a Webhook (Priority: P1) 🎯 MVP

**Goal**: Users can create a password-type key-value pair, link it to a webhook, and have the custom header automatically included in webhook HTTP requests.

**Independent Test**: Create a `CoreKeyValuePassword` with `key=Authorization`, `value=Bearer <token>`. Link to a `CoreStandardWebhook`. Trigger event. Verify HTTP request includes `Authorization: Bearer <token>` header.

### Tests for User Story 1

- [x] T009 [P] [US1] Unit test for header merging logic in `backend/tests/unit/webhook/test_models.py` — verify `_assign_headers()` merges custom headers with system defaults (`Accept`, `Content-Type`, HMAC signature headers). Test that custom header with same name as system header overrides the system default (FR-006).
- [x] T010 [P] [US1] Unit test for `HeaderConfig` serialization roundtrip in `backend/tests/unit/webhook/test_models.py` — verify `to_cache()` includes headers and `from_cache()` reconstructs them correctly.
- [x] T011 [P] [US1] Functional test for webhook with password header in `backend/tests/functional/webhook/test_webhook_headers.py` — create `CoreKeyValuePassword`, link to webhook via `headers` relationship, trigger webhook, assert HTTP request contains the authentication header with correct value.

### Implementation for User Story 1

- [x] T012 [US1] Implement custom header merging in `Webhook._assign_headers()` in `backend/infrahub/webhook/models.py` — after setting system headers and HMAC signature, iterate `self.custom_headers` and add each resolved header. For `static` and `password` types, use value directly. Custom headers override system defaults on name conflict. Log warning if duplicate header names exist among custom headers (last wins).
- [x] T013 [US1] Extend webhook cache invalidation in `backend/infrahub/webhook/triggers.py` — add `CoreKeyValueStatic`, `CoreKeyValuePassword`, `CoreKeyValueEnvironmentVariable` kinds to `TRIGGER_WEBHOOK_CONFIGURE` match filter so that KV node create/update/delete events trigger cache invalidation.
- [x] T014 [US1] Implement cache invalidation handler for KV node changes in `backend/infrahub/webhook/tasks/configure.py` — when a KV node is created/updated/deleted, find all webhooks linked to it via the `headers` relationship, and call `cache.delete(key=f"webhook:{webhook_id}")` for each. Add a new action case in `configure_webhook` flow or extend existing `_configure_one`.

**Checkpoint**: User Story 1 complete. Password-type headers are injected into webhook requests. Cache invalidates on header changes.

---

## Phase 4: User Story 2 — Environment Variable-Based Headers (Priority: P2)

**Goal**: Users can create an env-var-type key-value pair that resolves from the Prefect worker environment at send time.

**Independent Test**: Create `CoreKeyValueEnvironmentVariable` with `key=X-API-Key`, `value=MY_API_KEY`. Set `MY_API_KEY=secret123` in worker env. Link to webhook. Trigger event. Verify header `X-API-Key: secret123`. Unset env var, trigger again, verify header is skipped and warning logged.

### Tests for User Story 2

- [x] T015 [P] [US2] Unit test for env var resolution in `backend/tests/unit/webhook/test_models.py` — verify that `header_type="env"` headers resolve via `os.environ.get()`. Test with set variable (value included) and missing variable (header skipped, no exception).
- [x] T016 [P] [US2] Unit test for warning log on missing env var in `backend/tests/unit/webhook/test_models.py` — verify a warning is logged with the missing variable name when env var is not set (FR-009).

### Implementation for User Story 2

- [x] T017 [US2] Add env var resolution branch in header merging logic in `backend/infrahub/webhook/models.py` `_assign_headers()` — for `header_type="env"`, call `os.environ.get(header.value)`. If `None`, skip the header and log a warning identifying the missing variable name. If present, add resolved value as the header.

**Checkpoint**: User Story 2 complete. Env var headers resolve at send time with graceful handling of missing variables.

---

## Phase 5: User Story 3 — Reuse Headers Across Multiple Webhooks (Priority: P3)

**Goal**: A single key-value pair can be linked to multiple webhooks. Updating the KV value propagates to all linked webhooks on next trigger.

**Independent Test**: Create one `CoreKeyValuePassword`. Link to two webhooks. Trigger both. Verify both include the header. Update the KV value. Trigger again. Verify both use the new value.

### Tests for User Story 3

- [x] T018 [P] [US3] Functional test for shared header across webhooks in `backend/tests/functional/webhook/test_webhook_headers.py` — create one KV, link to two webhooks, trigger both, assert both requests include the header. Update KV value, invalidate cache, trigger again, verify updated value in both.
- [x] T019 [P] [US3] Functional test for header unlink in `backend/tests/functional/webhook/test_webhook_headers.py` — link KV to two webhooks, remove from one, verify the remaining webhook still sends the header while the unlinked one does not.

### Implementation for User Story 3

- [x] T020 [US3] Extend cache invalidation in `backend/infrahub/webhook/tasks/configure.py` to handle KV update events that affect multiple webhooks — when a KV node is updated, query all webhooks linked via `headers` relationship and invalidate each webhook's cache entry. Ensure relationship-change events (header linked/unlinked) also trigger invalidation for the affected webhook.

**Checkpoint**: User Story 3 complete. Shared headers work across webhooks with proper cache invalidation on updates.

---

## Phase 6: User Story 4 — Non-Sensitive Custom Headers (Priority: P3)

**Goal**: Users can create plain-text key-value pairs for non-sensitive routing/metadata headers displayed without masking.

**Independent Test**: Create `CoreKeyValueStatic` with `key=X-Source-System`, `value=infrahub`. Query via GraphQL — verify value is returned in cleartext (not masked). Link to webhook, trigger, verify header in request.

### Tests for User Story 4

- [x] T021 [P] [US4] Functional test for static header in `backend/tests/functional/webhook/test_webhook_headers.py` — create `CoreKeyValueStatic`, link to webhook, trigger, verify header value appears in HTTP request.
- [x] T022 [P] [US4] Unit test verifying static KV value is not masked in `backend/tests/unit/webhook/test_models.py` — query `CoreKeyValueStatic` via GraphQL, assert `value` field returns cleartext (not `***`). Contrast with `CoreKeyValuePassword` which returns `***`.

### Implementation for User Story 4

No additional implementation needed — static headers are already handled by the `header_type="static"` branch implemented in T012. This phase validates correctness through tests only.

**Checkpoint**: User Story 4 validated. Static headers display in cleartext and are sent correctly.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, E2E tests, edge cases, and cleanup

- [x] T023 [P] Add E2E Playwright test for key-value pair CRUD and webhook header association in `frontend/app/tests/e2e/webhook/webhook.spec.ts` — create a `CoreKeyValuePassword` via UI, navigate to webhook, add header association, save, verify header appears in webhook detail view.
- [x] T024 [P] Add user documentation for custom webhook headers in `docs/docs/topics/webhooks.mdx` (or appropriate docs location) — cover all 3 KV types, linking to webhooks, env var setup for Kubernetes workers, header precedence rules.
- [x] T025 [P] Add Towncrier changelog fragment in `changelog/` for the new custom headers feature.
- [x] T026 Run `uv run invoke format` and `uv run invoke lint` to ensure all new code passes formatting and linting gates.
- [x] T027 Run `uv run invoke backend.test-unit` to verify all unit tests pass (including new header tests).
- [x] T028 Run quickstart.md validation — execute the GraphQL mutations from `specs/infp-445-webhook-headers/quickstart.md` against a running instance and verify expected behavior.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Phase 2 — core feature, MVP
- **User Story 2 (Phase 4)**: Depends on Phase 2 — can run in parallel with US1 (different code paths)
- **User Story 3 (Phase 5)**: Depends on Phase 3 (T014 cache invalidation logic)
- **User Story 4 (Phase 6)**: Depends on Phase 3 (T012 header merging) — tests only, no new implementation
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Foundational only — no cross-story dependencies
- **US2 (P2)**: Foundational only — adds env var branch to US1's merging logic but works on separate code path
- **US3 (P3)**: Depends on US1 (cache invalidation infrastructure from T014)
- **US4 (P3)**: Depends on US1 (header merging from T012) — validation only

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Model/schema changes before runtime logic
- Runtime logic before cache/trigger integration
- Story complete before moving to next priority

### Parallel Opportunities

- **Phase 1**: T001 and T002 can run in parallel (different files)
- **Phase 2**: T006 and T007 can run in parallel after Phase 1
- **Phase 3**: T009, T010, T011 (tests) can all run in parallel
- **Phase 4**: T015, T016 (tests) can run in parallel; US2 can start in parallel with US1
- **Phase 5**: T018, T019 (tests) can run in parallel
- **Phase 6**: T021, T022 (tests) can run in parallel
- **Phase 7**: T023, T024, T025 can all run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests together:
Task: "Unit test for header merging logic in backend/tests/unit/webhook/test_models.py"
Task: "Unit test for HeaderConfig serialization roundtrip in backend/tests/unit/webhook/test_models.py"
Task: "Functional test for webhook with password header in backend/tests/functional/webhook/test_webhook_headers.py"

# After tests written and failing, implementation is sequential:
# T012 (merging) → T013 (triggers) → T014 (cache invalidation)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (schema definitions)
2. Complete Phase 2: Foundational (webhook model + cache extension)
3. Complete Phase 3: User Story 1 (password headers + merging + cache invalidation)
4. **STOP and VALIDATE**: Create a password KV, link to webhook, trigger, verify header in HTTP request
5. Deploy/demo if ready — covers the primary customer use case (Ansible EDA auth headers)

### Incremental Delivery

1. Setup + Foundational → Schema and runtime foundation ready
2. Add US1 → Auth headers work → Deploy/Demo (MVP!)
3. Add US2 → Env var headers work → Deploy/Demo
4. Add US3 → Shared headers validated → Deploy/Demo
5. Add US4 → Static headers validated → Deploy/Demo
6. Polish → Docs, E2E, changelog → Release

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (P1) + User Story 3 (depends on US1)
   - Developer B: User Story 2 (P2) + User Story 4 (tests only)
3. Stories integrate cleanly — US2 adds an env var branch, US3/US4 are validation-focused

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- US3 and US4 are lightweight — mostly testing/validation of infrastructure built in US1
