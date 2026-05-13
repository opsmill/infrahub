# Implementation Plan: Auto-create Account Groups from External Authentication Sources

**Branch**: `pmi-20260511-speckit-plan-and-other-documents` (working branch; spec dir pinned via `.specify/feature.json`) | **Date**: 2026-05-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/infp-556-auto-create-groups/spec.md`
**Jira/JPD**: [INFP-556](https://opsmill.atlassian.net/browse/INFP-556)

## Summary

Add opt-in, filter-scoped auto-creation of `CoreAccountGroup` rows when a user logs in via SSO/OIDC, OAuth2, or native LDAP (INFP-105) and their external group claims match an admin-configured regex filter. Hardens community PR #8515 with the product shaping captured in `spec.md`. Adds an **optional, UI-hidden** `origin` enum attribute to `CoreAccountGroup` to record the auth path that auto-created the group; the attribute is unset on every group not created by the auto-creation path (manually-created, platform-seeded, pre-upgrade existing rows). Ships in 1.10 alongside native LDAP.

Technical approach: a single hook in the existing SSO account-sign-in path (`backend/infrahub/auth.py::signin_sso_account`) evaluates external claims against the configured regex filter(s), derives effective local names (named capture group or raw claim), and find-or-creates `CoreAccountGroup` rows under the existing distributed lock pattern (`lock.registry.get`) for FR-011 concurrency safety. The same hook runs from the new native-LDAP route (delivered by INFP-105). Two new `INFRAHUB_SECURITY_*` settings (filter + per-login cap), one new schema attribute (optional + UI-hidden), no data backfill migration (pre-existing rows valid with unset `origin`), and one new structured event type. No frontend work — `origin` is excluded from the schema-driven UI by the schema-level hidden flag.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.9 (frontend — not touched)
**Primary Dependencies**: FastAPI 0.131.0, Pydantic 2.12, neo4j 6.0.3 driver, existing `InfrahubEventService` + `lock.registry` + `Node`/schema runtime
**Storage**: Neo4j 2025.10.1 (CalVer; community image per `docker-compose.yml`). `CoreAccountGroup` nodes (`Branch.AGNOSTIC`); attribute uniqueness on `name__value` already enforced.
**Testing**: pytest 9.0 (unit + functional + integration_docker); concurrency test under TestContainers; schema migration test against fixture pre-feature data
**Target Platform**: Linux container (production), local dev (uv + Docker)
**Project Type**: Backend-only feature in a backend+frontend monorepo (backend principal area, no frontend work)
**Performance Goals**: First-encounter login that triggers auto-creation: no user-perceived hang (SC-004). Subsequent reusing logins: no measurable additional latency vs. baseline (SC-004). Per-login soft cap default `50` (FR-020) bounds worst-case work per login.
**Constraints**: Auto-creation MUST be safe under concurrent first-logins (FR-011). Invalid regex MUST fail at startup (FR-004). `origin` MUST be read-only from every external write path (FR-021). `origin` MUST be optional and UI-hidden at the schema level (FR-012, clarification 2026-05-13); no data backfill is required on upgrade (FR-014) — pre-existing rows are valid with unset `origin`.
**Scale/Scope**: Designed for enterprise customers with 100+ externally-managed groups. The filter is the primary mitigation against runaway creation; the per-login cap is the secondary safeguard.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | ✅ | `origin` is a regular enum attribute on `CoreAccountGroup` (FR-012), marked optional and UI-hidden. No data backfill migration is required on upgrade (FR-014, clarification 2026-05-13) — pre-existing rows are valid with an unset `origin`. Validation against the active schema is unchanged. Generated files (`backend/infrahub/core/schema/generated/`) regenerated, not hand-edited. |
| II. Branch-Safe by Default | ✅ (N/A for entity) | `CoreAccountGroup` is `Branch.AGNOSTIC`; auto-creation happens during login (no branch context). No new branch-specific behavior introduced. |
| III. Type Safety & Explicit Contracts | ✅ | New `INFRAHUB_SECURITY_*` fields on the existing Pydantic `SecuritySettings`; internal data structures (compiled regex + named-capture map) use frozen dataclasses; new event payload follows existing `InfrahubEvent` typed model. `origin` is a typed optional enum at the schema level. |
| IV. Test Discipline | ✅ | Unit tests for regex compilation/matching, named-capture extraction, and provider→`origin` mapping. Functional tests for the full sign-in flow with mock IdP claim sets. Integration_docker test for concurrent first-logins (FR-011) and for upgrade-path verification that pre-existing rows have an unset `origin` (FR-014, replacing the previous backfill-correctness test). Functional test that `origin` remains unset on admin-facing and bootstrap creation paths. No mocking of the database. |
| V. Query Performance & Efficiency | ✅ | Find-or-create via parameterized Cypher `MERGE` (or query-then-create under the existing distributed lock); no N+1; cap (FR-020) bounds new-creation work per login; membership additions reuse existing batched paths. |
| VI. Security & Input Boundaries | ✅ | Regex patterns validated at startup (FR-004). Captured names re-validated against `CoreAccountGroup` name rules before insert (FR-017). `origin` system-managed; external write attempts rejected/ignored (FR-021). No new injection surface — all Cypher parameterized. Claim values in audit events stored verbatim length-truncated only (per 2026-05-11 clarification), no feature-specific RBAC. |
| VII. Simplicity & Maintainability | ✅ | Single integration point (`signin_sso_account`), reuses `lock.registry`, `InfrahubEventService.send`, and the schema-driven API surface (UI rendering of `origin` is suppressed by the schema-level hidden flag — no bespoke UI work, no backfill migration script either). Two new env vars, one new schema attribute, one new event class. No new abstractions, no new dependencies. The "enabled-but-unfiltered" misconfiguration class was deliberately eliminated in clarification (filter presence = activation). |

**Result**: No constitution violations. Complexity Tracking table left empty.

### Frontend principles

Not applicable. `origin` is marked UI-hidden at the schema level (clarification 2026-05-13), so the schema-driven UI excludes it from default `CoreAccountGroup` views — admins observe provenance through the API and the auto-creation event log. No bespoke UI components are in scope.

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
│   ├── auth.py                                           # MODIFIED — hook into signin_sso_account (line ~310)
│   ├── config.py                                         # MODIFIED — two new SecuritySettings fields + regex validator (line ~743)
│   ├── core/
│   │   └── schema/definitions/core/permission.py         # MODIFIED — add `origin` attribute (optional, UI-hidden) to CoreAccountGroup (line ~159)
│   │   # NOTE: No `migrations/graph/mNNN_set_account_group_origin.py` is needed (FR-014, clarification 2026-05-13).
│   │   #       The attribute is optional; pre-existing rows are valid with unset `origin`.
│   │   # NOTE: `core/initialization.py` is NOT modified — platform bootstrap MUST NOT set `origin` (FR-013).
│   ├── auth_groups/                                      # NEW package — auto-creation domain (single small module)
│   │   ├── __init__.py
│   │   ├── filter.py                                     # Compiled-filter dataclass + name extraction
│   │   ├── mapper.py                                     # Provider slot → origin enum literal (Oauth2Provider/OIDCProvider → "oidc_provider1"/etc.)
│   │   └── service.py                                    # autocreate_groups_for_login(...) — the hook implementation
│   └── events/
│       └── group_action.py                               # MODIFIED — add GroupAutoCreateEvent (intermediate) + 3 leaf classes: GroupAutoCreatedEvent, GroupAutoCreateRejectedClaimEvent, GroupAutoCreateCapBreachEvent (structural template: GroupMutatedEvent + GroupMemberAddedEvent/GroupMemberRemovedEvent)
└── tests/
    ├── unit/auth_groups/
    │   ├── test_filter.py                                # NEW
    │   └── test_mapper.py                                # NEW
    ├── functional/auth_groups/
    │   └── test_autocreate_flow.py                       # NEW
    └── integration_docker/auth_groups/
        ├── test_concurrent_first_logins.py               # NEW (FR-011)
        └── test_origin_unset_on_upgrade.py               # NEW (FR-014 reshaped — asserts pre-existing rows have unset origin post-upgrade)

docs/topics/security/sso.mdx                              # MODIFIED — FR-019 docs

changelog/+INFP-556-auto-create-account-groups.added.md  # NEW (towncrier)
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
