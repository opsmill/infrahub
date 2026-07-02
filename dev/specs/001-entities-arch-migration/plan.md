# Implementation Plan: Entities Clean-Architecture Migration

**Branch**: `frontend-entities-arch-migration` | **Date**: 2026-07-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-entities-arch-migration/spec.md`

## Summary

Migrate all ~24 frontend entity modules (and, last, the `nodes/` namespace) toward a DDD-inspired
layout — `api/` (flat, transport + mappers returning domain types), `ui/` (nested, React/TanStack),
and `domain/{model,rules,use-cases}` (pure, split only when >4 files) — reconciling with the existing
`dev/knowledge/frontend/entities-structure.md` rather than replacing it. Generated GraphQL/REST types
are the backend↔frontend contract and are permitted in `domain/`; the boundary enforced by the
incrementally-scoped Biome `noRestrictedImports` guard (Tier 1, no new dependency) is the layout and
cycle rules, not a generated-type ban.
Rollout is one entity per PR, each green
on `pnpm tsc && pnpm build && pnpm test && pnpm biome`, ordered `role-manager` → `branches` (then update
the knowledge doc) → fan-out → `nodes/`.

## Technical Context

**Language/Version**: TypeScript 5.9 (strict), React 19.2
**Primary Dependencies**: Vite 8.0, TanStack Query (server state), Apollo Client (GraphQL transport only), Tailwind 4.2 — **no new dependencies added**
**Storage**: N/A (client-side refactor; data via GraphQL/REST through `shared/api/`)
**Testing**: Vitest 4.1 (unit/component), Playwright 1.60 (E2E) — existing suites must stay green
**Target Platform**: Browser (frontend app)
**Project Type**: Web application frontend (`frontend/app/`)
**Performance Goals**: No runtime change expected; bundle size must not regress (pure file moves + import rewrites)
**Constraints**: Each PR green on `pnpm tsc && pnpm build && pnpm test && pnpm biome`; one entity per PR; preserve public behavior
**Scale/Scope**: 24 entity modules + `nodes/` namespace (~12 sub-modules, ~260 files). Generated types in `domain/` are permitted, so the migration focuses on layout (no root catch-all files), cycle-freedom, and keeping browser storage / global state out of `domain/`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | ✅ PASS | Generated files (`shared/api/`) untouched and never edited. Generated types remain the backend↔frontend contract and may be consumed directly in `domain/`. |
| III. Type Safety & Explicit Contracts | ✅ PASS | Reinforces contracts: `domain/` uses generated types directly or maps to explicit domain types via `api/` when the shapes differ. No new `any`/`as`. `api → domain/model` allows types + plain vocabulary constants (never domain rules/use-cases). |
| IV. Test Discipline | ✅ PASS | No behavior change; existing unit/component tests move with their subjects and must pass. E2E happy paths unchanged and must remain green. No new features → no new E2E required, but no regression permitted. |
| VII. Simplicity & Maintainability | ✅ PASS w/ note | Pragmatic split (>4 files, ≥2 per folder) honors YAGNI — no empty folders, no premature abstraction. **No new dependency** (dependency-cruiser deferred). The one new abstraction (`domain/model` as a named leaf) clarifies an existing dependency rather than inventing one. |
| Quality Gates (format/lint/type/test) | ✅ PASS | Every PR must pass all four commands. Tier-1 Biome guard added incrementally. |
| Changelog | ⚠️ N/A | Internal refactor, no user-facing change → no Towncrier fragment expected. Confirm per-PR at review. |

### Frontend principles

| Principle | Status | Notes |
|---|---|---|
| Reuse Before Reinvent | ✅ PASS | No new UI primitives. Migration relocates existing code; consumes no new shared components. |
| Single State Owner | ✅ PASS (deferred item noted) | Ownership unchanged. The `store`/`branchesState` read inside `branches/domain/get-branches.ts` violates "domain reads no global state" — **explicitly deferred** (FR-016), to be lifted to `ui/` later. Not introduced by this migration. |
| Backend Authoritative | ✅ PASS | No client-side duplication introduced; migration does not touch server-default logic. |
| Component Contracts Designed for All Callers | ✅ N/A | No component prop APIs change. |
| E2E Happy Path | ✅ PASS | No new page. Existing Playwright flows must stay green; no new E2E mandated. |

### Shared Components Inventory

Not applicable — this migration builds no new UI and consumes no new shared components/hooks. It relocates
existing files and rewrites import paths. No "(building new)" rows.

## Project Structure

### Documentation (this feature)

```text
specs/001-entities-arch-migration/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output — the layer/folder model + dependency rules
├── quickstart.md        # Phase 1 output — per-entity migration recipe
├── contracts/
│   ├── dependency-rules.md   # The allowed/forbidden import edges (the "contract")
│   └── biome-guard.md        # Tier-1 noRestrictedImports override shape
├── checklists/
│   └── requirements.md  # Spec quality checklist (from /speckit-specify)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
frontend/app/src/entities/<entity>/
├── api/                      # FLAT. Fetchers (GraphQL/REST), clients, generated↔domain mappers.
│                             # Returns DOMAIN types. May import domain/model (types + plain constants) + shared.
├── domain/
│   ├── model/                # Pure leaf: types, IDs, filters, sorts, inputs, results. No imports from api/rules/use-cases/ui.
│   ├── rules/                # Pure functions, no I-O.
│   └── use-cases/            # Orchestration; calls own entity's api/. Imports model + rules.
│   # (domain/ stays FLAT when ≤4 files; no folder for <2 files)
└── ui/                       # NESTED. ui/queries/ (TanStack), ui/hooks/, per-component folders.
                              # Imports own domain/, shared/, other entities' domain/ + ui/.

frontend/app/biome.jsonc      # Tier-1 guard: overrides[] with per-entity domain/ globs (grows per PR)
dev/knowledge/frontend/entities-structure.md   # Updated from the branches result (P1 story 2)
```

**Structure Decision**: Web-application frontend. Migration operates entirely within
`frontend/app/src/entities/`, plus the Biome config and one knowledge doc. Dependency direction
kept as `ui → domain → api` with the single new edge `api → domain/model` (types + plain vocabulary constants; `domain/model` is a pure leaf, so this stays acyclic).

## Dependency Contract (authoritative)

```text
Allowed:                                   Forbidden:
  ui → domain (same entity)                  domain → ui / routing / TanStack / Apollo
  ui → shared                                domain → browser storage / toast libs
  ui → other-entity domain, ui              api → domain/rules, domain/use-cases, ui
  domain/use-cases → own api/                domain/model → anything in api/rules/use-cases/ui
  domain/use-cases → domain/model, rules     ui → another entity's api/
  domain/rules → domain/model                (any import creating a cycle)
  domain → generated GraphQL/REST types
  api → domain/model (types + plain constants)
  api → shared
  shared → authentication (cross-cutting)
```

> **Notes:** generated types (incl. wire DTOs) are the backend↔frontend contract and are
> allowed in `domain/`; `api/` mappers are optional. `shared/` may depend on the
> `authentication` entity as a cross-cutting exception (`shared/` stays a leaf for every
> other entity).

## Complexity Tracking

*No unjustified constitution violations.* One deferral is tracked, not a violation:

| Item | Why deferred | Handling |
|------|--------------|----------|
| `store`/`branchesState` read in `branches/domain/get-branches.ts` (global state in domain) | Fixing it (lifting the read to `ui/`) is a behavior-adjacent change orthogonal to the structural move; bundling it would enlarge the `branches` PR and its risk | Recorded in FR-016; follow-up after migration. Tier-1 guard's browser-storage rule may be relaxed for this one file or the file annotated until the follow-up lands. |
| dependency-cruiser (Tier-2 directional enforcement) | New dependency → AGENTS.md ask-first gate | Deferred; directional rules (model-as-leaf, api→model-only) enforced by review until separately approved. |
