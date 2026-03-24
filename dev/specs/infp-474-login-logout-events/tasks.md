# Tasks: Login/Logout Activity Events

**Input**: Design documents from `/specs/infp-474-login-logout-events/`
**Branch**: `infp-474-login-logout-events`
**Generated**: 2026-03-24

> **Implementation status**: Completed tasks are marked `[x]`. Remaining work is marked `[ ]` and is driven by clarifications surfaced after initial implementation (admin-forced logout, SSO failure events, timestamp in GraphQL types).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Paths relative to repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Core infrastructure required before any story work.

- [ ] T001 Add `ACCOUNT_LOGGED_IN`, `ACCOUNT_LOGIN_FAILED`, `ACCOUNT_LOGGED_OUT` to `EventType` enum in `backend/infrahub/core/constants/__init__.py`
- [ ] T002 [P] Create `backend/infrahub/events/auth_action.py` with `AccountLoggedInEvent`, `AccountLoginFailedEvent`, `AccountLoggedOutEvent` (including `timestamp` field on all three)
- [ ] T003 [P] Export the three new event classes in `backend/infrahub/events/__init__.py`
- [ ] T004 Add `AuthResult` frozen dataclass and `AuthenticationError(AuthorizationError)` to `backend/infrahub/auth.py`
- [ ] T005 Add `_fetch_account_groups_and_roles()` helper to `backend/infrahub/auth.py`
- [ ] T006 Refactor `authenticate_with_password()` in `backend/infrahub/auth.py` to return `AuthResult`
- [ ] T007 Refactor `signin_sso_account()` in `backend/infrahub/auth.py` to return `AuthResult`
- [ ] T008 [P] Add changelog fragment `changelog/+infp-474.added.md`

**Checkpoint**: Foundation ready — event classes exist, auth functions return rich metadata.

---

## Phase 2: Foundational (GraphQL Surface)

**Purpose**: Register event types in GraphQL so all stories are queryable via the existing interface.

- [ ] T009 Add `AccountLoggedInEventType`, `AccountLoginFailedEventType`, `AccountLoggedOutEventType` ObjectTypes to `backend/infrahub/graphql/types/event.py`
- [ ] T010 Register all three types in `EVENT_TYPES` dict in `backend/infrahub/graphql/types/event.py`
- [ ] T011 Add `timestamp = DateTime(required=True)` field to `AccountLoggedInEventType`, `AccountLoginFailedEventType`, and `AccountLoggedOutEventType` in `backend/infrahub/graphql/types/event.py`

**Checkpoint**: All three auth event types are queryable via GraphQL with full field coverage including timestamp.

---

## Phase 3: User Story 1 — Authentication Audit Trail (Priority: P1) 🎯 MVP

**Goal**: Successful login and user-initiated logout emit queryable events with full account context.

**Independent Test**: Login as `First Account`, logout, query event feed filtered by `infrahub.account.logged_in` and `infrahub.account.logged_out` — both appear with correct `account_id`, `auth_method`, `session_id`, and matching `session_id` between the two events.

### Implementation — US1 (Password auth + user logout)

- [ ] T012 [US1] Emit `AccountLoggedInEvent` on successful password login in `backend/infrahub/api/auth.py`
- [ ] T013 [US1] Emit `AccountLoggedOutEvent` with `logout_type="user_initiated"` in `backend/infrahub/api/auth.py`
- [ ] T014 [P] [US1] Emit `AccountLoggedInEvent` on successful OAuth2 SSO callback in `backend/infrahub/api/oauth2.py`
- [ ] T015 [P] [US1] Emit `AccountLoggedInEvent` on successful OIDC SSO callback in `backend/infrahub/api/oidc.py`

### Implementation — US1 (Admin-forced logout, FR-011)

- [ ] T016 [US1] Add `POST /api/auth/sessions/{session_id}/invalidate` endpoint (or GraphQL mutation `InfrahubAccountSessionInvalidate`) that calls `invalidate_refresh_token()` and emits `AccountLoggedOutEvent` with `logout_type="admin_forced"` — requires admin role check — implement in `backend/infrahub/api/auth.py` or `backend/infrahub/graphql/mutations/account.py`
- [ ] T017 [US1] Write component test for admin-forced logout event emission in `backend/tests/component/api/test_auth_events.py`

### Tests — US1

- [ ] T018 [P] [US1] Unit tests for `AccountLoggedInEvent.get_resource()` and `get_payload()` in `backend/tests/unit/event/test_auth_action.py`
- [ ] T019 [P] [US1] Unit tests for `AccountLoggedOutEvent.get_resource()` and `get_payload()` in `backend/tests/unit/event/test_auth_action.py`
- [ ] T020 [US1] Component test: successful password login emits `AccountLoggedInEvent` in `backend/tests/component/api/test_auth_events.py`
- [ ] T021 [US1] Component test: user-initiated logout emits `AccountLoggedOutEvent` in `backend/tests/component/api/test_auth_events.py`
- [ ] T022 [P] [US1] Add `timestamp` field assertion to existing unit tests for all three event classes in `backend/tests/unit/event/test_auth_action.py`

**Checkpoint**: US1 fully functional — password login, user logout, and admin-forced logout all emit queryable events.

---

## Phase 4: User Story 2 — Failed Login Detection (Priority: P2)

**Goal**: Every failed authentication attempt (wrong password, unknown user, SSO failure) emits a `AccountLoginFailedEvent` with sufficient detail for security investigation.

**Independent Test**: POST incorrect password to `/api/auth/login`, POST unknown username to `/api/auth/login`, simulate an OAuth2 callback with an invalid `state` parameter — query event feed for `infrahub.account.login_failed` events, confirm three separate events each with distinct `failure_reason` and `timestamp`.

### Implementation — US2

- [ ] T023 [US2] Emit `AccountLoginFailedEvent` on `NodeNotFoundError` (unknown user) in `backend/infrahub/api/auth.py`
- [ ] T024 [US2] Emit `AccountLoginFailedEvent` on `AuthenticationError` (wrong password) in `backend/infrahub/api/auth.py`
- [ ] T025 [P] [US2] Wrap OAuth2 token exchange and userinfo failure paths with `try/except` and emit `AccountLoginFailedEvent` with `auth_method="oauth2"`, `sso_provider=provider_name`, and `failure_reason` from the caught exception in `backend/infrahub/api/oauth2.py`
- [ ] T026 [P] [US2] Wrap OIDC token exchange and userinfo failure paths with `try/except` and emit `AccountLoginFailedEvent` with `auth_method="oidc"`, `sso_provider=provider_name`, and `failure_reason` from the caught exception in `backend/infrahub/api/oidc.py`
- [ ] T027 [US2] Add `attempted_identifier` extraction for SSO failure paths: use the `state` param or provider name as `attempted_identifier` when user info is not yet available in `backend/infrahub/api/oauth2.py` and `backend/infrahub/api/oidc.py`

### Tests — US2

- [ ] T028 [P] [US2] Unit tests for `AccountLoginFailedEvent.get_resource()` with and without `account_id` in `backend/tests/unit/event/test_auth_action.py`
- [ ] T029 [US2] Component test: wrong password emits `AccountLoginFailedEvent` with `account_id` in `backend/tests/component/api/test_auth_events.py`
- [ ] T030 [US2] Component test: unknown user emits `AccountLoginFailedEvent` with `account_id=None` in `backend/tests/component/api/test_auth_events.py`
- [ ] T031 [P] [US2] Component test: invalid OAuth2 `state` parameter emits `AccountLoginFailedEvent` with `auth_method="oauth2"` in `backend/tests/component/api/test_auth_events.py`
- [ ] T032 [P] [US2] Component test: invalid OIDC `state` parameter emits `AccountLoginFailedEvent` with `auth_method="oidc"` in `backend/tests/component/api/test_auth_events.py`

**Checkpoint**: US2 fully functional — every failed auth attempt across all three methods emits a distinct, queryable failed login event.

---

## Phase 5: User Story 3 — Automation Triggers (Priority: P3)

**Goal**: Existing webhook integrations can trigger on auth events without new integration layer work.

**Independent Test**: Configure a webhook trigger for `infrahub.account.logged_in`, authenticate, confirm the webhook fires with the correct payload — no new infrastructure changes required.

### Implementation — US3

- [ ] T033 [US3] Verify `AccountLoggedInEvent`, `AccountLoginFailedEvent`, `AccountLoggedOutEvent` are emitted via `InfrahubEventService.send()` which already delivers to both Prefect (webhook-triggerable) and RabbitMQ — no new code required; existing event bus handles this automatically.

> **Note**: US3 requires no new implementation beyond US1 and US2. The existing `InfrahubEventService` routes all events to Prefect, which powers the webhook trigger mechanism. This story is satisfied automatically once US1 and US2 are complete.

**Checkpoint**: US3 satisfied — all auth events are webhook-triggerable via existing infrastructure.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T034 [P] Run `uv run ruff format` on all modified Python files
- [ ] T035 [P] Run `uv run ruff check --fix` on all modified Python files
- [ ] T036 Run `uv run pytest backend/tests/unit/event/test_auth_action.py backend/tests/component/api/test_auth_events.py -v` and confirm all pass
- [ ] T037 Update `dev/specs/infp-474-login-logout-events/plan.md` to reflect admin-forced logout and SSO failure gaps as completed once T016, T025, T026 are done

---

## Dependencies

```text
Phase 1 (T001–T008) → Phase 2 (T009–T011)
                     ↓
              Phase 3 (T012–T022)    ← can start after T004–T007
              Phase 4 (T023–T032)    ← can start after T002–T003 (event classes exist)
              Phase 5 (T033)         ← depends on Phase 3 + Phase 4 complete
              Phase 6 (T034–T037)    ← final pass
```

US2 (Phase 4) is independent of US1 admin-forced logout work (T016–T017) and can proceed in parallel.

---

## Parallel Execution

**Right now (all independent):**
- T011 — add `timestamp` to GraphQL types
- T022 — add timestamp assertions to unit tests
- T025 + T026 — OAuth2/OIDC failure event emission
- T031 + T032 — OAuth2/OIDC failure component tests

**After T025/T026:**
- T027 — SSO `attempted_identifier` extraction

**Independently:**
- T016 — admin-forced logout endpoint/mutation
- T017 — admin-forced logout component test

---

## Implementation Strategy

**MVP (US1 password + logout already done)**: T011, T022 — small, isolated fixes.

**Next increment (US2 SSO failures)**: T025 → T027 → T031, T032 — complete FR-003 coverage.

**Final increment (US1 admin logout)**: T016 → T017 — requires design decision on endpoint vs mutation.

**Design decision needed for T016**: REST (`DELETE /api/auth/sessions/{session_id}`) is simpler and consistent with the existing `/api/auth/logout` pattern. GraphQL mutation is more consistent with other account management mutations. Recommend REST unless the caller (admin UI) already uses GraphQL for account operations.

---

## Summary

| Phase | Story | Tasks | Done | Remaining |
|-------|-------|-------|------|-----------|
| 1 — Setup | — | 8 | 8 | 0 |
| 2 — GraphQL | — | 3 | 2 | 1 (T011) |
| 3 — US1 Audit Trail | P1 | 10 | 7 | 3 (T016, T017, T022) |
| 4 — US2 Failed Logins | P2 | 10 | 5 | 5 (T025–T027, T031–T032) |
| 5 — US3 Webhooks | P3 | 1 | 1 | 0 |
| 6 — Polish | — | 4 | 2 | 2 (T036, T037) |
| **Total** | | **36** | **25** | **11** |
