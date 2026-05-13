---

description: "Task list — INFP-556 Auto-create Account Groups from External Authentication Sources"
---

# Tasks: Auto-create Account Groups from External Authentication Sources

**Input**: Design documents from `/specs/infp-556-auto-create-groups/`
**Prerequisites**: spec.md, plan.md, research.md, data-model.md, contracts/{config-settings.md, events.md, schema-delta.md}, quickstart.md
**Jira/JPD**: [INFP-556](https://opsmill.atlassian.net/browse/INFP-556)
**Tests**: Tests are in scope. Constitution principle IV (Test Discipline) in plan.md mandates unit + functional + integration_docker coverage.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label (US1–US5) — only on tasks inside a story phase

## Path Conventions

Backend-only feature in a monorepo. All paths absolute from repo root.

- Backend code: `backend/infrahub/`
- Backend tests: `backend/tests/{unit,functional,integration_docker}/`
- Docs: `docs/topics/security/`
- Changelog: `changelog/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Skeleton for the new domain package and its test directories.

- [ ] T001 [P] Create new package `backend/infrahub/auth_groups/` with empty `__init__.py`
- [ ] T002 [P] Create test directories `backend/tests/unit/auth_groups/`, `backend/tests/functional/auth_groups/`, `backend/tests/integration_docker/auth_groups/`, each with an empty `__init__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema delta, schema migration, Pydantic config, and shared enums that every user story depends on. ⚠️ No user story work can begin until this phase is complete.

- [ ] T003 Add `origin` Dropdown attribute to `CoreAccountGroup` in `backend/infrahub/core/schema/definitions/core/permission.py:159` with the **7** enum literals from `contracts/schema-delta.md` (FR-012). Attribute MUST be marked `optional=True` (nullable) AND **UI-hidden** by default. Do NOT include `manual` or `system` literals (clarification 2026-05-13). [Sync: Gap Report]
- [ ] T004 Regenerate schema artifacts with `uv run invoke backend.generate`; verify `backend/infrahub/core/schema/generated/` and `backend/infrahub/core/protocols.py` are updated (depends on T003)
- [ ] T005 [P] Add `AccountGroupOrigin` StrEnum in `backend/infrahub/auth_groups/origin.py` mirroring the **7** schema literals (`oidc_provider1`, `oidc_provider2`, `oidc_google`, `oauth2_provider1`, `oauth2_provider2`, `oauth2_google`, `ldap`). Do NOT include `manual` or `system` — those creation paths leave `origin` unset (clarification 2026-05-13). [Sync: Gap Report]
- [ ] T006 [P] Add `auto_create_groups_filter: str | list[str] | None` field plus `_compile_filter_patterns` `@field_validator` to `SecuritySettings` in `backend/infrahub/config.py:743+`, storing compiled patterns on a private attribute and raising `ValueError` with setting name + position on bad regex (FR-001 to FR-004, contracts/config-settings.md)
- [ ] T007 [P] Add `auto_create_groups_max_per_login: int = 50` field to `SecuritySettings` in `backend/infrahub/config.py:743+` with `>= 1` validation (FR-020 config, contracts/config-settings.md)
- [ ] ~~T008~~ **REMOVED** (clarification 2026-05-13): No data-migration backfill is needed — `origin` is optional and pre-existing rows are valid with an unset value (FR-014). The previously-planned `m073_set_account_group_origin.py` MUST NOT be added; if any earlier branch added a stub, delete it. [Sync: Gap Report]
- [ ] ~~T009~~ **REMOVED** (clarification 2026-05-13): No migration to register. [Sync: Gap Report]

**Checkpoint**: Schema attribute exists, migration ready, config surface in place. User story implementation can now begin.

---

## Phase 3: User Story 1 - Auto-create groups from a filter pattern with name capture (Priority: P1) 🎯 MVP

**Goal**: First time a user logs in with an external claim matching the configured filter, a `CoreAccountGroup` with the captured name is atomically created (zero roles/permissions, `origin` set to the auth-flow value), the user is added as a member, and concurrent first-logins for the same brand-new claim produce exactly one group.

**Independent Test**: With filter `^LDAP/group/(?P<name>.+)$`, simulate a login carrying `LDAP/group/network-engineering`. Verify the group is created with the captured name, the user is a member, `origin` matches the auth flow (e.g. `oidc_provider1` or `ldap`), and a second user's login reuses the same group rather than duplicating it.

### Tests for User Story 1 ⚠️ Write FIRST, ensure they FAIL before implementation

- [ ] T010 [P] [US1] Unit test `FilterPattern` matching + named-capture extraction + no-capture fallback (FR-005 to FR-008) in `backend/tests/unit/auth_groups/test_filter.py`
- [ ] T011 [P] [US1] Unit test provider-slot → origin mapping for all 7 sources (OIDC×3, OAuth2×3, LDAP) in `backend/tests/unit/auth_groups/test_mapper.py` (R1, FR-013)
- [ ] T012 [P] [US1] Functional test happy-path auto-creation in `backend/tests/functional/auth_groups/test_autocreate_flow.py` covering US1 acceptance scenarios 1, 2, 3, and 5 (capture, dedup-on-reuse, no-capture full-claim, CoreGroup-name collision fallback) plus FR-018 dedup-within-login
- [ ] T013 [P] [US1] Integration_docker test for concurrent first-logins in `backend/tests/integration_docker/auth_groups/test_concurrent_first_logins.py` issuing N simultaneous logins for the same brand-new claim and asserting exactly one group is created and every login succeeds (FR-011, SC-008)

### Implementation for User Story 1

- [ ] T014 [P] [US1] Implement `FilterPattern` dataclass + `evaluate(claim) -> effective_name | None` (first-match-per-claim, in declared order) in `backend/infrahub/auth_groups/filter.py` (FR-005 to FR-008)
- [ ] T015 [P] [US1] Implement provider-slot → origin mapping function `origin_for_auth_flow(protocol, slot)` in `backend/infrahub/auth_groups/mapper.py` returning the matching `AccountGroupOrigin` literal (R1, FR-013, depends on T005)
- [ ] T016 [US1] Implement `autocreate_groups_for_login(db, account, protocol, slot, claims, settings)` in `backend/infrahub/auth_groups/service.py` using the 3-layer find-or-create pattern from research.md R3 (fast-path lookup → distributed lock `lock.registry.get(name=..., namespace="auto-create-group")` with under-lock re-check → `Node.init(...).save()` catching `UniqueConstraintViolation`), setting `origin` from T015, deduping effective names within the login, skipping claims whose effective name fails `CoreAccountGroup` identifier validation, and falling back to `sso_user_default_group` only when zero matches (FR-005 to FR-011, FR-016 partial, FR-017 skip behavior, FR-018) — depends on T014, T015
- [ ] T017 [US1] Hook `autocreate_groups_for_login` into `signin_sso_account` in `backend/infrahub/auth.py:310` so every OIDC and OAuth2 login routes external group claims through the service before the existing membership-add path (FR-005 entry) — depends on T016

**Checkpoint**: An admin can configure a filter, log a user in, and observe the matching claim produce a new local group with the user as a member; concurrent first-logins produce exactly one group.

---

## Phase 4: User Story 2 - Skip claims that fall outside the filter (Priority: P1)

**Goal**: Non-matching claims must be silently dropped so that an IdP emitting hundreds of unrelated group claims does not pollute Infrahub. Per-login soft cap (FR-020) provides the secondary safeguard against misconfiguration.

**Independent Test**: With filter `^LDAP/group/(?P<name>.+)$`, simulate a login carrying `LDAP/group/network-engineering`, `slack/general`, `github/contributors`. Verify only `network-engineering` is auto-created; `slack/general` and `github/contributors` produce no groups. Separately: configure a low cap, simulate more matching claims than the cap, verify the cap is honored and login completes.

### Tests for User Story 2 ⚠️ Write FIRST, ensure they FAIL before implementation

- [ ] T018 [P] [US2] Functional test filter scoping with mixed matching + non-matching claims in `backend/tests/functional/auth_groups/test_filter_scoping.py` covering US2 acceptance scenarios 1 and 2
- [ ] T019 [P] [US2] Functional test per-login cap behavior in `backend/tests/functional/auth_groups/test_per_login_cap.py`: a login carrying more matching claims than `auto_create_groups_max_per_login` creates exactly `cap` groups, completes successfully, and drops the surplus (FR-020 behavior — event emission tested in US5)

### Implementation for User Story 2

- [ ] T020 [US2] Add per-login new-creation counter to `autocreate_groups_for_login` in `backend/infrahub/auth_groups/service.py`: increment only on a successful new-group creation (membership additions to existing groups are uncounted), stop creating once `counter == settings.auto_create_groups_max_per_login`, accumulate dropped claims for later event emission, and let the login complete (FR-020 behavior — depends on T016)

**Checkpoint**: User Stories 1 AND 2 both pass independently — filter scoping verified, runaway-creation safeguard in place.

---

## Phase 5: User Story 3 - Honor the IFC-922 default group when no filter pattern matches (Priority: P2)

**Goal**: When a user's external claims produce zero matches under the filter, the existing `sso_user_default_group` (IFC-922) behavior must be preserved. When at least one claim matches, the default group must NOT be stacked on top — matching takes precedence.

**Independent Test**: Configure auto-creation + `sso_user_default_group`. Simulate a login with no matching claims; verify the user joins the default group. Simulate a login with one matching claim + several non-matching claims; verify the user joins the matched auto-created group and is NOT added to the default group.

### Tests for User Story 3 ⚠️ Write FIRST, ensure they FAIL before implementation

- [ ] T021 [P] [US3] Functional test default-group fallback when no claims match in `backend/tests/functional/auth_groups/test_default_group_fallback.py` (US3 acceptance scenario 1, FR-016)
- [ ] T022 [P] [US3] Functional test default group is NOT stacked when at least one claim matches in `backend/tests/functional/auth_groups/test_default_group_precedence.py` (US3 acceptance scenario 2, FR-016)

### Implementation for User Story 3

- [ ] T023 [US3] Coordinate auto-creation hook with the existing `sso_user_default_group` codepath in `backend/infrahub/auth.py:signin_sso_account`: invoke the default-group fallback only when `autocreate_groups_for_login` returned zero memberships and only when the setting is configured; ensure no double-add when matches occurred (FR-016 — depends on T017)

**Checkpoint**: User Stories 1, 2, and 3 all pass independently.

---

## Phase 6: User Story 4 - Distinguish auto-created groups from manually-created ones (Priority: P2)

**Goal**: `origin` is set correctly across every CoreAccountGroup creation path (`oidc_*` / `oauth2_*` / `ldap` for auto-creation, `manual` for admin-facing routes, `system` for platform bootstrap), pre-existing rows are backfilled to `manual` by the migration, and `origin` is read-only from all external write paths.

**Independent Test**: Trigger auto-creation via an OIDC login and verify the resulting group's `origin = oidc_providerN`. Create a group manually via the API and verify `origin = manual`. Inspect a platform-seeded bootstrap group and verify `origin = system`. After running the schema migration on a fixture with pre-existing groups, verify every row has `origin = manual` with zero nulls. Attempt to set/change `origin` via UI form, GraphQL mutation, REST PATCH, and schema-load; verify all four are rejected or silently ignored, and the original value is preserved.

### Tests for User Story 4 ⚠️ Write FIRST, ensure they FAIL before implementation

- [ ] T024 [P] [US4] Integration_docker test for upgrade-path invariant in `backend/tests/integration_docker/auth_groups/test_origin_unset_on_upgrade.py`: seed pre-feature `CoreAccountGroup` rows, run the 1.10 schema definition update (no data-migration script), assert every pre-existing row has `origin` unset (null/absent) and that the schema accepts that state (FR-014 reshaped, clarification 2026-05-13). Replaces the previously-planned `test_schema_migration_backfill.py`. [Sync: Gap Report]
- [ ] T025 [P] [US4] Functional test that admin-facing creation paths (UI/GraphQL/REST/schema-load) leave `origin` **unset** in `backend/tests/functional/auth_groups/test_origin_unset_on_admin_paths.py` — create a group via each surface, assert `origin` is null/absent on every read-back (FR-013, clarification 2026-05-13). Replaces the previously-planned `test_origin_manual.py`. [Sync: Gap Report]
- [ ] T026 [P] [US4] Functional test that platform-seeded bootstrap groups have `origin` **unset** in `backend/tests/functional/auth_groups/test_origin_unset_on_bootstrap.py` — inspect every group created by `create_default_account_groups` and assert `origin` is null/absent (FR-013, clarification 2026-05-13). Replaces the previously-planned `test_origin_system.py`. [Sync: Gap Report]
- [ ] T027 [P] [US4] Functional test `origin` read-only enforcement in `backend/tests/functional/auth_groups/test_origin_readonly.py`: GraphQL create-with-origin, GraphQL update-origin, REST PATCH origin, schema-load with origin — all rejected or silently ignored. Verify enforcement for BOTH (a) a group whose `origin` is currently set (auto-created — value preserved) and (b) a group whose `origin` is currently unset (admin-created — must remain unset, no value accepted) (FR-021, US4 acceptance scenario 5). [Sync: Gap Report]
- [ ] T046 [P] [US4] Functional test that `origin` is hidden from the schema-driven UI in `backend/tests/functional/auth_groups/test_origin_ui_hidden.py` — assert the schema metadata exposed to the UI marks `origin` as hidden (no field/column rendered by default) on `CoreAccountGroup` views (FR-012 UI-hidden, US4 acceptance scenario 6, clarification 2026-05-13). [Sync: Gap Report]

### Implementation for User Story 4

- [ ] ~~T028~~ **REMOVED** (clarification 2026-05-13): Platform bootstrap MUST NOT set `origin`. Do NOT edit `backend/infrahub/core/initialization.py::create_accounts_group`. If any earlier branch added the `origin=system` write, revert it (FR-013). [Sync: Gap Report]
- [ ] ~~T029~~ **REMOVED** (clarification 2026-05-13): Admin-facing creation paths (GraphQL/REST/schema-load) MUST NOT write any value to `origin`. The optional schema attribute leaves the value unset by default, which is the documented state. Revert any default-to-`manual` logic on those paths (FR-013). [Sync: Gap Report]
- [ ] T030 [P] [US4] Enforce `origin` read-only at the schema input-validation layer: reject user-supplied `origin` values on create/update with a clear validation error or silently ignore them (FR-021, R5). Updated scope: this also covers the "cannot set initial value via admin paths" requirement now that no admin path sets `origin` (FR-013, clarification 2026-05-13). [Sync: Gap Report]
- [ ] T031 [US4] Enforce `origin` read-only at the Cypher/Node write layer: server-determined `origin` value always wins (auto-creation path only); user-supplied values never reach the write path; admin/bootstrap paths never set `origin__value` (FR-021 defense-in-depth, FR-013, R5 — depends on T030)

**Checkpoint**: User Stories 1, 2, 3, AND 4 all pass independently. `origin` is correctly set everywhere and immune to external tampering.

---

## Phase 7: User Story 5 - Auditable record of every auto-creation event (Priority: P2)

**Goal**: Every auto-creation success, every rejected-claim skip, and every per-login cap breach emits a structured event into the activity log carrying the login context and the relevant payload. No event is emitted when a login reuses an already-existing auto-created group.

**Independent Test**: Trigger auto-creation; query the event log filtered to `GroupAutoCreatedEvent` and verify a single event with `group_name`, `source_pattern`, `idp`, `triggering_user_*`, `origin_value`. Log a second user into the same external group; verify no second `GroupAutoCreatedEvent` is emitted. Trigger an auto-creation with a captured name that fails identifier validation; verify a `GroupAutoCreateRejectedClaimEvent` with the verbatim length-truncated claim. Trigger a login that breaches the cap; verify a single `GroupAutoCreateCapBreachEvent` carrying `cap_value`, `dropped_count`, and the verbatim length-truncated dropped claims.

### Tests for User Story 5 ⚠️ Write FIRST, ensure they FAIL before implementation

- [ ] T032 [P] [US5] Functional test `GroupAutoCreatedEvent` emission in `backend/tests/functional/auth_groups/test_event_created.py`: one event per actual create, no event on reuse of existing auto-created group (US5 acceptance scenarios 1 and 2, FR-015)
- [ ] T033 [P] [US5] Functional test `GroupAutoCreateRejectedClaimEvent` emission in `backend/tests/functional/auth_groups/test_event_rejected.py` when an effective name fails `CoreAccountGroup` identifier validation (FR-017)
- [ ] T034 [P] [US5] Functional test `GroupAutoCreateCapBreachEvent` emission in `backend/tests/functional/auth_groups/test_event_cap_breach.py`: exactly one event per cap-breaching login, payload carries verbatim length-truncated dropped claims (FR-020 event, 2026-05-11 verbatim clarification)

### Implementation for User Story 5

- [ ] T035 [US5] Add `GroupAutoCreateEvent` concrete intermediate + `GroupAutoCreatedEvent`, `GroupAutoCreateRejectedClaimEvent`, `GroupAutoCreateCapBreachEvent` leaves to `backend/infrahub/events/group_action.py` modeled on the existing `GroupMutatedEvent` + `GroupMemberAddedEvent` / `GroupMemberRemovedEvent` shape, each with its own `event_name` ClassVar under the `EVENT_NAMESPACE.group.auto_create.*` prefix (contracts/events.md)
- [ ] T036 [US5] Emit `GroupAutoCreatedEvent` exactly once per successful new-group create from `autocreate_groups_for_login` in `backend/infrahub/auth_groups/service.py` — NOT on existing-group reuse, NOT on constraint-violation re-fetch (FR-015, R3 critical post-write invariant — depends on T016, T035)
- [ ] T037 [US5] Emit `GroupAutoCreateRejectedClaimEvent` when a matched claim's effective name fails identifier validation in `backend/infrahub/auth_groups/service.py`; claim value stored verbatim with length truncation only (FR-017, 2026-05-11 verbatim clarification — depends on T016, T035)
- [ ] T038 [US5] Emit a single `GroupAutoCreateCapBreachEvent` when the per-login cap is reached in `backend/infrahub/auth_groups/service.py`; dropped claims stored verbatim per-entry, length-truncated; login completes (FR-020 event, 2026-05-11 verbatim clarification — depends on T020, T035)

**Checkpoint**: All five user stories pass independently. Audit trail is queryable; compliance review can reconstruct every auto-creation.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, changelog, formatting, and full quickstart validation.

- [ ] T039 [P] Update `docs/topics/security/sso.mdx` per FR-019: working example with `^LDAP/group/(?P<name>.+)$`, explicit safety note about filter scoping, interaction with IFC-922 default group, credit to community PR #8515 author (wording to be coordinated with Yvonne at release time)
- [ ] T040 [P] Add towncrier fragment `changelog/+INFP-556-auto-create-account-groups.added.md` summarizing the user-facing change
- [ ] T041 Run `uv run invoke format` and `uv run invoke lint` to ensure no style/typing regressions
- [ ] T042 Walk through every step of `specs/infp-556-auto-create-groups/quickstart.md` against a running local instance; capture deltas (if any) back into the doc

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup. **Blocks all user stories.** T004 (regenerate schema) blocks anything importing `CoreAccountGroup` with the new attribute. T009 (register migration) depends on T008.
- **US1 (Phase 3)**: Depends on Foundational (needs schema, config, and `AccountGroupOrigin`).
- **US2 (Phase 4)**: Depends on US1 T016 (extends `autocreate_groups_for_login` with the cap counter).
- **US3 (Phase 5)**: Depends on US1 T017 (wires the auto-creation hook ahead of the default-group fallback).
- **US4 (Phase 6)**: Depends on Foundational (`origin` attribute must exist). Does NOT depend on US1's service; runs in parallel with US1/US2/US3.
- **US5 (Phase 7)**: Depends on US1 T016 (success-event emission point) and US2 T020 (cap-event emission point).
- **Polish (Phase 8)**: Depends on the user stories the team chose to ship.

### Within Each User Story

- Tests are written first and must FAIL before implementation tasks are merged.
- `FilterPattern` and `mapper` are pure-logic and parallel; `service.py` depends on both.
- The hook into `auth.py:signin_sso_account` (T017) depends on the service being importable.
- Event classes (T035) must exist before service code emits them (T036–T038).

### Parallel Opportunities

- T001, T002 in Phase 1 are fully parallel.
- T003, T005, T006, T007, T008 in Phase 2 touch different files and are parallel; T004 serializes after T003; T009 serializes after T008.
- All US1 tests (T010, T011, T012, T013) are parallel.
- T014 and T015 in US1 are parallel (different files); T016 serializes after both; T017 serializes after T016.
- US4 has the highest parallelism: T024, T025, T026, T027 (tests) and T028, T029, T030 (impls) all parallel; T031 serializes after T030.
- US5 tests T032, T033, T034 are parallel; T035 must precede T036–T038, which are sequential because they all edit `service.py`.
- Polish T039, T040 are parallel; T041 and T042 are sequential at the end.

---

## Parallel Example: User Story 1

```bash
# All tests for US1 in parallel (different files, all FAIL initially):
Task: "Unit test FilterPattern in backend/tests/unit/auth_groups/test_filter.py"
Task: "Unit test mapper in backend/tests/unit/auth_groups/test_mapper.py"
Task: "Functional test autocreate flow in backend/tests/functional/auth_groups/test_autocreate_flow.py"
Task: "Integration_docker test concurrent first-logins in backend/tests/integration_docker/auth_groups/test_concurrent_first_logins.py"

# Then the pure-logic implementations in parallel:
Task: "Implement FilterPattern in backend/infrahub/auth_groups/filter.py"
Task: "Implement origin mapper in backend/infrahub/auth_groups/mapper.py"

# Then sequentially:
Task: "Implement autocreate_groups_for_login in backend/infrahub/auth_groups/service.py"
Task: "Hook service into signin_sso_account in backend/infrahub/auth.py"
```

---

## Implementation Strategy

### MVP (User Story 1 only)

1. Complete Phase 1 (Setup).
2. Complete Phase 2 (Foundational) — schema attribute + migration + config + enum.
3. Complete Phase 3 (US1) — filter + mapper + service + hook + tests.
4. STOP and VALIDATE against US1 Independent Test.

The MVP delivers the core value proposition: admins can enable the filter and onboard a team by first-login. US2's filter-scoping behavior is already exercised by US1's tests (only matching claims drive creation); the explicit US2 scoping tests and the cap are the next safety increment.

### Incremental Delivery

1. Setup + Foundational → groundwork ready.
2. US1 → MVP, demo to enterprise design partners.
3. US2 → safe under real-world IdP noise; cap added.
4. US3 → IFC-922 contract preserved; existing default-group customers protected.
5. US4 → audit-grade provenance on every group; read-only `origin` enforced.
6. US5 → compliance-grade audit trail; every auto-creation event logged.
7. Polish.

### Sequencing Risk: INFP-105

Per research.md R9, INFP-105 (native LDAP) lands in 1.10 alongside this feature. `autocreate_groups_for_login` exposes the `protocol=LDAP` branch from day one so the API is stable; INFP-105 supplies the LDAP call site. The schema enum already carries `ldap`, so no follow-up schema migration is needed when INFP-105 lands.

---

## Notes

- Generated files (`backend/infrahub/core/schema/generated/`, `backend/infrahub/core/protocols.py`, `schema/schema.graphql`, `schema/openapi.json`, `frontend/app/src/shared/api/graphql/generated/`, `frontend/app/src/shared/api/rest/types.generated.ts`) are produced by T004 + a running instance for GraphQL/OpenAPI export. Do not hand-edit.
- The constitution check in plan.md commits to no mocked databases in integration tests; T013, T024 must hit the real Neo4j via TestContainers.
- Layer 1 of the three-layer find-or-create (R3) is a benchmarked optimization — T016 implements all three layers initially; if functional benchmarks show layer-2-only meets SC-004, layer 1 should be dropped before merge.
- Per-event-class leaves (T035) follow the existing `GroupMutatedEvent` → `GroupMemberAddedEvent` / `GroupMemberRemovedEvent` precedent — do NOT collapse to a single class with a discriminator field.
