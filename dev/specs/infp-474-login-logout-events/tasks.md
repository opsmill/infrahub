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

- [x] T001 [P] Create `backend/infrahub/events/auth_action.py` with `AccountLoggedInEvent`, `AccountLoggedOutEvent` (including `timestamp` field on both)
- [x] T002 [P] Export the two new event classes in `backend/infrahub/events/__init__.py`
- [x] T003 Add `AuthResult` frozen dataclass to `backend/infrahub/auth.py`
- [x] T004 Add `_fetch_account_groups_and_roles()` helper to `backend/infrahub/auth.py`
- [x] T005 Refactor `authenticate_with_password()` in `backend/infrahub/auth.py` to return `AuthResult`
- [x] T006 Refactor `signin_sso_account()` in `backend/infrahub/auth.py` to return `AuthResult`
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

### Tests — US1

- [ ] T016 [P] [US1] Unit tests for `AccountLoggedInEvent.get_resource()` and `get_payload()` in `backend/tests/unit/event/test_auth_action.py`
- [ ] T017 [P] [US1] Unit tests for `AccountLoggedOutEvent.get_resource()` and `get_payload()` in `backend/tests/unit/event/test_auth_action.py`
- [ ] T018 [US1] Component test: successful password login emits `AccountLoggedInEvent` in `backend/tests/component/api/test_auth_events.py`
- [ ] T019 [US1] Component test: user-initiated logout emits `AccountLoggedOutEvent` in `backend/tests/component/api/test_auth_events.py`
- [ ] T020 [P] [US1] Add `timestamp` field assertion to existing unit tests for both event classes in `backend/tests/unit/event/test_auth_action.py`

**Checkpoint**: US1 fully functional — password login and user logout emit queryable events (admin-only via GraphQL).

---

## Phase 4: Polish & Cross-Cutting Concerns

- [ ] T021 [P] Run `uv run ruff format` on all modified Python files
- [ ] T022 [P] Run `uv run ruff check --fix` on all modified Python files
- [ ] T023 Run `uv run pytest backend/tests/unit/event/test_auth_action.py backend/tests/component/api/test_auth_events.py -v` and confirm all pass

---

## Dependencies

```text
Phase 1 (T001–T007) → Phase 2 (T008–T011)
                     ↓
              Phase 3 (T012–T020)    ← can start after T003–T006
              Phase 4 (T021–T023)    ← final pass
```

---

## Parallel Execution

**Right now (all independent):**
- T010 — add `timestamp` to GraphQL types
- T011 — admin role check on account event queries
- T020 — add timestamp assertions to unit tests

---

## Implementation Strategy

**MVP (US1 core)**: T001–T015, T016–T020 — login/logout audit trail complete for password + SSO, admin-only access enforced.

---

## Summary

| Phase | Story | Tasks | Done | Remaining |
|-------|-------|-------|------|-----------|
| 1 — Setup | — | 7 | 1 | 6 |
| 2 — GraphQL | — | 4 | 0 | 4 |
| 3 — US1 Audit Trail | P1 | 9 | 0 | 9 |
| 4 — Polish | — | 3 | 0 | 3 |
| **Total** | | **23** | **1** | **22** |
