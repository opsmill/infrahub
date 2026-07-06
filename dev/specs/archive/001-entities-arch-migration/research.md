# Phase 0 Research: Entities Clean-Architecture Migration

All open questions were resolved during the 2026-07-02 grilling session; this file records the
decisions, rationale, and rejected alternatives. No `NEEDS CLARIFICATION` markers remain.

## D1 — Dependency direction

**Decision**: Keep `ui → domain → api`. `domain/use-cases` imports and calls its own entity's `api/` fetchers directly.

**Rationale**: The codebase already implements this in 71 domain files and the pattern is documented in `entities-structure.md`. The original proposal's `api → domain` inversion would require rewriting every domain function to accept an injected API facade — pure churn for no functional gain, and it re-introduces the `ports/` layer the architecture deliberately dropped.

**Alternatives rejected**: `api → domain` with injected facade (ports-shaped) — rejected as a 71-file rewrite contradicting the enforced doc.

## D2 — `ui/` nesting vs flat

**Decision**: `ui/` keeps nested subfolders (`ui/queries/`, `ui/hooks/`, per-component folders). `api/` stays flat.

**Rationale**: The doc mandates `ui/queries/` (where TanStack lives). 29 `ui/queries/` dirs exist. Flattening would collapse query factories, hooks, and every component into one directory (e.g. `branches/ui/` → ~40 flat files). `api/` is already flat everywhere, so the "no nested folders" rule is retained only there.

**Alternatives rejected**: Flat `ui/` (from the original spec) — rejected as destroying navigability and contradicting the TanStack placement rule.

## D3 — Mapper location ("Option A")

**Decision**: Mapping logic lives in `api/`. `api/` fetchers return **domain** types. A single new type-only edge `api → domain/model` is permitted. `domain/` becomes free of generated GraphQL/REST types.

**Rationale**: A mapper structurally touches both a generated wire shape and a domain type, so it must import both — it cannot satisfy both "`api/` imports only shared" and "`domain/` imports no generated types" simultaneously. One rule must yield. Putting the mapper in `api/` (the anti-corruption layer) and allowing `api → domain/model` (types only) keeps `domain/` portable and stable across schema regens — the highest-value boundary this migration buys.

**Alternatives rejected**: `domain/mappers/` holding mappers that import generated types (Option B) — rejected because it abandons the "no generated types in `domain/`" boundary that motivates the migration.

**Consequence**: `branch.mappers.ts` (which today co-locates domain types + mapping fns + generated imports) splits: types → `domain/model/`, mapping fns → `api/`.

## D4 — `domain/model` as a pure leaf

**Decision**: `domain/model` imports nothing from `api/`, `domain/rules`, `domain/use-cases`, or `ui/`.

**Rationale**: With `domain → api` (D1) and `api → domain/model` (D3), a single stray import from `model` into `api` creates a real dependency cycle. Keeping `model` a pure leaf guarantees the graph stays acyclic.

## D5 — `domain/` split policy

**Decision**: Split `domain/` into `model/`/`rules/`/`use-cases/` only when it has >4 files; never create a folder for <2 files. Classify: orchestration/I-O → `use-cases/`; pure/no-I-O → `rules/`; type declarations → `model/`.

**Rationale**: Honors the spec's own "no empty folders / split only when hard to scan." `config` (2 files) and `role-manager` (2 files) stay flat; `branches` (11), `proposed-changes` (8), `schema` (8) split.

**Alternatives rejected**: Uniform split for every entity — rejected as producing 1-file folders, which the spec forbids.

## D6 — Enforcement tooling (Tier 1 now, Tier 2 deferred)

**Decision**: Tier 1 — Biome `overrides` + `noRestrictedImports` on migrated entities' `domain/` globs, forbidding `@apollo/client`, `@tanstack/react-query`, `react`, browser storage, toast libs, and `**/graphql/generated`. No new dependency. Tier 2 — dependency-cruiser for directional folder rules — deferred pending new-dependency sign-off.

**Rationale**: Biome 2.4.16 supports per-glob `overrides` with `noRestrictedImports` (verified in `package.json`; `overrides`/`includes` already present in `biome.jsonc`). This expresses every forbidden *library/type* edge with zero new dependencies. Directional *folder* rules (model-as-leaf, `api → domain/model` only) are not expressible in Biome and require dependency-cruiser — a new dependency gated by AGENTS.md, so deferred and enforced by review meanwhile.

**Verification notes for implementation**: `noRestrictedImports` in Biome 2.x lives under the `nursery`/`style` group depending on point release; confirm the exact group key against `2.4.16` at first-PR time and pin it. Use `patterns` matching `**/graphql/generated/**` and package names.

## D7 — Guard cadence (incremental glob)

**Decision**: The Biome override lists only already-migrated entities' `domain/` paths, growing one glob line per PR.

**Rationale**: Enabling the rule globally on day one would fail the 8 existing generated-type leaks and every unmigrated entity at once. Incremental scoping means the guard is real from PR 1 and only ever passes. Chosen over "fix-then-guard" (front-loads 8 fixes into one PR) and "guard-last" (zero enforcement during the risky window).

## D8 — Rollout order & granularity

**Decision**: One entity per PR, each green on all four commands before the next. Order: `role-manager` → `branches` (+ update `entities-structure.md`) → remaining ~20 → `nodes/` last as its own multi-PR sub-epic.

**Rationale**: `role-manager` (2 files) validates mechanics + guard with near-zero blast radius. `branches` exercises every hard case (type/mapper split, generated-leak fix, >4 split) and becomes the documented reference. `nodes/` is a ~260-file namespace, not one entity, and holds in-flight sort work — migrated last, per sub-module, to avoid collision. Per-entity PRs keep diffs reviewable and bisectable.

**Alternatives rejected**: Big-bang single PR across 24 entities — un-reviewable, one bad import blocks everything.

## D9 — Branching / ticket

**Decision**: Planning branch `frontend-entities-arch-migration` created from HEAD without a Jira/JPD ticket by explicit requester override of the mandatory speckit gate. Working tree's in-flight sort work left untouched.

**Rationale**: Requester chose to proceed without a ticket. Branching from HEAD (not `stable`) was the only non-destructive option given uncommitted, conflicting working-tree changes (`qsp.ts` differs on `stable`). Implementation PRs branch fresh from trunk regardless, so the planning-branch base is immaterial.
