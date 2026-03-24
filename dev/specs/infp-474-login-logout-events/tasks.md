# Tasks: Login/Logout Activity Events

**Input**: Design documents from `/specs/infp-474-login-logout-events/`
**Branch**: `infp-474-login-logout-events`
**Generated**: 2026-03-24

> **Scope**: Only US1 (Authentication Audit Trail) is in scope. US2 (Failed Login Detection) and US3 (Automation Triggers) have been removed. `infrahub.account.*` events are admin-only (FR-005).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Paths relative to repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Core infrastructure required before any story work.

- [x] T001 Add `ACCOUNT_LOGGED_IN`, `ACCOUNT_LOGGED_OUT` to `EventType` enum in `backend/infrahub/core/constants/__init__.py`
- [x] T002 [P] Create `backend/infrahub/events/account_action.py` with `AccountLoggedInEvent`, `AccountLoggedOutEvent` (including `timestamp` field on both)
- [x] T003 [P] Export the two new event classes in `backend/infrahub/events/__init__.py`
- [x] T004 Add `AuthResult` frozen dataclass to `backend/infrahub/auth.py`
- [x] T005 Add `_fetch_account_groups_and_roles()` helper to `backend/infrahub/auth.py`
- [x] T006 Refactor `authenticate_with_password()` in `backend/infrahub/auth.py` to return `AuthResult`
- [x] T007 Refactor `signin_sso_account()` in `backend/infrahub/auth.py` to return `AuthResult`
- [x] T008 [P] Add changelog fragment `changelog/+infp-474.added.md`

**Checkpoint**: Foundation ready — event classes exist, auth functions return rich metadata.

---

## Phase 2: Foundational (GraphQL Surface)

**Purpose**: Register event types in GraphQL so all stories are queryable via the existing interface.

- [ ] T009 Add `AccountLoggedInEventType`, `AccountLoggedOutEventType` ObjectTypes to `backend/infrahub/graphql/types/event.py`
- [ ] T010 Register both types in `EVENT_TYPES` dict in `backend/infrahub/graphql/types/event.py`
- [ ] T011 Add `timestamp = DateTime(required=True)` field to `AccountLoggedInEventType` and `AccountLoggedOutEventType` in `backend/infrahub/graphql/types/event.py`
- [ ] T012 [P] Add admin role check to `infrahub.account.*` event queries in `backend/infrahub/graphql/types/event.py` — non-admin requests must receive an authorization error

**Checkpoint**: Both auth event types are queryable via GraphQL (with full field coverage including timestamp) by admin users only.

---

## Phase 3: User Story 1 — Authentication Audit Trail (Priority: P1) 🎯 MVP

**Goal**: Successful login and user-initiated logout emit queryable events with full account context.

**Independent Test**: Login as `First Account`, logout, query event feed filtered by `infrahub.account.logged_in` and `infrahub.account.logged_out` — both appear with correct `account_id`, `auth_method`, `session_id`, and matching `session_id` between the two events.

### Implementation — US1 (Password auth + user logout)

- [ ] T013 [US1] Emit `AccountLoggedInEvent` on successful password login in `backend/infrahub/api/auth.py`
- [ ] T014 [US1] Emit `AccountLoggedOutEvent` with `logout_type="user_initiated"` in `backend/infrahub/api/auth.py`
- [ ] T015 [P] [US1] Emit `AccountLoggedInEvent` on successful OAuth2 SSO callback in `backend/infrahub/api/oauth2.py`
- [ ] T016 [P] [US1] Emit `AccountLoggedInEvent` on successful OIDC SSO callback in `backend/infrahub/api/oidc.py`

### Implementation — US1 (Admin-forced logout, FR-008)

- [ ] T017 [US1] Add `POST /api/auth/sessions/{session_id}/invalidate` endpoint (or GraphQL mutation `InfrahubAccountSessionInvalidate`) that calls `invalidate_refresh_token()` and emits `AccountLoggedOutEvent` with `logout_type="admin_forced"` — requires admin role check — implement in `backend/infrahub/api/auth.py` or `backend/infrahub/graphql/mutations/account.py`
- [ ] T018 [US1] Write component test for admin-forced logout event emission in `backend/tests/component/api/test_auth_events.py`

### Tests — US1

- [ ] T019 [P] [US1] Unit tests for `AccountLoggedInEvent.get_resource()` and `get_payload()` in `backend/tests/unit/event/test_auth_action.py`
- [ ] T020 [P] [US1] Unit tests for `AccountLoggedOutEvent.get_resource()` and `get_payload()` in `backend/tests/unit/event/test_auth_action.py`
- [ ] T021 [US1] Component test: successful password login emits `AccountLoggedInEvent` in `backend/tests/component/api/test_auth_events.py`
- [ ] T022 [US1] Component test: user-initiated logout emits `AccountLoggedOutEvent` in `backend/tests/component/api/test_auth_events.py`
- [ ] T023 [P] [US1] Add `timestamp` field assertion to existing unit tests for both event classes in `backend/tests/unit/event/test_auth_action.py`

**Checkpoint**: US1 fully functional — password login, user logout, and admin-forced logout all emit queryable events (admin-only via GraphQL).

---

## Phase 4: Polish & Cross-Cutting Concerns

- [ ] T024 [P] Run `uv run ruff format` on all modified Python files
- [ ] T025 [P] Run `uv run ruff check --fix` on all modified Python files
- [ ] T026 Run `uv run pytest backend/tests/unit/event/test_auth_action.py backend/tests/component/api/test_auth_events.py -v` and confirm all pass
- [ ] T027 Update `dev/specs/infp-474-login-logout-events/plan.md` to reflect admin-forced logout gap as completed once T017 is done

---

## Dependencies

```text
Phase 1 (T001–T008) → Phase 2 (T009–T012)
                     ↓
              Phase 3 (T013–T023)    ← can start after T004–T007
              Phase 4 (T024–T027)    ← final pass
```

---

## Parallel Execution

**Right now (all independent):**
- T011 — add `timestamp` to GraphQL types
- T012 — admin role check on account event queries
- T023 — add timestamp assertions to unit tests

**Independently:**
- T017 — admin-forced logout endpoint/mutation
- T018 — admin-forced logout component test

---

## Implementation Strategy

**MVP (US1 core)**: T001–T016, T019–T023 — login/logout audit trail complete for password + SSO, admin-only access enforced.

**Final increment**: T017 → T018 — admin-forced logout (requires design decision on endpoint vs mutation).

**Design decision needed for T017**: REST (`DELETE /api/auth/sessions/{session_id}`) is simpler and consistent with the existing `/api/auth/logout` pattern. GraphQL mutation is more consistent with other account management mutations. Recommend REST unless the caller (admin UI) already uses GraphQL for account operations.

---

## Summary

| Phase | Story | Tasks | Done | Remaining |
|-------|-------|-------|------|-----------|
| 1 — Setup | — | 8 | 1 | 7 |
| 2 — GraphQL | — | 4 | 0 | 4 |
| 3 — US1 Audit Trail | P1 | 11 | 0 | 11 |
| 4 — Polish | — | 4 | 0 | 4 |
| **Total** | | **27** | **1** | **26** |
