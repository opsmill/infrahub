# Implementation Plan: Resource-pool form fields — value-or-pool tabs and target-type override

**Branch**: `ple-ifc-2764-pool-kind-override` | **Date**: 2026-09-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `dev/specs/ifc-2764-pool-field-tabs/spec.md`

## Summary

FR-001 through FR-022 are **already implemented and green on this branch**; this plan covers only
what remains: the availability harness (FR-023), the unverified attribute half of FR-017, the
shared e2e/documentation helpers (FR-024), and the 71-commit base drift that gates all of it.

The delivered work is catalogued in [research.md](./research.md) §1 so the plan does not re-derive
it. Current gate: 193 vitest files / 1371 tests, `biome ci`, `knip`, `betterer` at 186, backend
ruff/ty/mypy clean plus 161 + 49 component tests.

## Technical Context

**Language/Version**: TypeScript 5.x (React 19, React Compiler enabled) · Python 3.12 (backend)

**Primary Dependencies**: react-hook-form, jotai, TanStack Query, Radix (`@radix-ui/react-tabs`),
Tailwind v4; graphene and pydantic on the backend

**Storage**: Neo4j via Infrahub's own graph layer — untouched by the remaining work

**Testing**: vitest in browser mode (Playwright chromium) for the frontend; pytest with
testcontainers for backend component tests; pytest-playwright for e2e

**Target Platform**: Infrahub web app + API server, run locally via `invoke demo.start`

**Project Type**: Web application — `frontend/app` + `backend/infrahub` in one repository

**Performance Goals**: N/A. The remaining work is schema fixtures, tests and documentation; no
runtime path changes.

**Constraints**: React Compiler forbids manual memoization; no `as`/non-null/`any`; `Row`/`Col`
primitives; semantic theme tokens only; `betterer` must stay at 186.

**Scale/Scope**: 5 pool-backed form fields, 3 gating layers, ~24 availability-matrix rows, 7
missing schema shapes, 8 e2e call sites across ~10 files.

## Constitution Check

`.specify/memory/constitution.md` **does not exist** in this repository, so there are no
project-level principles to gate against. The equivalent constraints live in `dev/guidelines/`
and `dev/knowledge/`; the delivered work follows them and the tasks restate them as acceptance
conditions. **No gate violations.**

## Project Structure

### Documentation (this feature)

```
dev/specs/ifc-2764-pool-field-tabs/
├── spec.md              # requirements (updated to match delivered behaviour)
├── plan.md              # this file
├── research.md          # what is already built, and the open decisions
├── data-model.md        # the harness schema shapes and seed data
├── plan-quickstart.md   # how to validate the remaining work
├── quickstart.md        # HAND-WRITTEN user-facing trial guide — do not regenerate
└── checklists/
    └── requirements.md
```

`quickstart.md` is deliberately **not** the generated artifact: it is a plain-language trial guide
with 12 walkable cases, written for a human exercising the feature. The generated validation guide
is `plan-quickstart.md`.

### Source Code (repository root)

```
frontend/app/src/shared/components/
├── ui/tabs.tsx                          # variants: underline | field
├── form/field-tabs.tsx                  # FieldTabs* wrappers, pins the `field` variant
├── form/pool-allocation-panel.tsx       # the shared "From pool" panel
├── form/pool-kind-select.tsx            # the type override control
├── form/pool-prefix-length-input.tsx    # the mask override control
├── form/fields/{number,input}.field.tsx
├── form/fields/relationships/{generic,regular,relationship-hierarchical}-*.tsx
├── form/utils/getFieldDefaultValue.ts   # ← FR-017 attribute-side suspect
└── inputs/pool-select.tsx               # PoolCombobox / PoolPrefixLengthField / PoolKindOverrideField

backend/infrahub/core/node/resource_manager/
├── kind_validation.py                   # validate_allocated_kind
└── reservation.py                       # validate_reserved_prefix_length, validate_reserved_kind

models/examples/
├── ipam_kind_override.yml               # ← harness shapes are added here
└── ipam_kind_override_data.py           # ← harness seed data is added here

tests/e2e/helpers.py                     # ← select_pool(), shared by 8 call sites
```

**Structure Decision**: Existing web-application layout; no new top-level structure. The harness
extends the two `models/examples/` files this branch already introduced rather than adding a
third, so the trial guide keeps a single pair of load commands.

## Phase 0 — Research

See [research.md](./research.md). Four decisions were open; all are resolved there:

1. **Rebase before or after the harness** → **before**. The drift touches the form files this
   branch rewrote; resolving once, now, is cheaper than resolving twice and re-verifying the UI.
2. **One harness schema file or two** → **extend the existing one**, so the trial guide keeps one
   `infrahubctl schema load` line.
3. **Whether `getFieldDefaultValue.ts` is genuinely defective** → **unknown until reachable**;
   planned as a spike gated on the attribute schema shape, with both outcomes accounted for.
4. **How to reshape `select_pool()`** → **absorb the tab click into the helper**, leaving all 8
   call sites untouched.

## Phase 1 — Design

- [data-model.md](./data-model.md) — the 7 missing schema shapes, the seed data, and which
  matrix row each unlocks.
- **Contracts**: none. The GraphQL surface change (`address_type` on `IPAddressPoolInput`) is
  already delivered and present in `schema/schema.graphql`; the remaining work adds fixtures,
  tests and documentation and exposes no new interface.
- [plan-quickstart.md](./plan-quickstart.md) — how to validate the remaining work.

**Agent context update — deliberately skipped.** The workflow's step to rewrite the managed block
in `CLAUDE.md` was not run: this repository's `CLAUDE.md` delegates to `AGENTS.md`, which is
already complete, and the maintainer has asked that speckit runs leave it alone.

## Complexity Tracking

| Item | Why it is not simpler | Accepted because |
|---|---|---|
| FR-009 held as a widening rather than exactly | Converging the two pool channels made the gate a union. Gating on the from-pool relationship alone would have removed the pool from every plain node form, because those relationships exist only on object-template schemas. | Availability only ever widens, in one case (template schema, zero matching pools → empty list). IP fields already behave this way. Recorded in spec.md → Deviations. |
| A pre-existing form defect underneath FR-012/FR-021 | The shared form's mount-time `reset(defaultValues)` discards react-hook-form's field registry, so a later programmatic write updates values without notifying the control. | Submitted data is read from the values, so FR-021 holds and was verified end-to-end. Fixing the shared form belongs to its own ticket. |
| Seven schema shapes for one requirement | The availability rules span three independent gating layers; most rows are unreachable without a purpose-built shape. | It is the only way to satisfy FR-023's "reachable by hand" clause rather than asserting rules nobody can see. |
