# 6. Frontend Entity Layers: `ui → domain → api` with api-owned Mappers

**Status:** Accepted
**Date:** 2026-07-03
**Author:** @opsmill-team
**Source:** specs/archive/001-entities-arch-migration/research.md (D1–D5) and tasks.md decision log

## Context

The frontend `src/entities/` folder holds ~24 entity modules plus the large `nodes/` namespace. Before the entities clean-architecture migration, most entities followed the documented three-layer architecture (`ui → domain → api`), but the internal shape of `domain/` was flat and inconsistent, entity-root catch-all files (`types.ts`, `constants.ts`, `utils.ts`) accumulated unclassified code, and mapping between generated wire shapes and domain types had no fixed home. An earlier proposal suggested inverting the dependency direction (`api → domain` with injected facades, ports-style) and flattening `ui/`.

## Decision

Keep and sharpen the existing direction rather than inverting it:

- **`ui → domain → api`**: `domain/use-cases` imports and calls its own entity's `api/` fetchers directly. No ports/facade layer.
- **`domain/` is always organized as `model/` (vocabulary: types, kind constants, states), `rules/` (pure, no-I/O functions), and `use-cases/` (orchestration)** — every entity, regardless of size, so the layout is uniform across the codebase. A file goes into whichever folder matches its role, even alone. There are no entity-root catch-all files. Within the layer folders, a concept is split into its own file/area only when the domain core becomes hard to navigate, the concept has enough model/rules/tests/context to deserve its own area, or keeping it inside the generic files makes them harder to understand.
- **Mappers live in `api/`** (the anti-corruption layer). A single type-only edge `api → domain/model` is permitted; `domain/model` is a pure leaf (imports nothing from `api/`, `rules/`, `use-cases/`, or `ui/`), which keeps the graph acyclic. As implemented (option-b), mappers are *called by* use-cases and fetchers still return raw `{data, errors}`; the stronger "fetchers return domain types" form was considered and not adopted.
- **`ui/` keeps nested subfolders** (`ui/queries/` for TanStack, `ui/hooks/`, `ui/routing/`, per-component folders); `api/` stays flat.

## Consequences

- The dependency graph is a DAG with `domain/model` as the leaf; a stray `model → api` import is a real cycle and must be rejected in review.
- `domain/` stays portable: no React, TanStack, Apollo, browser storage, or toast imports.
- Every file has exactly one home determined by its role, so reviews argue about classification, not location taste. The canonical worked example is `entities/branches`; the full rules live in `dev/knowledge/frontend/entities-structure.md`.

## Alternatives Considered

- **`api → domain` inversion with injected API facades (ports-style)** — rejected: a 71-file rewrite contradicting the already-enforced documented direction, re-introducing the `ports/` layer the architecture deliberately dropped, with no functional gain.
- **Flat `ui/`** — rejected: collapses query factories, hooks, and components into one directory (~40 files for `branches`) and contradicts the `ui/queries/` TanStack placement rule.
- **Numeric split threshold (split only when `domain/` holds >4 files, no folder under 2 files)** — used during the migration's planning, then rejected: an arbitrary count makes similar entities look different and forces restructuring churn when an entity crosses the line. Consistency won: the three folders exist everywhere; judgment governs only concept-level file splits within them.
- **Full "fetchers return domain types" (mappers invisible to use-cases)** — evaluated during implementation and deferred as optional; the option-b shape (use-cases call mappers) preserved behavior with less churn.
