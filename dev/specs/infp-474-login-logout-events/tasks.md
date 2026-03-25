# Tasks: Login/Logout Activity Events

**Input**: Design documents from `/specs/infp-474-login-logout-events/`
**Branch**: `infp-474-login-logout-events`
**Generated**: 2026-03-24

> **Scope**: Only US1 (Authentication Audit Trail) is in scope. `infrahub.account.*` events are admin-only (FR-005).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Paths relative to repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Core infrastructure required before any story work.

- [ ] T001 [P] Create `backend/infrahub/events/auth_action.py` with `AccountLoggedInEvent`, `AccountLoggedOutEvent` (including `timestamp` field on both)
- [ ] T002 [P] Export the two new event classes in `backend/infrahub/events/__init__.py`
- [ ] T003 Add `AuthResult` frozen dataclass to `backend/infrahub/auth.py`
- [ ] T004 Add `_fetch_account_groups_and_roles()` helper to `backend/infrahub/auth.py`
- [ ] T005 Refactor `authenticate_with_password()` in `backend/infrahub/auth.py` to return `AuthResult`
- [ ] T006 Refactor `signin_sso_account()` in `backend/infrahub/auth.py` to return `AuthResult`
- [x] T007 [P] Add changelog fragment `changelog/+infp-474.added.md`

**Checkpoint**: Foundation ready — event classes exist, auth functions return rich metadata.

---

## Phase 2: Foundational (GraphQL Surface)

**Purpose**: Register event types in GraphQL so all stories are queryable via the existing interface.

- [ ] T008 Add `AccountLoggedInEventType`, `AccountLoggedOutEventType` ObjectTypes to `backend/infrahub/graphql/types/event.py`
- [ ] T009 Register both types in `EVENT_TYPES` dict in `backend/infrahub/graphql/types/event.py`
- [ ] T010 Add `timestamp = DateTime(required=True)` field to `AccountLoggedInEventType` and `AccountLoggedOutEventType` in `backend/infrahub/graphql/types/event.py`
- [ ] T011 [P] Add admin role check to `infrahub.account.*` event queries in `backend/infrahub/graphql/types/event.py` — non-admin requests must receive an authorization error

**Checkpoint**: Both auth event types are queryable via GraphQL (with full field coverage including timestamp) by admin users only.

---

## Phase 3: User Story 1 — Authentication Audit Trail (Priority: P1) 🎯 MVP

**Goal**: Successful login and user-initiated logout emit queryable events with full account context.

**Independent Test**: Login as `First Account`, logout, query event feed filtered by `infrahub.account.logged_in` and `infrahub.account.logged_out` — both appear with correct `account_id`, `auth_method`, `session_id`, and matching `session_id` between the two events.

### Implementation — US1 (Password auth + user logout)

- [ ] T012 [US1] Emit `AccountLoggedInEvent` on successful password login in `backend/infrahub/api/auth.py`
- [ ] T013 [US1] Emit `AccountLoggedOutEvent` with `logout_type="user_initiated"` in `backend/infrahub/api/auth.py`
- [ ] T014 [P] [US1] Emit `AccountLoggedInEvent` on successful OAuth2 SSO callback in `backend/infrahub/api/oauth2.py`
- [ ] T015 [P] [US1] Emit `AccountLoggedInEvent` on successful OIDC SSO callback in `backend/infrahub/api/oidc.py`

### Implementation — US1 (Admin-forced logout, FR-008)

- [ ] T016 [US1] Write component test for admin-forced logout event emission in `backend/tests/component/api/test_auth_events.py`

### Tests — US1

- [ ] T017 [P] [US1] Unit tests for `AccountLoggedInEvent.get_resource()` and `get_payload()` in `backend/tests/unit/event/test_auth_action.py`
- [ ] T018 [P] [US1] Unit tests for `AccountLoggedOutEvent.get_resource()` and `get_payload()` in `backend/tests/unit/event/test_auth_action.py`
- [ ] T019 [US1] Component test: successful password login emits `AccountLoggedInEvent` in `backend/tests/component/api/test_auth_events.py`
- [ ] T020 [US1] Component test: user-initiated logout emits `AccountLoggedOutEvent` in `backend/tests/component/api/test_auth_events.py`
- [ ] T021 [P] [US1] Add `timestamp` field assertion to existing unit tests for both event classes in `backend/tests/unit/event/test_auth_action.py`

**Checkpoint**: US1 fully functional — password login, user logout, and admin-forced logout all emit queryable events (admin-only via GraphQL).

---

## Phase 4: Polish & Cross-Cutting Concerns

- [ ] T022 [P] Run `uv run ruff format` on all modified Python files
- [ ] T023 [P] Run `uv run ruff check --fix` on all modified Python files
- [ ] T024 Run `uv run pytest backend/tests/unit/event/test_auth_action.py backend/tests/component/api/test_auth_events.py -v` and confirm all pass
- [ ] T025 Update `dev/specs/infp-474-login-logout-events/plan.md` to reflect admin-forced logout gap as completed once T016 is done

---

## Dependencies

```text
Phase 1 (T001–T007) → Phase 2 (T008–T011)
                     ↓
              Phase 3 (T012–T021)    ← can start after T003–T006
              Phase 4 (T022–T025)    ← final pass
```

---

## Parallel Execution

**Right now (all independent):**
- T010 — add `timestamp` to GraphQL types
- T011 — admin role check on account event queries
- T021 — add timestamp assertions to unit tests

---

## Implementation Strategy

**MVP (US1 core)**: T001–T015, T017–T021 — login/logout audit trail complete for password + SSO, admin-only access enforced.

**Design decision needed for T016**: REST (`DELETE /api/auth/sessions/{session_id}`) is simpler and consistent with the existing `/api/auth/logout` pattern. GraphQL mutation is more consistent with other account management mutations. Recommend REST unless the caller (admin UI) already uses GraphQL for account operations.

---

## Summary

| Phase | Story | Tasks | Done | Remaining |
|-------|-------|-------|------|-----------|
| 1 — Setup | — | 7 | 1 | 6 |
| 2 — GraphQL | — | 4 | 0 | 4 |
| 3 — US1 Audit Trail | P1 | 10 | 0 | 10 |
| 4 — Polish | — | 4 | 0 | 4 |
| **Total** | | **25** | **1** | **24** |
