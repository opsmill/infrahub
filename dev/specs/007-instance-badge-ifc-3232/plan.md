# Implementation Plan: Instance label and color as global settings

**Branch**: `ple-instance-badge-ifc-3232` | **Date**: 2026-11-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/007-instance-badge-ifc-3232/spec.md`, a design jam of four prototyped header directions (prototype removed before the PR, not kept in the repository), and three planning framings (minimal change, clean boundaries, test-first) merged on 2026-11-05.

## Summary

An administrator who holds `manage_global_preferences` sets an instance label (text, at most 32 characters after trimming) and an instance color (one of seven presets) on the Global preferences page. Both values are two new nullable fields on the existing global `Preference` row (`owner_id = "__global__"`), written through the existing `InfrahubSetPreferences(scope: GLOBAL)` mutation and read by the administrator through `InfrahubGlobalPreferences`. The public `/api/config` response gains an `instance` block read from that row, so every visitor, including the login page, renders a tinted badge at the right of the app header next to the status indicators, a 3 px colored bar above the sidebar and header, and a tab title of the form `<label> · <page title>`.

On 2026-11-10 the scope was extended with IFC-3588, shipped in the same pull request: an operator can set a default label and color for the deployment through `INFRAHUB_INSTANCE_LABEL` and `INFRAHUB_INSTANCE_COLOR` (or the `[instance]` section of `infrahub.toml`); `/api/config` resolves each field as saved value, else deployment default, else `null`, and adds `instance_defaults`; the form names the defaults; and the browser tab icon shows the Infrahub mark in the instance color. See *Extension: deployment defaults and colored tab icon (IFC-3588)* below.

## Technical Context

**Language/Version**: Python 3.14 (backend), TypeScript 6.0 / React 19.3 (frontend)

**Primary Dependencies**: FastAPI, graphene, Pydantic 2 (backend); Vite 8, Tailwind CSS 4, `@infrahub/ui`, TanStack Query, react-hook-form (frontend)

**Storage**: Neo4j; the global `Preference` StandardNode (no schema node, no graph migration, no seeded row)

**Testing**: pytest (unit and component tiers), Vitest browser mode, pytest-playwright E2E in `tests/e2e/`

**Target Platform**: Infrahub web UI on desktop browsers; REST and GraphQL API

**Project Type**: Web application (backend + frontend)

**Performance Goals**: `/api/config` performs one read-only `get_for_owner` per call; no polling is added, the other open tabs refetch `["config"]` on window focus

**Constraints**: No inline styles or arbitrary Tailwind values (theme tokens only); no `cast`, `any` or `type: ignore`; generated files regenerated, never edited; the E2E test is the last task and the feature is not complete until it passes

**Scale/Scope**: 12 tasks for IFC-3232; about 10 backend files, about 20 frontend files, 1 E2E file, 2 docs files. IFC-3588 adds 9 done tasks and 1 open task (T013 to T022) over 36 committed files, tests and generated files included, plus the review fixes of T021.

## Decisions

| Question | Decision | Why |
|---|---|---|
| Mutation arguments | Two flat arguments `instance_label: String`, `instance_color: InstanceColor` with the existing `_UNSET` sentinel | Follows the `date_format` / `timezone` pattern; an input object pays off only for fields that are out of scope |
| Keeping the fields off per-user preferences | `GlobalPreferencesType(RawPreferencesType)` subclass used only by `InfrahubGlobalPreferences`; the mutation raises `ValidationError` when `scope != GLOBAL` and either argument is provided, before any read | FR-008; the only way to make the fields unselectable on the user and effective queries |
| Color wire format | `InstanceColor(InfrahubStringEnum)` with name == value, uppercase (`RED = "RED"`, …) | graphene puts member names on the GraphQL wire and Pydantic serialises values on REST; equality keeps `schema.graphql`, `openapi.json` and both generated TypeScript types consistent. Docs write the names in lowercase |
| Public read path | `ConfigAPI.instance: InstanceIdentityAPI` read from `PreferenceRepository(db).get_for_owner(GLOBAL_OWNER_ID)`; missing row → both `None` (since IFC-3588: each `None` field falls back to the deployment default) | Every client loads `/api/config` before first render, including the login page (FR-009, FR-010) |
| Tab title | `useTitle` registers the page title in an atom; one `DocumentTitle` owner in `entities/preferences/ui/` writes `<label> · <page title>`, or `<label> · Infrahub` when no page registers a title | A single writer reads the label and the latest registered title at every render, so leaving a page always lands on a title that carries the current label (US2-4) |
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
│   ├── domain/model/preference.ts
│   ├── domain/rules/{instance-color,format-document-title,validate-instance-label}.ts
│   ├── domain/use-cases/update-global-preference.ts
│   └── ui/{document-title,instance-badge,instance-color-bar,instance-identity-form,global-preferences-editor}.tsx
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

- Stale title on pages without `useTitle`: mitigated by the single `DocumentTitle` owner, which falls back to `<label> · Infrahub` when no page registers a title and recomputes the title whenever the label or the registered title changes; guarded by the `DocumentTitle` tests, including "label changed while a page is open" and "page unmounts".
- Two Save buttons on the Global preferences page: the new form's button is named "Save instance identity" so the existing `name="Save", exact=True` locators in the E2E and component tests stay unique; each form submits only its own keys, asserted by the form tests.
- Database read on `/api/config`: one read-only call, no row created, asserted by the REST test. Any exception on that read is logged and the identity is served as unset, so the login page still renders during an outage. IFC-3588 keeps this behavior and does not serve the deployment defaults in this case. No caching is added on purpose: the row is tiny and a cache would delay propagation to other sessions.
- The return type of `InfrahubGlobalPreferences` changes from `RawPreferencesType` to `GlobalPreferencesType` (a superset); the frontend query uses no fragment, so no client breaks. This GraphQL schema change and the `/api/config` contract change were approved by the tech owner on 2026-11-04 as part of the "new global setting" decision.
- Hand-written USER-scope guard: runs before any read; the mutation and query tests pin the error and the absence of the fields on user types.
- Two generated `InstanceColor` types agree only because name == value; the form passes the REST-derived type into the gql.tada variable, so drift fails type checking.

## Extension: deployment defaults and colored tab icon (IFC-3588)

**Date**: 2026-11-10 | **Source**: [IFC-3588](https://opsmill.atlassian.net/browse/IFC-3588), decisions taken with the tech owner on 2026-11-10 | **Spec**: User Story 5, FR-018 to FR-025

### Decisions

| Question | Decision | Why |
|---|---|---|
| Where the defaults come from | `InstanceSettings(BaseSettings)` in `backend/infrahub/config.py`, `env_prefix="INFRAHUB_INSTANCE_"`, fields `label: str \| None` and `color: InstanceColor \| None`; `Settings.instance = Field(default_factory=InstanceSettings)`; `ConfiguredSettings.instance` property | Follows the other settings sections, so the environment variables and the `[instance]` section of `infrahub.toml` work without extra code. The factory makes an invalid value fail when the settings load rather than when `config.py` is imported |
| Validation of the defaults | `field_validator("label")` calls `validate_instance_label(value, field_name="INFRAHUB_INSTANCE_LABEL")` and turns its `ValidationError` into a `ValueError`; `field_validator("color", mode="before")` (`normalize_color`) strips and uppercases a string, turns an empty result into `None`, and rejects an unknown name with "INFRAHUB_INSTANCE_COLOR must be one of RED, AMBER, GREEN, BLUE, INDIGO, PURPLE, GRAY" | Same rules as a saved label; the messages name the variable the operator sets; a deployment tool can pass an unset variable as an empty string, so empty means not set |
| Saved value or default | A saved value overrides the default per field; resetting the saved value applies the default again; the form fields stay editable | Decision of the tech owner on 2026-11-10: override from the web UI rather than locking the fields. Known limitation: while a default is set, the web UI cannot remove that field, only replace it |
| Public read | `instance` resolved per field in `InstanceIdentityResolver.resolve`; `instance_defaults` added to `ConfigAPI`; a failed read serves `instance` as unset and still serves `instance_defaults` | The form needs the defaults to name them, and the GraphQL query keeps returning saved values only so the form can tell the two apart |
| Tab icon | `InstanceFavicon` recolors `infrahub-mark.svg` with a per-preset `faviconColor` and writes it to `link[rel="icon"]` as a data URL | The tech owner asked for a colored tab icon, outline variant, on 2026-11-10; favicon upload stays out of scope |

### Module move to avoid the `config` → `core` import cycle

`config.py` needs `InstanceColor` and `validate_instance_label` to validate the defaults. They lived in `infrahub/core/preferences/constants.py` and `validation.py`. Importing anything under `infrahub.core` runs `infrahub/core/__init__.py`, which imports `infrahub.core.registry`, which imports `infrahub.lock`, which imports `infrahub.config`. So `config.py` cannot import from `infrahub.core` without a cycle.

The first commit of the extension moves `InstanceColor`, `INSTANCE_LABEL_MAX_LENGTH`, `validate_instance_label` and its control-character helper to a new module `backend/infrahub/instance_identity.py`, which imports only `infrahub.exceptions` and `infrahub.utils`. Every caller (`core/preferences/models.py`, `core/query/preference.py`, `graphql/types/preferences.py`, `graphql/mutations/preferences.py`, `api/internal.py`) now imports from it. The label tests move from `backend/tests/unit/core/test_preference_validation.py` to `backend/tests/unit/test_instance_identity.py`; behavior is unchanged.

### Dependency structure in `backend/infrahub/api/internal.py`

- `get_instance_defaults() -> InstanceIdentityAPI` builds the defaults from `config.SETTINGS.instance`.
- `build_instance_identity_resolver(db = Depends(get_db))` builds an `InstanceIdentityResolver` from a `PreferenceRepository` and `get_instance_defaults()`. Its `resolve()` reads the global row through `PreferenceRepository.get_for_owner(GLOBAL_OWNER_ID)`. With no row it returns a copy of the defaults; otherwise each field is the saved value when it is not `None`, else the default. Any exception on the read is logged ("Instance identity unavailable, serving it as unset") and both fields are returned as `None`, because a default could name a different stage than the saved value it stands in for (changed during review, T021).
- `get_config(instance_resolver = Depends(build_instance_identity_resolver))` puts `await instance_resolver.resolve()` and `instance_resolver.defaults` into `ConfigAPI`. This shape follows the review on the PR: the dependency builds the component, and the endpoint calls it.

Both values arrive as parameters, so `get_config` can be called directly with explicit values, as the LDAP unit tests in `backend/tests/unit/api/test_internal_config_ldap.py` do.

### Form hints

`InstanceIdentityForm` reads `instance_defaults` from `useConfig()`. `InstanceLabelField` sets the default label as the input placeholder and, while the trimmed field is empty, renders "Leave empty to use the deployment default: `<label>`." and adds its id to `aria-describedby`. `InstanceColorField` sets the combobox placeholder to "Deployment default: `<Color>`" when a default color exists, else "No color". Nothing is disabled.

### Tab icon approach

- `frontend/app/src/entities/preferences/domain/rules/instance-color.ts`: each preset gains `faviconColor`, a hex value, because the tab icon is rendered outside the page and cannot read the theme tokens; `instanceFaviconColor(color)` returns it or `null`.
- `frontend/app/src/entities/preferences/domain/rules/recolor-infrahub-mark.ts`: `recolorInfrahubMark(markSvg, color)` replaces `#0B97BB` (the accent fill and gradient starts), `#264D59` and `#0C3E54` (the two stops of the hexagon outline gradient), without regard to case. Every other color, such as `#0B1828` and `white`, is kept.
- `frontend/app/src/entities/preferences/ui/instance-favicon.tsx`: imports `@/assets/infrahub-mark.svg?raw`, and in an effect keyed on the color sets the `href` of `link[rel="icon"]` to `data:image/svg+xml,` plus the encoded recolored SVG. The effect cleanup restores the original `href` (`/favicons/favicon.ico` in `frontend/app/index.html`). With no color in effect it does nothing. It reads `instance.color`, so a default color also colors the icon.
- Mounted in `frontend/app/src/app/app.tsx` inside `ConfigProvider`, next to `DocumentTitle`.

Whether Safari shows an SVG tab icon is not verified.

### Files

```text
backend/infrahub/
├── instance_identity.py                  # new: enum, length limit, label validator
├── config.py                             # InstanceSettings, Settings.instance, ConfiguredSettings.instance
├── api/internal.py                       # per-field resolution, instance_defaults
└── core/preferences/{constants,models,validation}.py, core/query/preference.py,
    graphql/{types,mutations}/preferences.py  # imports moved
backend/tests/
├── unit/test_instance_identity.py        # new: label rules, moved from test_preference_validation.py
├── unit/config/test_instance_settings.py # new: accepted and rejected defaults
├── unit/api/test_internal_config_ldap.py
└── component/api/test_50_internals.py    # per-field resolution, read failure, reset

frontend/app/src/
├── app/app.tsx
├── entities/preferences/domain/rules/{instance-color,recolor-infrahub-mark}.ts
└── entities/preferences/ui/{instance-favicon,instance-identity-form}.tsx
frontend/app/tests/fake/config.ts         # instance_defaults, generateConfigWithInstanceDefaults

schema/openapi.json, frontend/app/src/shared/api/rest/types.generated.ts   # regenerated
docs/docs/reference/configuration.mdx, docker-compose.yml, development/docker-compose.yml  # regenerated
tasks/docs.py                             # renders the enum values of an optional enum setting
docs/docs/deploy-manage/user-management/managing-preferences.mdx
dev/knowledge/backend/preferences.md
changelog/+ifc-3588-instance-env-defaults.added.md
```

### Constitution check for the extension

- **I. Schema-driven integrity**: no core schema change and no GraphQL schema change. `schema/openapi.json`, the REST types, the configuration reference and the compose environment blocks are regenerated. PASS.
- **III. Type safety**: `InstanceColor | None` on the settings, the REST model and the generated TypeScript type; no `cast`, `any` or `type: ignore`. PASS.
- **IV. Test discipline**: settings and label rules in `tests/unit/`; resolution, read failure and reset in `tests/component/api/test_50_internals.py`; Vitest for the form hints, the recolor rule and `InstanceFavicon`. No E2E covers the defaults or the tab icon (see T022). PARTIAL.
- **VII. Simplicity**: one new module and one settings section; no new package or dependency. PASS.

### Surviving risks of the extension

- No E2E for the deployment defaults: the E2E suite starts one server per session, so a test cannot set a different environment for one test.
- The tab icon is checked only by Vitest; no E2E reads it, and Safari support for an SVG tab icon is not verified.
- The validation messages name `INFRAHUB_INSTANCE_LABEL` and `INFRAHUB_INSTANCE_COLOR` also when the invalid value comes from the `[instance]` section of `infrahub.toml`.
- While a deployment default is set for a field, the web UI cannot remove that field; it can only replace it with a saved value, because an empty saved value falls back to the default (the precedence the tech owner chose on 2026-11-10).
- During a failed read of the saved values, every page shows no badge and no bar, even when the deployment sets defaults.
