# Implementation Plan: Auto-create Account Groups from External Authentication Sources

**Branch**: `pmi-20260511-speckit-plan-and-other-documents` (working branch; spec dir pinned via `.specify/feature.json`) | **Date**: 2026-05-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/infp-556-auto-create-groups/spec.md`
**Jira/JPD**: [INFP-556](https://opsmill.atlassian.net/browse/INFP-556)

## Summary

Add opt-in, filter-scoped auto-creation of `CoreAccountGroup` rows when a user logs in via SSO/OIDC, OAuth2, or native LDAP (INFP-105) and their external group claims match an admin-configured regex filter. Hardens community PR #8515 with the product shaping captured in `spec.md`. Adds an **optional, free-form `Text`** `origin` attribute to `CoreAccountGroup`, declared with the schema property **`display: extra`** so the schema-driven UI hides it from the default group view but lets a user reveal it via the extra/advanced-attributes toggle. The value, when set, is the configured name of the identity provider that triggered auto-creation (e.g. the configured OIDC/OAuth2/LDAP provider name from settings — not a fixed enum literal). The attribute is unset (null) on every group not created by the auto-creation path (manually-created, platform-seeded, pre-upgrade existing rows). Ships in 1.10 alongside native LDAP.

Technical approach: a single hook in the existing SSO account-sign-in path (`backend/infrahub/auth.py::signin_sso_account`) evaluates external claims against the configured regex filter(s), derives effective local names (named capture group or raw claim), and find-or-creates `CoreAccountGroup` rows under the existing distributed lock pattern (`lock.registry.get`) for FR-011 concurrency safety. The same hook runs from the new native-LDAP route (delivered by INFP-105). The configured provider name passes through from the auth-flow context into the new row's `origin` text value — no enum mapping. Two new `INFRAHUB_SECURITY_*` settings (filter + per-login cap), one new schema attribute (`Text`, optional, read-only, `display: extra`), no data backfill migration (pre-existing rows valid with unset `origin`), and one new structured event type. No bespoke frontend work — the schema-driven UI already honors `display: extra` to keep `origin` out of the default group view while letting a user toggle extra/advanced attributes on to read it. Long-term direction: replace this Text attribute with object-level metadata referencing a `CoreNode`-derived identity-provider object once that platform machinery exists (out of scope for 1.10 — see spec.md Out of Scope).

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.9 (frontend — not touched)
**Primary Dependencies**: FastAPI 0.131.0, Pydantic 2.12, neo4j 6.0.3 driver, existing `InfrahubEventService` + `lock.registry` + `Node`/schema runtime
**Storage**: Neo4j 2025.10.1 (CalVer; community image per `docker-compose.yml`). `CoreAccountGroup` nodes (`Branch.AGNOSTIC`); attribute uniqueness on `name__value` already enforced.
**Testing**: pytest 9.0 (unit + functional + integration_docker); concurrency test under TestContainers; schema migration test against fixture pre-feature data
**Target Platform**: Linux container (production), local dev (uv + Docker)
**Project Type**: Backend-only feature in a backend+frontend monorepo (backend principal area, no frontend work)
**Performance Goals**: First-encounter login that triggers auto-creation: no user-perceived hang (SC-004). Subsequent reusing logins: no measurable additional latency vs. baseline (SC-004). Per-login soft cap default `50` (FR-020) bounds worst-case work per login.
**Constraints**: Auto-creation MUST be safe under concurrent first-logins (FR-011). Invalid regex MUST fail at startup (FR-004). `origin` MUST be read-only from every external write path (FR-021). `origin` MUST be a `Text` attribute, optional (nullable), and declared with `display: extra` at the schema level (FR-012, clarification 2026-05-13 — supersedes the earlier "fully UI-hidden + Dropdown enum" shape); value when set is the configured provider name (free-form string). No data backfill is required on upgrade (FR-014) — pre-existing rows are valid with unset `origin`.
**Scale/Scope**: Designed for enterprise customers with 100+ externally-managed groups. The filter is the primary mitigation against runaway creation; the per-login cap is the secondary safeguard.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | ✅ | `origin` is a regular `Text` attribute on `CoreAccountGroup` (FR-012), marked optional, read-only, and declared with `display: extra`. No data backfill migration is required on upgrade (FR-014, clarification 2026-05-13) — pre-existing rows are valid with an unset `origin`. Validation against the active schema is unchanged. Generated files (`backend/infrahub/core/schema/generated/`) regenerated, not hand-edited. |
| II. Branch-Safe by Default | ✅ (N/A for entity) | `CoreAccountGroup` is `Branch.AGNOSTIC`; auto-creation happens during login (no branch context). No new branch-specific behavior introduced. |
| III. Type Safety & Explicit Contracts | ✅ | New `INFRAHUB_SECURITY_*` fields on the existing Pydantic `SecuritySettings`; internal data structures (compiled regex + named-capture map) use frozen dataclasses; new event payload follows existing `InfrahubEvent` typed model. `origin` is a typed optional `Text` attribute at the schema level (no Python-side `AccountGroupOrigin` enum is needed; the value is the configured provider name string). |
| IV. Test Discipline | ✅ | Unit tests for regex compilation/matching and named-capture extraction. Functional tests for the full sign-in flow with mock IdP claim sets, asserting `origin` carries the configured provider name string from the auth-flow context (no enum mapping to assert). Integration_docker test for concurrent first-logins (FR-011) and for upgrade-path verification that pre-existing rows have an unset `origin` (FR-014, replacing the previous backfill-correctness test). Functional test that `origin` remains unset on admin-facing and bootstrap creation paths. Functional test that the schema metadata for `origin` declares `display: extra` (FR-012). No mocking of the database. |
| V. Query Performance & Efficiency | ✅ | Find-or-create via parameterized Cypher `MERGE` (or query-then-create under the existing distributed lock); no N+1; cap (FR-020) bounds new-creation work per login; membership additions reuse existing batched paths. |
| VI. Security & Input Boundaries | ✅ | Regex patterns validated at startup (FR-004). Captured names re-validated against `CoreAccountGroup` name rules before insert (FR-017). `origin` system-managed; external write attempts rejected/ignored (FR-021). No new injection surface — all Cypher parameterized. Claim values in audit events stored verbatim length-truncated only (per 2026-05-11 clarification), no feature-specific RBAC. |
| VII. Simplicity & Maintainability | ✅ | Single integration point (`signin_sso_account`), reuses `lock.registry`, `InfrahubEventService.send`, and the schema-driven API surface (UI rendering of `origin` is governed by the existing `display: extra` schema property — no bespoke UI work, no backfill migration script, no Python enum, no provider-slot→literal mapper). Two new env vars, one new schema attribute (`Text`), one new event class. No new abstractions, no new dependencies. The "enabled-but-unfiltered" misconfiguration class was deliberately eliminated in clarification (filter presence = activation). |

**Result**: No constitution violations. Complexity Tracking table left empty.

### Frontend principles

Not applicable. `origin` is declared with `display: extra` at the schema level (clarification 2026-05-13), so the schema-driven UI hides it from the default `CoreAccountGroup` group view but still lets a user opt in via the existing extra/advanced-attributes toggle. No bespoke UI components are in scope; the existing renderer handles this through the schema metadata it already consumes.

### Shared Components Inventory

Not applicable (no frontend changes).

## Project Structure

### Documentation (this feature)

```text
specs/infp-556-auto-create-groups/
├── spec.md                 # Feature spec (with 3 clarification sessions)
├── plan.md                 # This file
├── research.md             # Phase 0 output
├── data-model.md           # Phase 1 output
├── quickstart.md           # Phase 1 output
├── contracts/              # Phase 1 output (config + event + schema deltas)
│   ├── config-settings.md
│   ├── events.md
│   └── schema-delta.md
└── checklists/             # (existing dir)
```

### Source Code (repository root)

```text
backend/
├── infrahub/
│   ├── auth.py                                           # MODIFIED in PR #9257 — `signin_sso_account` split into focused helpers (no behavior change). The auto-create hook lives in the extracted `_assign_group_memberships` helper (line ~366), NOT inline in `signin_sso_account`.
│   ├── api/oauth2.py                                     # MODIFIED in PR #9257 — small cleanup (-3 lines) coordinating with the auth.py helper split.
│   ├── api/oidc.py                                       # MODIFIED in PR #9257 — small cleanup (-3 lines) coordinating with the auth.py helper split.
│   ├── config.py                                         # MODIFIED — two new SecuritySettings fields + regex validator (line ~770)
│   ├── core/
│   │   └── schema/definitions/core/permission.py         # MODIFIED — add `origin` attribute (Text, optional, read_only=True, display="extra") to CoreAccountGroup (line ~159)
│   │   # NOTE: No `migrations/graph/mNNN_set_account_group_origin.py` is needed (FR-014, clarification 2026-05-13).
│   │   #       The attribute is optional; pre-existing rows are valid with unset `origin`.
│   │   # NOTE: `core/initialization.py` is NOT modified — platform bootstrap MUST NOT set `origin` (FR-013).
│   ├── auth_groups/                                      # NEW package — auto-creation domain (single small module)
│   │   ├── __init__.py
│   │   ├── filter.py                                     # `ClaimFilter` class — wraps compiled `re.Pattern` tuple; `name_for(claim)`, `names_for(claims)`, `is_active`
│   │   └── service.py                                    # `AutoCreatedGroups` class — constructed `AutoCreatedGroups(db, account, provider_name)`; `assign(claims, claim_filter) -> tuple[str, ...]`; pulls configured provider name from auth-flow context and writes it verbatim to origin (no enum mapping)
│   │   # NOTE: shipped surface is a class, NOT the free function `autocreate_groups_for_login(...)` originally
│   │   #       described in tasks.md. The `settings` parameter was eliminated — the call site builds a
│   │   #       `ClaimFilter` from `config.SETTINGS.security.auto_create_groups_filter_patterns` and passes
│   │   #       it in directly. Class name is `ClaimFilter` (not `FilterPattern` / `FilterEvaluator`).
│   │   # NOTE: `auth_groups/mapper.py` and `auth_groups/origin.py` are NOT created — the previous enum-mapping design
│   │   #       was superseded by clarification 2026-05-13 (Text attribute holding the configured provider name).
│   └── events/
│       └── group_action.py                               # PENDING (US5 follow-up) — add GroupAutoCreateEvent (intermediate) + 3 leaf classes: GroupAutoCreatedEvent, GroupAutoCreateRejectedClaimEvent, GroupAutoCreateCapBreachEvent (structural template: GroupMutatedEvent + GroupMemberAddedEvent/GroupMemberRemovedEvent)
└── tests/
    ├── unit/auth_groups/
    │   └── test_filter.py                                # SHIPPED in PR #9257
    │   # NOTE: test_mapper.py is NOT created — no enum mapping exists in the Text-attribute design.
    └── component/auth_groups/                            # SHIPPED in PR #9257 — single directory for all non-unit auth_groups tests
        ├── conftest.py                                   # SHIPPED — fixtures (28 lines)
        ├── test_autocreate_flow.py                       # SHIPPED — ~430 lines, covers US1 happy-path + US2 scoping (`test_non_matching_claims_produce_no_groups_when_filter_is_on`) + US3 default-group fallback (`TestDefaultGroupFallback` class — see tasks.md T021/T022/T023)
        ├── test_concurrent_first_logins.py               # PENDING (T013/T048 follow-up — FR-011)
        └── test_origin_unset_on_upgrade.py               # PENDING (US4 follow-up — FR-014 reshaped)

# NOTE: tasks.md originally placed component tests under `backend/tests/functional/auth_groups/` and
#       `backend/tests/integration_docker/auth_groups/`. The shipped layout is a single `component/auth_groups/`
#       directory (reconciled 2026-05-15).

docs/topics/security/sso.mdx                              # PENDING (US3 polish — IFC-2593) — FR-019 docs
docs/docs/reference/configuration.mdx                     # MODIFIED in PR #9257 — auto-generated 2-line bump for the new SecuritySettings fields
docker-compose.yml                                        # MODIFIED in PR #9257 — 2-line addition for the new SecuritySettings fields

changelog/+INFP-556-auto-create-account-groups.added.md  # PENDING (IFC-2593) — towncrier fragment
```

**Structure Decision**: Backend-only feature. A new tiny package `backend/infrahub/auth_groups/` houses the three pure-logic units (filter, mapper, service) so they are unit-testable without the FastAPI/Neo4j stack. The actual hook lives in `auth.py::signin_sso_account` and calls into `auth_groups.service`. Schema, config, migration, and event additions slot into existing locations and follow established templates (no new patterns introduced).

## Complexity Tracking

> No Constitution Check violations to justify.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _(none)_  |            |                                     |

### Revision: Implementation Sync 2026-05-12

- Reason: Technical Context cited stale dependency versions (FastAPI 0.121.1, Pydantic 2.10, Neo4j 5.28). Reconciled against `pyproject.toml` / `uv.lock` (FastAPI 0.131.0, Pydantic 2.12.x, neo4j driver 6.0.3) and `docker-compose.yml` (Neo4j server `2025.10.1-community`).

### Revision: Implementation Sync 2026-05-13

- Reason: `origin` reshaped per Clarification Session 2026-05-13 — attribute becomes optional and UI-hidden; only the auto-creation path writes a value (admin-facing and bootstrap paths leave it unset). Removed the planned `mNNN_set_account_group_origin.py` migration (no backfill needed). Removed the planned edit to `core/initialization.py::create_accounts_group` (bootstrap MUST NOT set `origin`). Replaced `test_schema_migration_backfill.py` with `test_origin_unset_on_upgrade.py`. Updated Constitution Check rows I, III, IV, VII and the Frontend principles note to reflect the new UI-hidden constraint and the absence of a data-migration script. The Summary and Constraints lines were updated to remove the "backfill `manual`" commitment.

### Revision: Implementation Sync 2026-05-14

- Reason: Re-aligned to spec.md after rebase onto `pmi-ifc-2521-auto-create-groups`. The Session 2026-05-13 clarification now lands a substantially different shape than what the previous reconcile produced: `origin` is a `Text` attribute (NOT a Dropdown enum), value is the **configured provider name** (free-form string, NOT one of seven enum literals), and UI visibility is governed by the existing **`display: extra`** schema property (hidden from default view, revealable via the extra/advanced-attributes toggle — NOT fully UI-hidden). Updated Summary, Constraints, Constitution rows I/III/IV/VII, Frontend principles, and Project Structure (removed `auth_groups/mapper.py`, `auth_groups/origin.py`, `tests/unit/auth_groups/test_mapper.py`). Spec.md, contracts/schema-delta.md, contracts/events.md, data-model.md, quickstart.md, tasks.md updated in the same pass. Long-term direction (metadata-framework + identity-provider `CoreNode`) recorded in spec.md Out of Scope; plan does not implement it.

### Revision: Implementation Sync 2026-05-15

- Reason: PR #9257 ("User groups auto-creation MVP IFC-2586 IFC-2587 IFC-2588 IFC-2590") merged and the shipped code drifted from this plan's Project Structure in three load-bearing ways: (1) **Test layout** — what the plan placed under `backend/tests/functional/auth_groups/` and `backend/tests/integration_docker/auth_groups/` was consolidated into a single `backend/tests/component/auth_groups/` directory, with a single `test_autocreate_flow.py` (~430 lines + `conftest.py`) absorbing US1 happy-path + US2 scoping + US3 default-group fallback scenarios. The concurrent-first-logins test (FR-011) was NOT included — tracked as T048 in tasks.md. (2) **Service surface** — `backend/infrahub/auth_groups/service.py` ships as the class `AutoCreatedGroups(db, account, provider_name).assign(claims, claim_filter)`, not the free function `autocreate_groups_for_login(db, account, provider_name, claims, settings)` named in the original plan; the `settings` parameter was eliminated (the call site builds a `ClaimFilter` directly). (3) **Filter class** — `backend/infrahub/auth_groups/filter.py` ships as `ClaimFilter` (not `FilterPattern` / `FilterEvaluator`) with methods `name_for(claim) -> str | None` and `names_for(claims) -> tuple[str, ...]` (not `evaluate` / `evaluate_many`). Additionally: `auth.py::signin_sso_account` was split into focused helpers in the same PR (no behavior change) and the auto-create hook now lives in the extracted `_assign_group_memberships` helper; `api/oauth2.py` and `api/oidc.py` had small (-3 line) cleanups; `docker-compose.yml` and `docs/docs/reference/configuration.mdx` each got an auto-generated 2-line bump for the new `SecuritySettings` fields. Project Structure section updated; tasks.md status flips, class/method renames, and path rewrites tracked in the parallel tasks.md Sync entry. Spec.md is unchanged — user-facing behavior matches what shipped for US1 and US3, plus the US2 scoping subset.
