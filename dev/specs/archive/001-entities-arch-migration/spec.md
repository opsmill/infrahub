# Feature Specification: Entities Clean-Architecture Migration

**Feature Branch**: `frontend-entities-arch-migration`
**Created**: 2026-07-02
**Status**: Extracted
**Input**: Reconcile and migrate the frontend `entities/` folder toward a feature-first, DDD-inspired structure (`api/`, `ui/`, `domain/{model,rules,use-cases}`), reconciling with — not superseding — the existing documented architecture in `dev/knowledge/frontend/entities-structure.md`.

## Overview

The frontend `src/entities/` folder holds ~24 entity modules plus a large `nodes/` namespace. Most entities already follow a documented three-layer architecture (`ui → domain → api`) described in `dev/knowledge/frontend/entities-structure.md`, but the internal shape of `domain/` is flat and inconsistent, transport concerns (generated GraphQL/REST types, mappers) leak into `domain/`, and no automated guard prevents boundary regressions.

This feature migrates every entity toward a sharper, DDD-inspired layout — `domain/` split into `model/`, `rules/`, and `use-cases/` where size warrants — while **reconciling with, not replacing,** the existing documented architecture. The migration is staged one entity per pull request, guarded by an incrementally-scoped lint rule, and leaves the `domain/` layer free of generated transport types.

## Clarifications

### Session 2026-07-02 (grilling)

- The original proposal's dependency arrows were inverted; the codebase direction `ui → domain → api` is kept (domain calls its own entity's `api/`).
- `ui/` retains nested subfolders (`ui/queries/`, `ui/hooks/`, per-component folders); `api/` stays flat.
- Mappers ("Option A"): mapping logic lives in `api/`; `api/` fetchers return **domain** types; a single new type-only edge `api → domain/model` is permitted. `domain/` becomes free of generated GraphQL/REST types.
- `domain/model` is a pure leaf — it imports nothing from `api/`, `rules/`, `use-cases/`, or `ui/`.
- `domain/` is split only when it has more than 4 files; no folder is created to hold fewer than 2 files.
- Enforcement ships in two tiers: Tier 1 (Biome `noRestrictedImports`, no new dependency) with the migration; Tier 2 (dependency-cruiser, directional folder rules) deferred pending new-dependency sign-off.
- Rollout is staged, all entities in scope, `nodes/` migrated last as its own multi-PR sub-epic.
- The `store`/`branchesState` (browser-state-in-domain) class of leak is fixed later, not as a blocker of the initial migration.
- No Jira/JPD ticket; the mandatory feature-branch gate was explicitly overridden by the requester for this planning branch.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Validate the reconciled pattern on a trivial entity (Priority: P1)

As a frontend engineer, I migrate the smallest self-contained entity (`role-manager`, 2 files) to the reconciled structure so the folder mechanics and the Tier-1 lint guard are proven end-to-end with negligible blast radius before any large module is touched.

**Why this priority**: Nothing else can safely proceed until the pattern and its automated guard are demonstrated to work and to pass CI. This is the smallest slice that delivers a validated, repeatable template.

**Independent Test**: Migrate `role-manager` alone; confirm `pnpm tsc && pnpm build && pnpm test && pnpm biome` are all green and the Tier-1 lint override for `role-manager/domain` passes. Delivers a working reference and a live guard.

**Acceptance Scenarios**:

1. **Given** `role-manager/domain` with `get-decision-options.ts` (a pure function) and its test, **When** the entity is migrated, **Then** the pure function lands in `domain/rules/` (or the domain stays flat if under the split threshold) and no `domain/` file imports React, TanStack, Apollo, browser storage, toast libraries, or generated types.
2. **Given** the migrated entity, **When** CI runs, **Then** `pnpm tsc`, `pnpm build`, `pnpm test`, and `pnpm biome` all pass and the Biome `noRestrictedImports` override now lists this entity's `domain/` glob.
3. **Given** the migration PR, **When** a reviewer reads the diff, **Then** it touches only this one entity plus the incremental lint-config line.

---

### User Story 2 - Establish the canonical reference entity (Priority: P1)

As a frontend engineer, I migrate `branches` — the architecture doc's reference example — to exercise every non-trivial rule (the >4-file domain split, the Option-A mapper move, and a real generated-type leak fix), then update `entities-structure.md` from the result so it becomes the copyable template for the fan-out.

**Why this priority**: `branches` is the only pilot that exercises all the hard cases at once (type/mapper split, generated-type quarantine, domain split). Until it is clean and documented, the ~20 fan-out entities have no authoritative example to follow.

**Independent Test**: Migrate `branches` alone; confirm `branch.mappers.ts` is split (domain types → `domain/model/`, mapping functions → `api/`), that `branches/domain/**` no longer imports generated types, and that all four verification commands pass. Update the knowledge doc.

**Acceptance Scenarios**:

1. **Given** `branch.mappers.ts` currently exports both domain types (`BranchListItem`, `BranchDetail`) and mapping functions and imports generated types, **When** migrated, **Then** the domain types live in `domain/model/`, the mapping functions live in `api/` and return those domain types, and `domain/` imports no generated type.
2. **Given** `branches/domain` has 11 files, **When** migrated, **Then** it is split into `model/`, `rules/`, and/or `use-cases/` with each created folder holding at least 2 files, and orchestration/pure/type files are classified per the heuristic.
3. **Given** the migration is complete, **When** `dev/knowledge/frontend/entities-structure.md` is read, **Then** it documents the reconciled structure using `branches` as the worked example.

---

### User Story 3 - Fan out across the remaining entities (Priority: P2)

As a frontend engineer, I migrate each remaining entity (all ~20, no exclusions) one PR at a time, copying the `branches` pattern, so the whole `entities/` folder (excluding `nodes/`) converges on the reconciled structure with the guard growing per PR.

**Why this priority**: This is the bulk of the value but depends entirely on the P1 template being locked. Each entity is an independent, shippable slice.

**Independent Test**: For any single entity, migrate it and confirm all four verification commands pass and the Tier-1 glob now covers its `domain/`.

**Acceptance Scenarios**:

1. **Given** any not-yet-migrated entity, **When** it is migrated, **Then** its layout matches the reconciled rules and the four verification commands pass before the next entity is started.
2. **Given** an entity whose `domain/` has 4 or fewer files (e.g. `config`), **When** migrated, **Then** its `domain/` stays flat (no `model/`/`rules/`/`use-cases/` split).
3. **Given** each fan-out PR, **When** merged, **Then** the Biome override's list of guarded `domain/` globs has grown by exactly that entity and still passes.

---

### User Story 4 - Migrate the `nodes/` namespace last (Priority: P3)

As a frontend engineer, I migrate the `nodes/` namespace (~260 files across ~12 sub-modules) as its own multi-PR sub-epic after every other entity is done, without disturbing the in-flight sort work already living inside `nodes/object`.

**Why this priority**: `nodes/` is the largest, most entangled area and is not a single entity; it must follow the proven pattern and must not collide with active feature work. Lowest priority, highest risk — done last.

**Independent Test**: Each `nodes/` sub-module migrates as its own PR passing all four verification commands, with the in-flight sort files left functional.

**Acceptance Scenarios**:

1. **Given** every non-`nodes/` entity is migrated, **When** the `nodes/` sub-epic begins, **Then** each `nodes/` sub-module is migrated in its own PR following the canonical pattern.
2. **Given** in-flight sort work exists in `nodes/object`, **When** `nodes/object` is migrated, **Then** the sort functionality remains intact and its tests still pass.

### Edge Cases

- **Entity has no `api/`** (e.g. `config`, `role-manager`, `role-manager` has domain+ui only): migrate the layers that exist; do not create an empty `api/`.
- **Domain type and its mapper share one file** (`branch.mappers.ts`): the file is split — types to `domain/model/`, mapping to `api/`.
- **Enabling the guard breaks unmigrated entities**: the Tier-1 Biome override is scoped incrementally (per-entity glob) so it only ever covers already-clean domains and never fails an unmigrated one.
- **Browser-state read inside `domain/`** (`get-branches.ts` reads `store`/`branchesState`): flagged by the guard but explicitly deferred; resolved later by lifting the read to `ui/`. Where the guard would fail an otherwise-migrated entity on this specific class, the deferral is recorded rather than blocking the PR.
- **A mapper would force `api → domain/use-cases`**: not allowed; only `api → domain/model` (types) is permitted. If a mapper needs more than a model type, the shape moves to `domain/model`.
- **`domain/model` accidentally imports from `api/`**: creates a dependency cycle; must be caught (Tier 1 covers library/type leaks; the directional model-leaf rule is Tier 2 / manual review until then).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Each migrated entity MUST place external data-access code (GraphQL/REST fetchers, clients, and mapping functions) directly in a flat `api/` folder (no nested subfolders).
- **FR-002**: `api/` fetchers MUST return domain types (not raw generated shapes); mapping from generated shapes to domain types MUST occur within `api/`.
- **FR-003**: `domain/` MUST NOT import generated GraphQL or REST types, React, TanStack Query, Apollo Client, browser storage, or notification/toast libraries.
- **FR-004**: `api/` MAY import `domain/model` for type-only purposes; it MUST NOT import `domain/rules`, `domain/use-cases`, or `ui/`.
- **FR-005**: `domain/model` MUST be a pure leaf — importing nothing from `api/`, `domain/rules`, `domain/use-cases`, or `ui/`.
- **FR-006**: A `domain/` folder MUST be split into `model/`, `rules/`, and/or `use-cases/` only when it contains more than 4 files; below that it stays flat.
- **FR-007**: No `model/`, `rules/`, or `use-cases/` subfolder may be created to hold fewer than 2 files.
- **FR-008**: When splitting, files MUST be classified as: orchestration / I-O → `use-cases/`; pure, no I-O → `rules/`; type declarations → `model/`.
- **FR-009**: `ui/` MUST retain its nested subfolders (`ui/queries/`, `ui/hooks/`, per-component folders); the existing `ui → domain → api` direction (domain calls its own `api/`) MUST be preserved.
- **FR-010**: A Tier-1 Biome `noRestrictedImports` guard MUST forbid the imports in FR-003 for migrated entities' `domain/` and MUST be scoped incrementally (one `domain/` glob added per migrated entity) so it never fails an unmigrated entity.
- **FR-011**: Each entity migration MUST be delivered as its own pull request that passes `pnpm tsc`, `pnpm build`, `pnpm test`, and `pnpm biome` before the next entity is started.
- **FR-012**: The migration MUST proceed in order: `role-manager` → `branches` (then update `dev/knowledge/frontend/entities-structure.md`) → remaining ~20 entities → `nodes/` last.
- **FR-013**: `nodes/` MUST be migrated as a separate multi-PR sub-epic and MUST NOT disrupt in-flight sort work in `nodes/object`.
- **FR-014**: The migration MUST NOT add new runtime or dev dependencies; dependency-cruiser (Tier 2) is deferred and requires separate sign-off.
- **FR-015**: The migration MUST preserve public behavior and existing tests; business logic MUST NOT be rewritten except where required to satisfy a boundary rule.
- **FR-016**: The browser-state-in-`domain/` class of leak (e.g. `get-branches.ts` reading `store`/`branchesState`) is out of scope for the initial per-entity migration and MUST be recorded for a later follow-up (lifting the read to `ui/`).

### Key Entities

- **Entity module**: a folder under `src/entities/` (e.g. `branches`, `role-manager`) containing some subset of `api/`, `domain/`, `ui/`.
- **`domain/model`**: domain vocabulary — types, value objects, IDs, filters, sorts, inputs, result types. Pure leaf.
- **`domain/rules`**: pure business/domain functions with no I-O.
- **`domain/use-cases`**: orchestration functions for the entity that call `api/`.
- **`api/`**: transport — fetchers, clients, generated-type imports, and generated↔domain mappers returning domain types.
- **`ui/`**: React components, hooks, `ui/queries/` (TanStack), UI state and view models.
- **Tier-1 guard**: a Biome `noRestrictedImports` override, incrementally scoped per migrated entity.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of migrated entities have a `domain/` folder that imports zero generated GraphQL/REST types (target at migration completion: all ~24 entities + `nodes/` sub-modules).
- **SC-002**: The count of `domain/` files importing generated types drops from 8 (today) to 0 by completion, decreasing monotonically per PR.
- **SC-003**: Every migration PR is green on all four verification commands (`tsc`, `build`, `test`, `biome`) before merge — 0 exceptions.
- **SC-004**: The Tier-1 Biome guard covers 100% of migrated entities' `domain/` folders and produces 0 false failures on unmigrated entities throughout the rollout.
- **SC-005**: No new dependency is added during the migration (dependency count unchanged).
- **SC-006**: Each migration PR touches exactly one entity (plus the single incremental lint-config line), keeping every diff independently reviewable and revertible.
- **SC-007**: In-flight sort functionality in `nodes/object` remains fully working (its tests pass) throughout and after the `nodes/` sub-epic.

## Assumptions

- The existing documented architecture (`dev/knowledge/frontend/entities-structure.md`) is authoritative and this migration extends it; conflicts were resolved in favor of the codebase's actual direction.
- Biome (v2.4) `overrides` + `noRestrictedImports` can express the Tier-1 forbidden-import rules per glob without a new dependency.
- Directional folder rules (model-as-leaf, `api → domain/model` only) are enforced by review until Tier 2 (dependency-cruiser) is separately approved.
- The planning branch was created without a Jira/JPD ticket by explicit requester override; a ticket may be attached before implementation PRs are opened.
- The in-flight sort work in `nodes/object` will be committed/merged on its own feature branch independently of this migration.
- "All entities" means every module under `src/entities/`; `nodes/` is treated as a namespace of multiple sub-modules migrated individually.
