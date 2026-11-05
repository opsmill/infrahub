# Implementation Plan: Instance label and color as global settings

**Branch**: `ple-instance-badge-ifc-3232` | **Date**: 2026-11-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/007-instance-badge-ifc-3232/spec.md`, a design jam of four prototyped header directions (prototype removed before the PR, not kept in the repository), and three planning framings (minimal change, clean boundaries, test-first) merged on 2026-11-05.

## Summary

An administrator who holds `manage_global_preferences` sets an instance label (text, at most 32 characters after trimming) and an instance color (one of seven presets) on the Global preferences page. Both values are two new nullable fields on the existing global `Preference` row (`owner_id = "__global__"`), written through the existing `InfrahubSetPreferences(scope: GLOBAL)` mutation and read by the administrator through `InfrahubGlobalPreferences`. The public `/api/config` response gains an `instance` block read from that row, so every visitor, including the login page, renders a tinted badge at the right of the app header next to the status indicators, a 3 px colored bar above the sidebar and header, and a tab title of the form `<label> · <page title>`.

## Technical Context

**Language/Version**: Python 3.14 (backend), TypeScript 6.0 / React 19.3 (frontend)

**Primary Dependencies**: FastAPI, graphene, Pydantic 2 (backend); Vite 8, Tailwind CSS 4, `@infrahub/ui`, TanStack Query, react-hook-form (frontend)

**Storage**: Neo4j; the global `Preference` StandardNode (no schema node, no graph migration, no seeded row)

**Testing**: pytest (unit and component tiers), Vitest browser mode, pytest-playwright E2E in `tests/e2e/`

**Target Platform**: Infrahub web UI on desktop browsers; REST and GraphQL API

**Project Type**: Web application (backend + frontend)

**Performance Goals**: `/api/config` performs one read-only `get_for_owner` per call; no polling is added, the other open tabs refetch `["config"]` on window focus

**Constraints**: No inline styles or arbitrary Tailwind values (theme tokens only); no `cast`, `any` or `type: ignore`; generated files regenerated, never edited; the E2E test is the last task and the feature is not complete until it passes

**Scale/Scope**: 12 tasks; about 10 backend files, about 20 frontend files, 1 E2E file, 2 docs files

## Decisions

| Question | Decision | Why |
|---|---|---|
| Mutation arguments | Two flat arguments `instance_label: String`, `instance_color: InstanceColor` with the existing `_UNSET` sentinel | Follows the `date_format` / `timezone` pattern; an input object pays off only for fields that are out of scope |
| Keeping the fields off per-user preferences | `GlobalPreferencesType(RawPreferencesType)` subclass used only by `InfrahubGlobalPreferences`; the mutation raises `ValidationError` when `scope != GLOBAL` and either argument is provided, before any read | FR-008; the only way to make the fields unselectable on the user and effective queries |
| Color wire format | `InstanceColor(InfrahubStringEnum)` with name == value, uppercase (`RED = "RED"`, …) | graphene puts member names on the GraphQL wire and Pydantic serialises values on REST; equality keeps `schema.graphql`, `openapi.json` and both generated TypeScript types consistent. Docs write the names in lowercase |
| Public read path | `ConfigAPI.instance: InstanceIdentityAPI` read from `PreferenceRepository(db).get_for_owner(GLOBAL_OWNER_ID)`; missing row → both `None` | Every client loads `/api/config` before first render, including the login page (FR-009, FR-010) |
| Tab title | The single `useTitle` hook composes `formatDocumentTitle(useConfig().instance.label, title)`; `app-layout.tsx` and `login.tsx` call `useTitle("Infrahub")` | Every route then has a titled ancestor, so the unmount restore always lands on a composed title (US2-4) |
| Frontend location | `entities/preferences/` for the badge, bar, color rules and form; the one cross-entity import is `useConfig` | The setting is a global preference and the form lives there |
| Color choice input | Existing `Combobox`, with an additive optional `icon` on `ComboboxItem` for the swatch | Keeps the E2E helper `select_combobox_option` and role queries working |
| Badge and bar | Lifted from the prototype: tinted `Badge` variant per color (new `indigo` variant on `--active`), `max-w-48 truncate` with a tooltip; bar `h-0.75 w-full shrink-0 aria-hidden` | Decided in the design jam; the tech owner placed the badge on the right |

## Constitution Check

- **I. Schema-driven integrity**: no core schema change; `Preference` is a StandardNode. Generated files (`schema/schema.graphql`, `schema/openapi.json`, `frontend/app/src/shared/api/**`) are regenerated in T4 and T7, never edited. PASS.
- **II. Branch-safe**: the row is read and written without branch filters, like the existing date and timezone fields; the setting belongs to the instance, not to a branch (FR-002), and `dev/knowledge/backend/preferences.md` states it (T11). PASS.
- **III. Type safety**: the enum is typed end to end (model, graphene `Enum.from_enum`, Pydantic `InstanceAPI`, generated TypeScript); `Optional[X]` on the two new model fields matches the two adjacent fields of `Preference` for consistency; no `cast`, `any` or `type: ignore`. PASS.
- **IV. Test discipline**: validation in `tests/unit/`; repository, mutation, query and REST in `tests/component/`; Vitest for rules, hooks and components; `tests/e2e/preferences/test_instance_identity.py` last. PASS.
- **V. Query performance**: the only Cypher change adds two return columns to `_RETURN_LABELS`; user input reaches the database only through `StandardNode.save`, which binds parameters. PASS.
- **VI. Security**: the write is gated by `raise_for_permission` before any read; the public read exposes only the label and color, which are meant for every visitor. PASS.
- **VII. Simplicity**: no new package, repository method, dataclass or input type. PASS.

No violations; the Complexity Tracking table is empty.

## Project Structure

### Documentation (this feature)

```text
specs/007-instance-badge-ifc-3232/
├── plan.md              # This file
├── spec.md
├── data-model.md        # Fields, enum, validation rules
├── contracts/           # GraphQL and REST contract deltas
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/infrahub/
├── core/preferences/{constants,models,validation}.py
├── core/query/preference.py
├── graphql/{types,queries,mutations}/preferences.py
└── api/internal.py
backend/tests/
├── unit/core/test_preference_validation.py
├── component/core/test_preference_repository.py
├── component/graphql/{mutations,queries}/test_preferences.py
└── component/api/test_50_internals.py

frontend/app/src/
├── entities/preferences/
│   ├── api/{get-global-preferences-from-api,update-global-preference-from-api}.ts
│   ├── domain/model/{instance-identity,preference}.ts
│   ├── domain/rules/{instance-color,format-document-title,validate-instance-label}.ts
│   ├── domain/use-cases/update-global-preference.ts
│   └── ui/{instance-badge,instance-color-bar,instance-identity-form,global-preferences-editor}.tsx
│       └── queries/update-global-preferences.mutation.ts
├── entities/navigation/ui/app-header.tsx
├── shared/hooks/useTitle.ts
├── shared/components/ui/badge.tsx
├── shared/components/inputs/combobox.tsx
└── pages/{app-layout,login}.tsx
frontend/app/tests/fake/config.ts

tests/e2e/preferences/test_instance_identity.py
docs/docs/deploy-manage/user-management/managing-preferences.mdx
dev/knowledge/backend/preferences.md
changelog/+ifc-3232-instance-badge.added.md
```

**Structure Decision**: web application; backend changes stay inside the existing preferences package and the internal API router, frontend changes stay inside the `preferences` entity plus the three shell files that mount the badge and bar.

## Execution order and parallelism

| Group | Tasks | Mode |
|---|---|---|
| 1 Backend | T1 → (T2 ∥ T3) → T4 | T2 and T3 in parallel after T1 |
| 2 Frontend foundations | T5 ∥ T6 → T7 | after T4 |
| 3 Frontend surfaces | T8 ∥ T9 | after T5 and T7 |
| 4 Closing | T10 → T12; T11 any time after T3 | E2E last |

## Surviving risks

- Stale title on pages without `useTitle`: mitigated by `useTitle("Infrahub")` in `app-layout.tsx` and `login.tsx`, and by restoring a fallback computed from the label current at unmount time instead of the title captured at mount; guarded by the unmount tests, including "label changed while mounted".
- Two Save buttons on the Global preferences page: the new form's button is named "Save instance identity" so the existing `name="Save", exact=True` locators in the E2E and component tests stay unique; each form submits only its own keys, asserted by the form tests.
- Database read on `/api/config`: one read-only call, no row created, asserted by the REST test. A database error on that read is logged and the identity is served as unset, so the login page still renders during an outage. No caching is added on purpose: the row is tiny and a cache would delay propagation to other sessions.
- The return type of `InfrahubGlobalPreferences` changes from `RawPreferencesType` to `GlobalPreferencesType` (a superset); the frontend query uses no fragment, so no client breaks. This GraphQL schema change and the `/api/config` contract change were approved by the tech owner on 2026-11-04 as part of the "new global setting" decision.
- Hand-written USER-scope guard: runs before any read; the mutation and query tests pin the error and the absence of the fields on user types.
- Two generated `InstanceColor` types agree only because name == value; the form passes the REST-derived type into the gql.tada variable, so drift fails type checking.
