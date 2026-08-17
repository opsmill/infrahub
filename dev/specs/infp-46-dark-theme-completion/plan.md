# Implementation Plan: Dark Theme Completion

**Branch**: `dark-theme-completion-infp-46` | **Date**: 2026-08-17 | **Spec**: [spec.md](./spec.md)

**Ticket**: [INFP-46](https://opsmill.atlassian.net/browse/INFP-46)

**Input**: [spec.md](./spec.md), informed by [research.md](./research.md)

## Summary

The dark palette exists but is unreachable: it is activated only by a development-only
`@custom-variant` and a manually added class. This plan makes it reachable, binds every surface that
currently pins itself to light, retires the token debt, and turns non-production deployments dark by
default so the team dogfoods it.

The technical spine is a **single resolution, computed once and handed down**. A stored choice
(`LIGHT`/`DARK`/`SYSTEM`) resolves server-side across the user and organisation layers; the client
resolves `SYSTEM` against the operating system to a strict `light`/`dark`; every consumer — the
document class, GraphiQL, Mermaid, the schema visualizer — takes that one resolved value. No
consumer runs its own `prefers-color-scheme` check, which is what makes them incapable of drifting
apart.

Two decisions carry most of the risk and are settled in [research.md](./research.md): the
"non-production build" signal is PEP 440 pre-release status on the running version, published as a
resolved value on the unauthenticated config payload (§R1); and the first paint is owned by an inline
classification script reading a `localStorage` mirror, not by React (§R2).

## Technical Context

**Language/Version**: Python 3.14 (backend), TypeScript 5.9 (frontend)

**Primary Dependencies**: FastAPI 0.131, Graphene, Pydantic 2.12; React 19.2, Vite 8.0, Tailwind CSS
4.2, `graphiql` 5.2.4, `rehype-mermaid`, `infrahub-schema-visualizer` (submodule)

**Storage**: Neo4j — one additional nullable field on the existing `Preference` `StandardNode`. No
new records, no data migration expected.

**Testing**: pytest 9.0 (backend unit), Vitest 4.1 (frontend unit), Playwright 1.60 and
pytest/testcontainers (end-to-end)

**Target Platform**: Web application, evergreen browsers

**Project Type**: Web — Python backend + React frontend, plus one external repository

**Performance Goals**: Correct theme in the first painted frame on every load after a browser's first
visit. Theme switching repaints without a reload and without re-running the Mermaid pipeline on every
React render.

**Constraints**: The light theme must be visually unchanged (FR-020). Semantic colors must stay
mutually distinguishable in both themes (FR-021). The login page must be themed before a session
exists.

**Scale/Scope**: 3 backend layers (constants/model/GraphQL) + 1 config field; ~104 existing CSS
tokens reused, none added; ~20 application files carrying hardcoded variants; 1 external repository.

## Constitution Check

*GATE: evaluated before Phase 0 research and re-checked after the Phase 1 design below.*

| Principle | Assessment |
|---|---|
| **I. Schema-Driven Integrity** | ⚠ **Gate — requires sign-off.** Generated artifacts change: `schema/schema.graphql`, `schema/openapi.json`, `frontend/app/src/shared/api/rest/types.generated.ts`. All are regenerated, never hand-edited, and committed. `AGENTS.md` lists GraphQL schema modifications and database schema changes as **Ask First**; see [Open governance points](#open-governance-points). |
| **II. Branch-Safe by Default** | ✅ Not applicable in substance. `Preference` is a `StandardNode` outside the branched graph, and a theme has no temporal or per-branch meaning. No branch-aware queries are introduced. |
| **III. Type Safety & Explicit Contracts** | ✅ `Theme` is a closed enum end to end — rejected at construction on read, typed through GraphQL, and a discriminated union on the client. ⚠ Two inherited constraints must be honoured: `Optional[Theme]` not `Theme \| None` (`StandardNode.guess_field_type`), and single-line enum descriptions (SDL printer stability). |
| **IV. Test Discipline** | ✅ Resolution logic (both stages), the pre-release derivation, and the three-state mutation argument are pure functions with table-driven unit tests. The version-derived default is tested by calling the resolver with version strings, never by faking a deployment. |
| **V. Query Performance & Efficiency** | ✅ One extra nullable property on a record already fetched. No new queries, no new round trips — `theme` rides the existing effective-preferences query and the existing config payload. |
| **VI. Security & Input Boundaries** | ✅ The config payload gains only a resolved `"light"`/`"dark"`; the version string is **not** newly exposed to anonymous callers. Global-scope writes reuse the existing permission check; no new permission is introduced. |
| **VII. Simplicity & Maintainability** | ✅ Extends the existing preference machinery rather than adding storage. Removes more than it adds: the `@custom-variant` escape hatch, ~20 files of hardcoded variants, and GraphiQL's now-redundant theme picker. |

**Post-design re-check**: no violations introduced. [Complexity Tracking](#complexity-tracking) is
empty.

## Project Structure

### Documentation (this feature)

```text
dev/specs/infp-46-dark-theme-completion/
├── spec.md
├── research.md
├── data-model.md
├── quickstart.md
├── plan.md                       # this file
├── contracts/
│   ├── graphql-preferences.md
│   └── rest-config.md
├── checklists/
│   └── requirements.md
└── tasks.md                      # produced by the tasks phase
```

### Source code

```text
backend/infrahub/
├── core/preferences/
│   ├── constants.py              # + Theme enum
│   └── models.py                 # + Preference.theme: Optional[Theme]
├── graphql/
│   ├── types/preferences.py      # + Theme, EffectiveTheme; += EffectivePreferencesType, RawPreferencesType
│   ├── queries/preferences.py    # resolve theme through the existing chain
│   └── mutations/preferences.py  # + theme argument, _UNSET three-state handling
├── config.py                     # + ExperimentalFeaturesSettings.default_theme override
├── api/internal.py               # + ConfigAPI.default_theme (resolved, unauthenticated)
└── core/preferences/theme.py     # NEW — version → default theme, pure

frontend/app/
├── index.html                    # + inline pre-paint classification script
└── src/
    ├── shared/context/theme-context.tsx      # NEW — holds resolved "light"|"dark"; imports no entity
    ├── entities/preferences/
    │   ├── domain/model/preference.ts        # + theme
    │   ├── domain/rules/theme.ts             # NEW — stage-2 resolution, pure (no storage access)
    │   ├── ui/theme-provider.tsx             # NEW — fills the shared context; applies class, mirrors, listens
    │   ├── ui/preference-fields.tsx          # + theme field with pre-release marker
    │   └── ui/queries/*.ts                   # + theme in query and mutation documents
    ├── pages/graphql/index.tsx               # forcedTheme="light" → resolved theme
    └── shared/components/
        ├── editor/markdown/
        │   ├── markdown-with-mermaid.tsx     # memoised theme-dependent plugins
        │   └── mermaid-diagram.tsx           # bg-white → token
        └── data-viewer/data-viewer.tsx       # neutral/white → tokens

frontend/packages/ui/src/styles/theme.css     # − @custom-variant escape hatch
```

**Structure Decision**: Web application layout. The theme preference slots into the existing
`entities/preferences/` vertical on both sides, so no new architectural seam appears. The one new
backend module (`core/preferences/theme.py`) exists to keep the version→default derivation a pure,
directly testable function rather than logic embedded in the API layer.

⚠ **The context must live in `shared/`, not in the entity.** `shared/` components consume the
resolved theme (Mermaid, the data viewer), and `dev/knowledge/frontend/entities-structure.md`
prohibits `shared/` from importing an entity: an entity's component "may be imported by other
entities and by higher layers — never by `shared/`". So the dependency runs one way only:

```text
shared/context/theme-context.tsx      ← declares the context, imports no entity
        ▲                    ▲
        │ fills              │ consumes
entities/preferences/ui/     shared/components/*, pages/*
  theme-provider.tsx
```

This mirrors `DatePreferencesProvider` exactly — it lives in `entities/preferences/ui/` and fills
`shared/context/date-preferences-context.tsx`, whose docstring records that the shared context
"never imports `entities`". Copy that arrangement rather than inventing one.

⚠ `domain/rules` may not touch browser storage, so `domain/rules/theme.ts` stays a pure function and
the `localStorage` mirror lives in the provider.

## Implementation phases

Ordered by dependency, not by the numbering of the original handover list. Phase A is the keystone;
B–E are independent of each other once A exists and can proceed in parallel.

### Phase A — Theme preference (US1) · P1

The foundation. Everything else consumes the resolved value it produces.

1. **Backend store** — `Theme` enum in `constants.py`; `theme: Optional[Theme] = None` on
   `Preference`; repository untouched (it persists whatever the model declares).
2. **Backend GraphQL** — per [contracts/graphql-preferences.md](./contracts/graphql-preferences.md).
   ⚠ The mutation's three-state `_UNSET` handling is the single easiest thing to get wrong: collapsing
   "omitted" and "null" makes an override impossible to clear.
3. **Regenerate** `schema/schema.graphql`, then frontend types.
4. **Frontend model and query** — extend `PreferenceValues` / `EffectivePreferences`; add `theme` to
   the effective-preferences query and the upsert mutation.
5. **Stage-2 resolution** — `domain/rules/theme.ts`: pure `(choice, systemPrefersDark) → "light" |
   "dark"`.
6. **Theme provider** — applies the class to the document element, writes the `localStorage` mirror,
   subscribes to `prefers-color-scheme` changes (FR-007) and to `storage` events (multi-tab), and
   exposes the resolved value to consumers. Sits alongside the existing
   `date-preferences-provider.tsx`, which is the established pattern for this shape.
7. **Pre-paint script** — inline in `index.html` `<head>`, before the module script, reading the
   mirror. Per [research.md](./research.md) §R2, a browser's first-ever visit still corrects after
   the config payload arrives; this is an accepted, documented boundary.
   ⚠ It runs before everything and blocks rendering, so it must fail safe. `localStorage` access
   **throws** when storage is disabled or unavailable (Safari private browsing), and an uncaught
   throw here degrades the whole load for a cosmetic feature — wrap it in `try`/`catch` and fall
   through to the light default. Validate the stored string against the known set before applying it
   rather than using it directly as a class name.
   ⚠ No Content-Security-Policy is configured today, so the inline script is fine. If one is ever
   added it needs a nonce or hash, or the first paint silently reverts to light.
8. **Preference field** — a `Combobox` matching the existing fields, with the pre-release marker on
   dark and a description on "match system" making clear it can resolve to the pre-release palette
   (FR-008). "Automatic (inherited)" remains the empty-value label.
9. **Retire the escape hatch** — remove `@custom-variant dark` and its `TODO: DELETE` (FR-019). ⚠ Do
   this **last** within Phase A: it is what the whole current dark rendering depends on, so removing
   it before the provider works leaves the tree with no way to reach dark at all.

### Phase B — Non-production default (US2) · P1

1. `core/preferences/theme.py` — pure `(version: str, override) → "light" | "dark"`.
2. `ExperimentalFeaturesSettings.default_theme: Literal["light","dark"] | None`. ⚠ Tri-state, not
   `bool` — see [contracts/rest-config.md](./contracts/rest-config.md).
3. `ConfigAPI.default_theme`; regenerate the OpenAPI schema and frontend REST types.
4. Client substitutes it when the effective preference resolves with source `DEFAULT`.
5. Pin the theme explicitly in both end-to-end suites so they stop depending on the build's version.

### Phase C — Embedded surfaces (US3, US4) · P2

1. **GraphiQL** — replace `forcedTheme="light"` with the resolved value. ⚠ Pass `"light"`/`"dark"`,
   never `"system"`: GraphiQL would then run its own detection and could disagree with the
   application (see [research.md](./research.md) §R3).
2. **Mermaid** — derive `mermaidConfig.theme`; ⚠ memoise the plugin array on the resolved theme, or
   the rehype pipeline re-runs every render; tokenise the `bg-white` container and the error banner.

### Phase D — Token discipline (US5, US6) · P2/P3

1. Migrate the ~20 files carrying hardcoded `dark:` variants to tokens.
2. `shared/components/ui/badge.tsx` last and separately — twelve occurrences that likely encode
   semantic colors, needing a palette decision under FR-021 rather than a mechanical swap.
3. Data viewer: `neutral`/`bg-white` → tokens.
4. Add the automated guard that makes SC-004 a standing property. `betterer` is already in CI and
   is the lower-friction option; a lint rule is the stricter one. Decide when writing the tasks.
5. ⚠ Verify the light theme is unchanged after every batch, not once at the end — this is the
   constraint a token swap breaks most easily, and a late discovery is expensive to bisect.

### Phase E — Schema visualizer (US7) · P3

1. `git submodule update --init frontend/packages/schema-visualizer`.
2. Upstream pull request on `opsmill/infrahub-schema-visualizer`: dark support, theme accepted from
   the embedding application.
3. Merge and release upstream.
4. Bump the pointer here. ⚠ Never point at an unpushed commit.

## Open governance points

Flagged rather than assumed, per `AGENTS.md` **Ask First**. Both want a decision before Phase A
starts.

1. **GraphQL schema modification.** New `Theme` enum, new `EffectiveTheme` type, new field on two
   types, new mutation argument. Additive and non-breaking, but it changes the public schema.
2. **Persisted model change.** A nullable field on the `Preference` `StandardNode`. Expected to be
   additive with no data migration — pre-existing rows lack the property and read as `None`, which is
   already the valid "nothing set" state. This expectation should be confirmed by someone who owns
   the `StandardNode` persistence path rather than taken on the reasoning alone.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Removing `@custom-variant` before the provider works | Dark becomes unreachable mid-branch | Sequenced last within Phase A |
| Mermaid plugin array rebuilt per render | Continuous re-render, pinned CPU | Memoise on resolved theme; watch the profiler during US4 verification |
| Passing `"system"` to GraphiQL | Sandbox silently disagrees with the app | Pass only resolved `light`/`dark` |
| GraphiQL's `forcedTheme` reactivity and picker-hiding are not documented public API — both were verified by reading the bundled source of 5.2.4 | A minor bump could break the binding without notice | Record the version dependency; re-verify on upgrade; cover the binding with a test |
| `shared/` importing `entities/` for the theme | Prohibited dependency direction, and **no lint guard exists** — layer rules are review-enforced only | Context in `shared/`, provider in the entity, per the `DatePreferencesProvider` precedent |
| Pre-paint script throws on unavailable `localStorage` | Blocking head script degrades every load | `try`/`catch` with a light fallback; validate the value before applying |
| Token swap alters the light theme | Breaks FR-020, the one hard preservation constraint | Verify light after every batch |
| Semantic colors flattened during migration | Status/severity no longer distinguishable (FR-021) | Handle `badge.tsx` as a palette decision, not a swap |
| Default flip destabilises end-to-end suites | Failures misattributed | Pin the theme in both suites; baseline only from a green post-#10284 run |
| #10284 does not land | Phase D's target surfaces do not exist | Phases A–C and E are independent of it; D rebases onto it |
| Submodule pointer moved to an unpushed commit | Breaks every other checkout | Upstream merge strictly precedes the bump |

## Dependencies

- PR [#10284](https://github.com/opsmill/infrahub/pull/10284) merged — Phase D only.
- Existing account-backed preference machinery (user/global layers, effective resolution, source
  reporting, permissions, locking).
- `hatch-vcs` version derivation (the INFP-566 work) — Phase B.
- `opsmill/infrahub-schema-visualizer` — Phase E only.

## Complexity Tracking

No constitutional violations require justification. This feature reuses an existing store, an
existing resolution chain, an existing permission model, and an existing token system; the only new
module is a pure function extracted for testability.
