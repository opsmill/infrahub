---
description: "Task list for Frontend Request Prioritization (X-Priority) — IFC-2890"
---

# Tasks: Frontend Request Prioritization (`X-Priority`)

**Input**: Design documents from `specs/ifc-2890-frontend-request-priority/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: INCLUDED — the spec's Testing Decisions and Constitution IV (Test Discipline) explicitly require them. Tests assert the *observable outbound header* per transport and per query class, not injection internals.

**Organization**: Tasks are grouped by user story (spec priorities) so each story is an independently testable increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US6 map to the spec's user stories
- All paths are repo-relative. Frontend root: `frontend/app/`. Backend root: `backend/`.

## Path Conventions (this feature)

- New contract module: `frontend/app/src/shared/api/priority/`
- Transports: `frontend/app/src/shared/api/graphql/`, `.../rest/`, `frontend/app/src/shared/libs/graphiql/`
- Backend CORS: `backend/infrahub/config.py`; backend tests: `backend/tests/component/api/`, `backend/tests/unit/config/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the location for the new contract module; no dependencies.

- [X] T001 Create the `frontend/app/src/shared/api/priority/` directory for the new `RequestPriority` contract module (per plan Project Structure).
- [X] T002 [P] Add a Towncrier changelog fragment under `changelog/` describing the frontend `X-Priority` emitter + CORS allow-header addition (Constitution: user-facing change).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The typed `RequestPriority` contract that every transport consumes. MUST complete before any transport work.

**⚠️ CRITICAL**: No transport injection (US1) or opt-in (US2) can begin until this phase is complete.

- [X] T003 [US-shared] Implement the contract in `frontend/app/src/shared/api/priority/index.ts`: export `type RequestPriority = 'high' | 'low'`, `const DEFAULT_PRIORITY: RequestPriority = 'high'`, `const PRIORITY_HEADER = 'X-Priority'`, and a `resolvePriority(value: unknown): RequestPriority` normalizer that returns `'low'` only for exactly `'low'` and `DEFAULT_PRIORITY` otherwise (data-model normalization rule, critique E1).
- [X] T004 [P] [US-shared] Unit-test the contract in `frontend/app/src/shared/api/priority/index.test.ts`: `resolvePriority` maps `'low'→'low'`, `'high'/'normal'/undefined/garbage→'high'`; assert the constant values (`X-Priority`, default `high`).

**Checkpoint**: Contract module ready — transport work can begin.

---

## Phase 3: User Story 1 - Frontend traffic wins under overload (Priority: P1) 🎯 MVP

**Goal**: Every frontend-originated request carries `X-Priority: high` by default across all four transports; nothing is emitted `normal`/unheadered.

**Independent Test**: Intercept an outbound request on each transport in a normal flow → asserts `X-Priority: high`; audit finds no `normal`/unheadered frontend path.

### Tests for User Story 1 ⚠️ (write first, ensure they FAIL)

- [X] T005 [P] [US1] GraphQL default test in `frontend/app/src/shared/api/graphql/graphqlClientApollo.test.ts`: an operation with no `context.priority` produces an outbound request with `X-Priority: high` (mirror existing `makeOperation`/`setContext`/`Observable.of` patterns).
- [X] T006 [P] [US1] REST default test in `frontend/app/src/shared/api/rest/client.test.ts`: a request with no priority option carries `X-Priority: high` after `authMiddleware.onRequest`.
- [X] T007 [P] [US1] Raw-fetch default test in `frontend/app/src/shared/api/rest/fetch.test.ts`: `fetchUrl` to an Infrahub-API URL carries `X-Priority: high`.
- [X] T008 [P] [US1] GraphiQL fetcher test in `frontend/app/src/shared/libs/graphiql/use-graphiql-fetcher.test.ts`: the sandbox fetch carries `X-Priority: high`.

### Implementation for User Story 1

- [X] T009 [US1] Add a `setContext` priority link in `frontend/app/src/shared/api/graphql/graphqlClientApollo.tsx` and insert it into `from([errorLink, authLink, priorityLink, httpLink])`; set `headers[PRIORITY_HEADER] = resolvePriority(context.priority)`. (Uploads ride the shared `createUploadLink`, so they inherit it — verifies part of US4.)
- [X] T010 [US1] In `frontend/app/src/shared/api/rest/client.ts` `authMiddleware.onRequest`, `request.headers.set(PRIORITY_HEADER, resolvePriority(options?.priority))` — set BEFORE the `requestClones` clone is captured so the replay inherits it (part of US4).
- [X] T011 [US1] In `frontend/app/src/shared/api/rest/fetch.ts` `fetchUrl`, set `PRIORITY_HEADER` to `resolvePriority(...)` ONLY when the URL's origin matches `INFRAHUB_API_SERVER_URL`'s origin (origin comparison, critique E3 / FR-007).
- [X] T012 [US1] In `frontend/app/src/shared/libs/graphiql/use-graphiql-fetcher.ts`, add `PRIORITY_HEADER: 'high'` to the fetch headers so no frontend request is unheadered (FR-003).

**Checkpoint**: MVP — every transport emits `high` by default; T005–T008 pass. Deliverable on its own.

---

## Phase 4: User Story 2 - Developer marks a background load `low` (Priority: P2)

**Goal**: A single per-query opt-in emits `X-Priority: low`; undeclared queries stay `high`. (Extends the same transport files as US1.)

**Independent Test**: Define one declared-`low` query and one undeclared → declared emits `low`, undeclared emits `high`, no call-site change needed to inherit.

### Tests for User Story 2 ⚠️

- [X] T013 [P] [US2] GraphQL opt-in test in `graphqlClientApollo.test.ts`: operation with `context: { priority: 'low' }` → `X-Priority: low`.
- [X] T014 [P] [US2] REST opt-in test in `rest/client.test.ts`: request with `{ priority: 'low' }` option → `X-Priority: low`.
- [X] T015 [P] [US2] Raw-fetch opt-in test in `rest/fetch.test.ts`: `fetchUrl(url, payload, { priority: 'low' })` → `X-Priority: low`.

### Implementation for User Story 2

- [X] T016 [US2] Confirm/extend the GraphQL priority link (T009) reads `operation.getContext().priority` through `resolvePriority`; document the opt-in convention `context: { priority: 'low' }` in `frontend/app/src/shared/api/priority/index.ts` (JSDoc + a typed helper if it reduces boilerplate). Depends on T009.
- [X] T017 [US2] Extend `authMiddleware`/`apiClient` typing in `rest/client.ts` so a per-request `priority?: RequestPriority` option is accepted and read in `onRequest`. Depends on T010.
- [X] T018 [US2] Add the optional `priority?: RequestPriority` argument to `fetchUrl` in `rest/fetch.ts` (default via `resolvePriority`). Depends on T011.

**Checkpoint**: US1 + US2 work; the `low` path is exercised by synthetic declared-`low` queries in tests (no real background load exists in v1 — see research §open-question-2).

---

## Phase 5: User Story 3 - Watched live-status stays `high` (Priority: P2)

**Goal**: Watched polls (task list/status, proposed-change details/events, branch action state) emit `high` and are never declared `low`.

**Independent Test**: Assert `high` on those specific queries; audit confirms none is declared `low`.

### Tests for User Story 3 ⚠️

- [X] T019 [P] [US3] Test in `frontend/app/src/entities/tasks/ui/task-display.test.tsx` (or a colocated test) that the task-list poll (`get-task-list.query.ts`) and task-status poll (`is-task-running-on-branch.query.ts`) emit `X-Priority: high`.
- [X] T020 [P] [US3] Test in `frontend/app/src/entities/proposed-changes/` that proposed-change details (`get-proposed-change-details.query.ts`) and events (`get-events.query.ts`) polls emit `X-Priority: high`.
- [X] T021 [P] [US3] Test in `frontend/app/src/entities/branches/` that the branch-action-state poll (`get-branch-action-state.query.ts`) emits `X-Priority: high`.

### Implementation for User Story 3

- [X] T022 [US3] Audit the watched-status query definitions (task list/count/details, PC details/events, branch action state) and confirm NONE declares `priority: 'low'` — they inherit the `high` default. No code change expected; record the audit result inline in the PR description. (Guards SC-002 / FR-005.)

**Checkpoint**: Watched data provably stays `high` despite polling.

---

## Phase 6: User Story 4 - Header survives request rebuilds (Priority: P2)

**Goal**: The header is preserved across 401→refresh replay (GraphQL + REST) and file upload.

**Independent Test**: Force a 401 replay and an upload → header re-carried.

### Tests for User Story 4 ⚠️

- [X] T023 [P] [US4] GraphQL replay test in `graphqlClientApollo.test.ts`: simulate `TOKEN_EXPIRED` → `retryWithRefreshedToken`; assert the replayed operation still carries its original `X-Priority` (relies on `...oldHeaders` spread).
- [X] T024 [P] [US4] REST replay test in `rest/client.test.ts`: simulate a 401 → stored-clone replay; assert the clone carries `X-Priority`.
- [X] T025 [P] [US4] Upload test in `frontend/app/src/entities/nodes/object/api/create-object-from-api.test.ts` (or colocated): a multipart mutation via the shared upload link carries `X-Priority: high`.

### Implementation for User Story 4

- [X] T026 [US4] Verify the injection order guarantees preservation: GraphQL sets the header via `context` (spread on replay); REST sets the header before clone capture. Adjust T009/T010 ordering only if a test reveals a gap. No new module expected.

**Checkpoint**: No interactive request degrades to `normal` after a rebuild (SC-003).

---

## Phase 7: User Story 5 - Cross-origin deployment accepts the header (Priority: P2)

**Goal**: The API's CORS allow-list permits `x-priority`, and the preflight is not shed by admission.

**Independent Test**: OPTIONS preflight with `Access-Control-Request-Headers: x-priority` → response allow-lists `x-priority` and is not rejected.

### Tests for User Story 5 ⚠️

- [X] T027 [P] [US5] Component test in `backend/tests/component/api/test_cors_priority.py`: FastAPI `TestClient` issues an `OPTIONS` preflight with `Access-Control-Request-Headers: x-priority`; assert `Access-Control-Allow-Headers` includes `x-priority`. Mirror `test_admission_middleware.py` setup.
- [X] T028 [P] [US5] Unit test in `backend/tests/unit/config/test_config.py`: `default_cors_allow_headers()` includes `"x-priority"`.

### Implementation for User Story 5

- [X] T029 [US5] Append `"x-priority"` to `default_cors_allow_headers()` in `backend/infrahub/config.py` (~lines 50-51), preserving lowercase style. (Governance "Ask First" — security-adjacent CORS change; additive only.)
- [X] T030 [US5] Verify the admission layer exempts CORS `OPTIONS` preflight (critique E2): inspect `backend/infrahub/api/admission/middleware.py` — if `OPTIONS`/preflight is NOT exempt, add the exemption so preflights are not shed under load; extend `test_cors_priority.py` to assert the preflight succeeds even with a saturated/again-gated admission pool if feasible. Record the finding (exempt-or-fixed) in the PR.

**Checkpoint**: Cross-origin (dev/split-host) requests carrying `X-Priority` succeed, under load too.

---

## Phase 8: User Story 6 - Operator confirms adoption via metrics (Priority: P3)

**Goal**: Confirm frontend adoption is observable.

**Independent Test**: Drive representative flows → `infrahub_admission_missing_priority_total` stays ~0 for frontend-origin traffic (validated per spec Assumption on the unlabeled counter).

- [X] T031 [US6] Add the E2E scenario `frontend/app/tests/e2e/` asserting: interactive flow → all captured outbound requests carry `X-Priority: high`; a background-tagged (synthetic `low`) flow → `low`; none `normal`. (Contracts: request-priority.contract.md; SC-001/SC-002.)
- [X] T032 [US6] Document the metric check in the PR / quickstart follow-up: with a running stack, `curl /metrics | grep infrahub_admission_missing_priority_total` trends to its non-frontend floor (spec Assumption, SC-001). No code change.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [ ] T033 [P] Run `pnpm biome:fix` and `pnpm test src/shared/api` in `frontend/app/`; fix any lint/type issues (Constitution quality gates).
- [ ] T034 [P] Run `uv run invoke format lint` and `uv run invoke backend.test-unit -- -k "cors and priority"` for the backend change.
- [ ] T035 Run the full [quickstart.md](./quickstart.md) validation checklist end-to-end and check off its "Done when" items.
- [ ] T036 [P] Update frontend transport knowledge doc under `dev/knowledge/frontend/` noting the `X-Priority` emitter + the `low` opt-in convention (Constitution documentation requirement).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup; **blocks all stories** (every transport imports the contract).
- **US1 (Phase 3)**: depends on Phase 2. The MVP.
- **US2 (Phase 4)**: depends on US1 — extends the *same* transport files (T016←T009, T017←T010, T018←T011). Not parallel with US1 on shared files.
- **US3 (Phase 5)**: depends on US1 (needs the default injection to assert `high`). Independent of US2.
- **US4 (Phase 6)**: depends on US1 (injection points). Largely verification.
- **US5 (Phase 7)**: **fully independent** — backend-only; can run in parallel with all frontend stories from the start.
- **US6 (Phase 8)**: depends on US1–US2 (needs high+low emitting) for the E2E.
- **Polish (Phase 9)**: after desired stories complete.

### Parallel Opportunities

- T002 (changelog) ∥ everything.
- **US5 (backend, T027–T030)** can proceed in parallel with the entire frontend track — no shared files.
- Within US1: T005–T008 (tests, different files) run in parallel; T009–T012 (different files) run in parallel.
- Within US2: T013–T015 parallel.
- Within US3: T019–T021 parallel.
- Within US4: T023–T025 parallel.

---

## Parallel Example: User Story 1

```bash
# Tests first (different files, parallel):
Task: "GraphQL default test in graphqlClientApollo.test.ts"        # T005
Task: "REST default test in rest/client.test.ts"                   # T006
Task: "Raw-fetch default test in rest/fetch.test.ts"               # T007
Task: "GraphiQL fetcher test in use-graphiql-fetcher.test.ts"      # T008

# Then implementation (different files, parallel):
Task: "Priority link in graphqlClientApollo.tsx"                   # T009
Task: "onRequest header in rest/client.ts"                         # T010
Task: "fetchUrl header (origin-guarded) in rest/fetch.ts"          # T011
Task: "GraphiQL fetch header in use-graphiql-fetcher.ts"           # T012
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational (contract) → 3. Phase 3 US1 (default `high` on all transports) → **STOP & VALIDATE** (T005–T008 pass) → shippable MVP: every frontend request is now distinguishable from background traffic.

### Incremental Delivery

MVP (US1) → US2 (`low` opt-in) → US3 (watched-status assertions) → US4 (rebuild preservation) → US5 (CORS, parallelizable early) → US6 (E2E + metric). Each adds value without breaking the previous.

### Suggested MVP scope

Phase 1 + Phase 2 + Phase 3 (US1). US5 (backend CORS) is small and independent — bundle it into the MVP PR so cross-origin dev isn't broken by the new header.

---

## Notes

- [P] = different files, no incomplete-task dependency.
- US1 and US2 edit the same transport files → sequential per file (US2 extends US1), not cross-story parallel there.
- The `low` set is empty in v1: the opt-in is proven by synthetic tests + the E2E, not by demoting real interactive/watched traffic.
- Tests assert the observable outbound header, never injection internals (spec Testing Decisions).
- Commit after each task or logical group; verify tests FAIL before implementing.
