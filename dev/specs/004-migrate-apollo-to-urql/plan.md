# Implementation Plan: Migrate GraphQL Transport from Apollo Client to urql

**Branch**: `migrate-apollo-to-urql-infp-563` | **Date**: 2026-07-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-migrate-apollo-to-urql/spec.md`

## Summary

Replace the frontend's transport-only `@apollo/client` with `@urql/core` to cut ~40 KB gzipped from the bundle while preserving every observable transport behavior. Apollo is used imperatively (95 `query`/`mutate` call sites fronted by TanStack Query; no Apollo hooks or cache). The approach is an **adapter that preserves the existing `graphqlClient.query/mutate` interface and `{ data, errors }` result shape**, so no call-site logic changes. The four cross-cutting Apollo links map to urql exchanges: `authExchange` (auth + token-refresh-and-replay, FR-006), `mapExchange` (priority header + error routing), and the native `fetchExchange` (per-operation URL + multipart uploads). The one behavior without a 1:1 urql equivalent — Client-level in-flight dedup — is gated by a Phase-0 spike.

## Technical Context

**Language/Version**: TypeScript 5.9, React 19.2

**Primary Dependencies**: Remove `@apollo/client@3.13.8`, `apollo-upload-client@18.0.1`, `@types/apollo-upload-client`. Add `@urql/core@^6`, `@urql/exchange-auth@^3`. Keep `graphql@^16` (required by `gql.tada`), `gql.tada`, `json-to-graphql-query`, `@tanstack/react-query`.

**Storage**: N/A (frontend transport only; TanStack Query remains the sole client cache)

**Testing**: Vitest (browser mode) for unit/component, Playwright for E2E, `betterer` for TS-regression, Biome for format/lint, `knip` for unused deps

**Target Platform**: Browser (SPA served by Vite build)

**Project Type**: Web application frontend (`frontend/app/`)

**Performance Goals**: Production JS bundle gzip size decreases (SC-001, direction-only). No per-request latency regression.

**Constraints**: Zero observable behavioral change (SC-004). No GraphQL-layer caching/dedup introduced by this layer beyond urql's unavoidable Client-level dedup (see Constitution Check / research Decision 3). No backend, schema, or CI/CD changes.

**Scale/Scope**: 1 client module rewritten; 95 imperative call sites unchanged; ~29 `gql` import-path edits; 3 test files touched (1 rewrite, 2 wrapper swaps); 1 provider removal in `app.tsx`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Assessment |
|---|---|
| **I. Schema-Driven Integrity** | N/A — no schema or generated-file changes. Generated GraphQL types (`gql.tada`) are consumed unchanged. |
| **II. Branch-Safe by Default** | **Relevant.** Branch/date are carried per-operation via `context` → URL. The **dedup gap (research Decision 3)** is precisely a branch-safety risk: cross-branch concurrent identical ops could collide. Gated by a mandatory spike + mitigation before ship. |
| **III. Type Safety & Explicit Contracts** | **Pass, with a rule.** Adapter is generic over `TypedDocumentNode` to preserve `gql.tada` inference. No new `any`/`as`/`!`. The 29 `gql(string)` sites are already untyped (parity, not regression). |
| **IV. Test Discipline** | **Pass.** Rewrite the Apollo-coupled transport test against urql exchanges; add explicit FR-006 coverage (SC-003); existing browser + E2E suites must pass unchanged. |
| **V. Query Performance & Efficiency** | N/A (backend Cypher-focused). Frontend: no N+1 introduced; caching authority unchanged. |
| **VI. Security & Input Boundaries** | **Pass.** New deps reviewed and justified (bundle reduction; `@urql/core` is a maintained, smaller transport). Token handling preserved; no secrets committed. **New-dependency governance gate → maintainer sign-off required.** |
| **VII. Simplicity & Maintainability** | **Pass — net simplification.** Removes 3 deps for 2; replaces the hand-rolled refresh Observable with idiomatic `authExchange`. The adapter is a single abstraction serving 95 existing callers (well past the two-caller bar). |

**Quality gates**: Formatting (Biome), Lint (Biome), TS strict (`betterer`), Tests (Vitest + Playwright), **Changelog** — a `changelog/+<slug>.housekeeping.md` fragment is required (dependency swap; not user-facing behavior).

**Result**: No unjustified violations. Complexity Tracking table not required. One gating risk (branch-safe dedup) tracked as a Phase-0 spike, not a violation.

## Project Structure

### Documentation (this feature)

```text
specs/004-migrate-apollo-to-urql/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (transport contracts)
├── quickstart.md        # Phase 1 output (validation guide)
├── contracts/
│   └── transport-client.md   # Phase 1 output (preserved interface contract)
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
frontend/app/
├── src/
│   ├── shared/api/graphql/
│   │   ├── graphqlClient.ts          # NEW: urql-backed client + adapter (replaces graphqlClientApollo.tsx)
│   │   ├── graphqlClient.test.ts     # REWRITE: exchange-level tests + FR-006 coverage
│   │   ├── exchanges/                # NEW (optional): auth / priority+error exchange modules
│   │   ├── gql.ts                    # NEW: local `gql` re-export from @urql/core (for the 29 dynamic-string sites)
│   │   ├── fragments.ts              # unchanged
│   │   └── utils.ts                  # unchanged (jsonToGraphQLQuery request builders)
│   ├── entities/**/api/*-from-api.ts # UNCHANGED logic; only `gql` import path edits where applicable
│   ├── app/app.tsx                   # EDIT: remove <ApolloProvider> wrapper
│   └── shared/components/inputs/
│       ├── enum.test.tsx             # EDIT: drop ApolloProvider wrapper
│       └── dropdown.test.tsx         # EDIT: drop ApolloProvider wrapper
├── package.json                      # EDIT: dependency swap
└── (changelog fragment at repo-root changelog/)
```

**Structure Decision**: Single frontend app (`frontend/app/`). All changes are localized to `src/shared/api/graphql/` plus mechanical `gql` import edits, one provider removal, and two test-wrapper swaps. The preserved adapter interface (`contracts/transport-client.md`) keeps the 95 call sites and their consuming use-cases untouched.

## Phase 0 — Research

Complete. See [research.md](./research.md). All three spec assumptions resolved (one superseded: multipart is native). One new gating risk surfaced: **Client-level in-flight dedup** (Decision 3) — requires a spike before ship.

## Phase 1 — Design & Contracts

Complete:
- [data-model.md](./data-model.md) — preserved transport contracts (client interface, context keys, behavior chain, error routing, `gql` producers).
- [contracts/transport-client.md](./contracts/transport-client.md) — the interface + behavioral contract that is the FR-008 acceptance surface.
- [quickstart.md](./quickstart.md) — runnable validation (bundle baseline, gates, FR-006 tests, dedup spike, manual parity, E2E).
- Agent context: no `<!-- SPECKIT ... -->` markers exist in `CLAUDE.md`; the optional `after_plan` agent-context hook may add them. No manual edit made.

## Post-Design Constitution Re-Check

No new violations introduced by the design. Branch-safety (II) remains the single tracked risk, correctly gated by the Phase-0 dedup spike in `quickstart.md` step 4. Type-safety (III) is preserved by the generic adapter. Ready for `/speckit-tasks`.
