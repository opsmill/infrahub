# Implementation Plan: Custom prefix mask for from-pool allocation

**Branch**: `from-pool-prefix-mask-infp-362` | **Date**: 2026-06-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/ifc-1869-from-pool-prefix-mask/spec.md`

## Summary

Add an optional "Prefix length" control to the from-pool flow, shown only after a pool is selected and only for **IP address pools** (`CoreIPAddressPool`). The control is a small shared component (`PoolPrefixLengthInput`) rendered **inside `PoolSelect`** itself, so all three host fields that use `PoolSelect` (`input.field.tsx`, `regular-relationship.field.tsx`, `relationship-hierarchical.field.tsx`) inherit it without per-host wiring (FR-011). The number-pool selector (`PoolSelector`) is untouched. Empty = pool default (unchanged); the default is shown as the input placeholder. The value is carried on `PoolValue.from_pool.prefixlen` and emitted by the mutation builders **only when the user overrides** (a shared `buildFromPoolPayload` helper drops an absent/`undefined` length so it is never serialized). The IP-address path works through the existing inline `IPAddressPoolInput.prefixlen` → `get_resource`; **no GraphQL schema change was needed.**

> **As-built deltas from the original plan** (see Implementation slices + spec Assumptions):
> - **IP prefix pools deferred** — their inline input uses `size`, not `prefixlen`; the control is hidden for them. Slice B below was not implemented.
> - **Conflict guard (FR-014)** added to `CoreIPAddressPool.get_resource`: an explicit `prefixlen` conflicting with an existing reservation raises an inline error instead of silently reusing it. This replaced the planned "unsatisfiable-length" framing and two heavier alternatives (release-on-re-point; reserved-resource lookup endpoint) — both rejected/deferred.
> - **Verification was manual** via the live preview, not new Playwright specs (the E2E tasks remain open).

## Technical Context

**Language/Version**: TypeScript 5.9 / React 19.2 (frontend); Python 3.14 (backend)
**Primary Dependencies**: Vite 8, Tailwind 4.2, react-hook-form, Apollo Client, TanStack Query (FE); FastAPI, Graphene GraphQL (BE)
**Storage**: Neo4j (via existing pool allocation; no schema/storage change)
**Testing**: Vitest + Playwright (FE); pytest functional/component (BE)
**Target Platform**: Web app (Vite dev :8080 → API :8000)
**Project Type**: Web application (frontend + backend)
**Performance Goals**: N/A (single optional form control; no new hot paths)
**Constraints**: Must not regress the existing one-step pool default flow; GraphQL input changes require maintainer sign-off; do not edit generated files; do not commit the ~24 unrelated working-tree files.
**Scale/Scope**: One shared control + type/mutation threading (FE); ≤3 small edits + tests (BE).

## Constitution Check

*GATE: must pass before Phase 0 and re-checked after Phase 1.*

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | PASS | No data-schema change. Generated FE/BE files regenerated, never hand-edited (GraphQL types via codegen). |
| II. Branch-Safe by Default | PASS | Allocation runs inside the existing mutation transaction; no new queries. Merge behaviour unchanged (no new node/edge types). |
| III. Type Safety & Explicit Contracts | PASS | `PoolValue.prefixlen?: number`; no `any`. GraphQL input field typed `Int`. Contracts defined before code ([contracts/](./contracts/)). |
| IV. Test Discipline | PASS | FE unit (gating/validation/mutation emission), E2E (extend two IPAM specs), BE functional tests (address works; prefix/attribute after change; unsatisfiable-length error). |
| V. Query Performance & Efficiency | PASS | One additive field (`default_prefix_length`) on an existing pool list query; no N+1. |
| VI. Security & Input Boundaries | PASS | Length validated client-side and authoritatively by the pool allocator server-side; no string interpolation; authn/authz unchanged. |
| VII. Simplicity & Maintainability | PASS | Reuse `Input`+`Row`; one small composite (`PoolPrefixLengthInput`) shared by 3 callers (justified in Complexity Tracking); `prefixlen` added only where needed (YAGNI). |

### Frontend principles

| Principle | Status | Notes |
|---|---|---|
| Reuse Before Reinvent | PASS (justified) | Reuse `Input`, `Row`, `PoolSelect`. One small new shared component `PoolPrefixLengthInput` serves three callers (the IP host fields) — meets constitution VII's "two existing callers" bar; see Complexity Tracking. |
| Single State Owner | PASS | Value owned by the `useForm` field via existing `onChange(PoolValue)`. No mirrored `useState`. |
| Backend Authoritative | PASS | Pool default and final allocation owned by backend; UI only hints the default (fetched) and forwards an optional override. |
| Component Contracts Designed for All Callers | PASS | `PoolPrefixLengthInput` has one prop API (`poolKind`, `defaultPrefixLength`, `addressFamily`, `value`, `onChange`) consumed by all three IP host fields (`input.field.tsx`, `regular-relationship.field.tsx`, `relationship-hierarchical.field.tsx`); no synthetic-prop hacks ([contract](./contracts/frontend-pool-selector.md)). |
| E2E Happy Path | PASS | Extend `ip-prefix-create-with-pool.spec.ts` and `ip-address-create-with-pool.spec.ts` with full save-and-verify flow. |

**Gate result: PASS.** One Ask-First item (GraphQL inline input change for prefix/attribute paths) is flagged, not a violation. No Complexity Tracking entries required.

### Shared Components Inventory

| Need | Reusing | Source |
|---|---|---|
| IP pool picker (combobox; builds `PoolValue`; gated to IP pools) | `PoolSelect` | `shared/components/inputs/pool-select.tsx` |
| IP attribute host (`prefix`/`address`) — renders PoolSelect + pool state | `InputField` | `shared/components/form/fields/input.field.tsx` |
| IP relationship host — renders PoolSelect + pool state | `RegularRelationshipField` | `shared/components/form/fields/relationships/regular-relationship.field.tsx` |
| IP hierarchical-relationship host — renders PoolSelect + pool state | `RelationshipHierarchicalField` | `shared/components/form/fields/relationships/relationship-hierarchical.field.tsx` |
| **Prefix-length control (building new)** | `PoolPrefixLengthInput` | `shared/components/form/pool-prefix-length-input.tsx` (new) — see Complexity Tracking |
| Numeric input | `Input` | `shared/components/ui/input.tsx` |
| Inline layout for `/` adornment + input | `Row` | `shared/components/container/` |
| From-pool value type | `PoolValue` (+ optional `prefixlen`) | `shared/components/form/type.ts` |
| Mutation emission | `getCreateMutationFromFormData` / `getUpdateMutationFromFormData` | `shared/components/form/utils/mutations/` |
| Pool kind gating | `IP_ADDRESS_POOL` / `IP_PREFIX_POOL` consts | `entities/resource-manager/constants.ts` |
| Pool list query (add `default_prefix_length`) | `generateRelationshipListQuery` | `entities/nodes/relationships/api/generate-relationship-list.query.ts` |

**The IP picker is `PoolSelect`, rendered by three host fields** (`input.field.tsx` for the `prefix`/`address` attribute, `regular-relationship.field.tsx`, and `relationship-hierarchical.field.tsx`). `PoolSelector` (`form/pool-selector.tsx`) is the **number-pool** selector (`pools: NumberPool[]`, trigger `number-pool-button`) and is intentionally untouched — FR-003 excludes non-IP pools. To satisfy FR-011 without duplicating logic across the three host fields, the prefix-length control is a small new shared component (`PoolPrefixLengthInput`) rendered by each host beside its `PoolSelect`. This is the one "(building new)" row; see Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/ifc-1869-from-pool-prefix-mask/
├── plan.md            # this file
├── spec.md            # feature spec (+ Clarifications)
├── research.md        # Phase 0 — backend path audit, decisions
├── data-model.md      # Phase 1 — PoolValue + validation + lifecycle
├── contracts/         # Phase 1 — GraphQL inline input + FE component contracts
│   ├── graphql-inline-from-pool.md
│   └── frontend-pool-selector.md
├── quickstart.md      # Phase 1 — manual + automated verification
├── checklists/requirements.md
└── tasks.md           # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (as built)

```text
frontend/app/src/shared/components/form/
├── type.ts                                       # PoolValue.from_pool.prefixlen?
├── pool-prefix-length-input.tsx                  # NEW control: props value/placeholder/invalid/onChange
└── utils/mutations/
    ├── buildFromPoolMutationValue.ts             # NEW helper: drop absent/undefined prefixlen
    ├── getCreateMutationFromFormData.ts          # emit via buildFromPoolPayload
    └── getUpdateMutationFromFormData.ts          # emit via buildFromPoolPayload
frontend/app/src/shared/components/inputs/pool-select.tsx   # renders PoolPrefixLengthInput (gated CoreIPAddressPool); placeholder from default; emits prefixlen only on override
frontend/app/src/shared/components/ui/form.tsx              # findErrorMessage (nested errors); FormInput flags own error only; FormMessage surfaces child error
frontend/app/src/entities/nodes/relationships/api/generate-relationship-list.query.ts  # fetch default_prefix_length for CoreIPAddressPool only
frontend/app/src/entities/resource-manager/constants.ts     # MIN/MAX_PREFIX_LENGTH (1–128)
# Tests: pool-prefix-length-input.test.tsx, ui/form.test.tsx (findErrorMessage), mutations/*.test.ts
# NOTE: pool-selector.tsx / number.field.tsx (number pools) NOT changed.
# NOTE: the 3 host fields render <PoolSelect/> unchanged — the control lives inside PoolSelect, so no per-host wiring.

backend/infrahub/core/node/resource_manager/ip_address_pool.py   # FR-014 conflict guard in get_resource
backend/tests/component/core/resource_manager/test_ipaddress_pool.py  # conflict + idempotency test
changelog/+ifc-1869-from-pool-prefix-length.added.md             # towncrier fragment
# NOT changed (deferred): graphql/types/attribute.py, core/node/__init__.py, ip_prefix_pool.py, getFormFieldFrom*.ts
```

**Structure Decision**: Web-application layout. The control lives once inside the shared `PoolSelect`, gated to `CoreIPAddressPool`, so all three host fields that already render `PoolSelect` inherit it with no per-host wiring (FR-011). The number-pool selector (`PoolSelector`) is untouched. The only backend change is the FR-014 conflict guard; no GraphQL input change shipped.

## Implementation slices (as built)

1. **Slice A (P1, frontend) — DONE**: `PoolValue.from_pool.prefixlen`; build `PoolPrefixLengthInput` and render it inside `PoolSelect`, gated to `CoreIPAddressPool`; placeholder = pool default; range validation (1–128) via a nested RHF field; mutation emission via `buildFromPoolPayload` (override-only). Fetch `default_prefix_length` for address pools in the relationship list query. FE unit tests.
2. **Slice B (FR-014 backend guard) — DONE**: in `CoreIPAddressPool.get_resource`, reject an explicit `prefixlen` that conflicts with an existing reservation (idempotent otherwise). Component test. No GraphQL change.
3. **Slice C (validation/error surfacing) — DONE**: inline range validation + the FR-014 conflict error surfaced on the form via `findErrorMessage`/`FormMessage`; changelog fragment.
4. **Deferred — IP prefix pools & attribute path**: would add `prefixlen`/thread `size` to `IPPrefixPoolInput` and the IP attribute input (Ask-First GraphQL change) plus backend threading. **Not implemented**; the UI hides the control for prefix pools. Tracked as a follow-up.
5. **Open — Playwright E2E**: the address/prefix create-with-pool specs were not extended; the feature was verified manually in the live preview. Add E2E before relying on it in CI.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| New shared component `PoolPrefixLengthInput` | The prefix-length control must render in the three host fields that use `PoolSelect` (`input.field.tsx`, `regular-relationship.field.tsx`, `relationship-hierarchical.field.tsx`) with identical gating/validation/value semantics. A shared component serves all three (≥2 callers, satisfying constitution VII). | Inlining the control three times was rejected: it duplicates the gating + validation + `/`-adornment logic and risks the host fields drifting (a real FR-011 consistency risk). Extending only one host was rejected because it leaves the other IP entry points without the feature. |
