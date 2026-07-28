---

description: "Task list for Apollo Client → urql transport migration"
---

# Tasks: Migrate GraphQL Transport from Apollo Client to urql

**Input**: Design documents from `/specs/004-migrate-apollo-to-urql/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/transport-client.md, quickstart.md

**Tests**: INCLUDED — SC-003 requires explicit FR-006 (token-refresh) coverage, and Constitution IV mandates test discipline. The Apollo-coupled transport test is rewritten against urql.

**Organization**: One user story (US1 — behavior-identical transport swap). A GraphQL transport cannot be partially swapped, so US1 is the whole feature; phases sequence setup → gating prerequisites → the swap → validation.

**Paths**: all under `frontend/app/` unless noted. Repo root = `/Users/bilal/opsmill/infrahub`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 (only story). Setup / Foundational / Polish tasks carry no story label.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependency swap and baseline capture.

- [x] T001 In `frontend/app/package.json`, remove `@apollo/client`, `apollo-upload-client`, and (devDependencies) `@types/apollo-upload-client`; add `@urql/core@^6` and `@urql/exchange-auth@^3`; keep `graphql@^16`. Run `pnpm install` from `frontend/app/` and commit the updated lockfile.
- [x] T002 [P] Capture the pre-migration bundle baseline: from `develop`, run `cd frontend/app && pnpm build`, record the gzipped size of the main JS chunk(s) into `specs/004-migrate-apollo-to-urql/bundle-baseline.md` (SC-001 comparison anchor). Do this from a clean `develop` checkout before T001's changes land, or from a separate worktree.

**Checkpoint**: urql deps installed; bundle baseline recorded.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Resolve the one behavioral risk and stand up shared scaffolding before the client is built.

**⚠️ CRITICAL**: T003 gates the whole migration — do not build the client until its outcome is known.

- [x] T003 **Dedup spike (GATING — Constitution II branch-safety)**: write a throwaway check firing two concurrent `Client.query` calls with identical document + variables but different `context.url` (branch A vs branch B), and assert each response reflects its own branch. Record the result and the chosen mitigation (accept / fold branch discriminator into the operation key / per-branch client) in `specs/004-migrate-apollo-to-urql/research.md` under Decision 3. See `quickstart.md` step 4.
- [x] T004 [P] Create `frontend/app/src/shared/api/graphql/gql.ts` re-exporting `gql` from `@urql/core` (used by the 29 dynamic-string sites in T011). Include a one-line comment explaining why it exists (stable local seam for `gql(jsonToGraphQLQuery(...))` call sites).

**Checkpoint**: Dedup behavior understood + mitigation decided; local `gql` seam ready.

---

## Phase 3: User Story 1 — Behavior-identical transport swap (Priority: P1) 🎯 MVP

**Goal**: Replace Apollo with a urql-backed `graphqlClient` whose `query`/`mutate` interface, result shape, headers, endpoint resolution, error routing, token-refresh, and uploads are indistinguishable from today — with a smaller bundle.

**Independent Test**: Full unit/component/E2E suites pass unchanged; manual parity across browse/CRUD/upload/token-expiry/branch-diff; bundle smaller than the T002 baseline. See `contracts/transport-client.md` assertions 1–8.

### Tests for User Story 1 (write first, ensure they FAIL against a stub) ⚠️

- [x] T005 [P] [US1] Rewrite `frontend/app/src/shared/api/graphql/graphqlClient.test.ts` (replacing `graphqlClientApollo.test.ts`) driving urql exchanges directly: assert `X-Priority` defaults to `high` and becomes `low` when `context.priority === "low"` (FR-002), and `Authorization: Bearer <token>` present when a token exists / absent otherwise (FR-001). Covers contract assertion 1.
- [x] T006 [P] [US1] In the same test file, add FR-006 token-refresh coverage (SC-003), four cases: (a) `TOKEN_EXPIRED` → single refresh + successful replay; (b) persistent `TOKEN_EXPIRED` after replay → `redirectToLogin()`; (c) refresh returns no `access_token` → redirect; (d) refresh throws → redirect. Assert exactly one refresh per operation and no hung promise. Covers contract assertion 6.
- [x] T007 [P] [US1] Add result-shape tests: success → `{ data, errors: undefined }` (NOT `[]`); GraphQL error with partial data → both `data` and `errors` populated (FR-007). Covers contract assertions 3–4.

### Implementation for User Story 1

- [x] T008 [US1] Create the header+error exchange at `frontend/app/src/shared/api/graphql/exchanges/priority-error-exchange.ts` using `mapExchange`: `onOperation` stamps `X-Priority` via `resolvePriority(operation.context.priority)` into `fetchOptions.headers` (FR-002); `onError` routes catalogue codes via `parseCatalogueError` — `AUTHENTICATION_REQUIRED` → `redirectToLogin()`, `PERMISSION_DENIED` → silent, `UNDEFINED_ERROR` → toast + dev-only console warning, default → `context.processErrorMessage(message)` if present else toast (FR-005).
- [x] T009 [US1] Create the auth exchange at `frontend/app/src/shared/api/graphql/exchanges/auth-exchange.ts` using `@urql/exchange-auth`'s `authExchange`: `addAuthToOperation` appends the bearer token from `getAccessToken()` (FR-001); `didAuthError` returns true on `TOKEN_EXPIRED`; `refreshAuth` calls `queryClient.fetchQuery(refreshAccessTokenQueryOptions())`, stores the new token, and on no-token / throw / unchanged-token-after-retry performs `redirectToLogin()` (FR-006 one-shot guard via closure token comparison).
- [x] T010 [US1] Create `frontend/app/src/shared/api/graphql/graphqlClient.ts` (replacing `graphqlClientApollo.tsx`): instantiate `@urql/core` `Client` with `exchanges: [priorityErrorExchange, authExchange, fetchExchange]` (no `cacheExchange`), plus any mitigation from T003. Export a default adapter exposing `query({query, variables?, context?, fetchPolicy?})` and `mutate({mutation, variables?, context?})`, each: computing per-op `url` = `CONFIG.GRAPHQL_URL(context.branch, context.date)` with `requestPolicy: 'network-only'` (FR-003), calling `.toPromise()`, and normalizing to `{ data, errors }` per `contracts/transport-client.md` (errors `undefined` on success, partial data retained, network error → no data). Generic over `TypedDocumentNode` to preserve `gql.tada` inference (Constitution III). Uploads work natively via `fetchExchange` (FR-004). Make T005–T007 pass.
- [x] T011 [US1] Update the 29 files importing `gql` from `@apollo/client` (the `gql(jsonToGraphQLQuery(...))` sites in `src/entities/**/api/*-from-api.ts`) to import `gql` from `@/shared/api/graphql/gql` (T004). Mechanical codemod; no query-body changes. The 65 `gql.tada` `graphql()` files are untouched.
- [x] T012 [US1] Update all default-import sites of the client from `@/shared/api/graphql/graphqlClientApollo` to `@/shared/api/graphql/graphqlClient` (mechanical find/replace across `src/`, ~63 files). Delete `graphqlClientApollo.tsx`.
- [x] T013 [US1] Remove the `<ApolloProvider>` wrapper (and its import) from `frontend/app/src/app/app.tsx`; render children directly (imperative-only usage needs no provider).
- [x] T014 [P] [US1] In `frontend/app/src/shared/components/inputs/enum.test.tsx` and `dropdown.test.tsx`, remove the `ApolloProvider` wrapper and its import; render the UI without a provider.

**Implementation note (deviation from T008–T010 file layout)**: because usage is
fully imperative, the priority-header injection and catalogue error-routing were
folded into the adapter (`graphqlClient.tsx`) rather than a separate
`exchanges/priority-error-exchange.ts` — `buildOperationContext` stamps
`X-Priority`, and the exported `handleGraphQLErrors` runs after every
query/mutate (where `processErrorMessage` is directly in hand). Only the
`authExchange` (token refresh) needs to live in the exchange chain; it is defined
inline via `authConfigInitializer`. The result type also mirrors Apollo's
`ApolloQueryResult` exactly — non-optional `data` plus both `error` (singular)
and `errors` (array) — because callers consume both shapes. A branch-aware
request key (`keyedQueryRequest`) was added per the T003 spike outcome.

**Checkpoint**: urql client live behind the preserved interface; all Apollo imports gone; transport tests green.

---

## Phase 4: Polish & Cross-Cutting Concerns

- [x] T015 [P] Add changelog fragment `changelog/+migrate-apollo-to-urql.housekeeping.md` describing the transport swap and bundle reduction (Constitution changelog gate).
- [x] T016 Run static gates from `frontend/app/`: `pnpm exec biome ci .`, `pnpm knip` (confirms no leftover apollo deps/exports), `pnpm exec betterer ci`. Fix any fallout. (SC-002)
- [x] T017 Run `cd frontend/app && pnpm test` — unit/component suites green, including T005–T007. (SC-002, SC-003)
- [ ] T018 Run `cd frontend/app && pnpm test:e2e` — existing Playwright suite green, with attention to object create/update (file upload) and branch/diff flows. (SC-002, SC-004)
- [x] T019 Bundle comparison: `cd frontend/app && pnpm build`; compare the gzipped main-chunk size against `bundle-baseline.md` (T002) and record the delta. Confirm a decrease. (SC-001)
- [x] T020 [P] Verify no stray Apollo references: `grep -rn "@apollo/client\|apollo-upload-client" frontend/app/src` and `grep -n apollo frontend/app/package.json` both return nothing. (SC-005)
- [ ] T021 Manual parity pass per `quickstart.md` step 5 against a running backend: authenticated browse, object CRUD, file upload, forced token-expiry recovery, branch diff/compare. Confirm indistinguishable from the `develop` build. (SC-004)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 first; T002 baseline is independent ([P]) and best captured from a clean `develop`.
- **Foundational (Phase 2)**: T003 (spike) gates Phase 3 — its mitigation feeds T010. T004 is independent ([P]).
- **User Story 1 (Phase 3)**: depends on Phase 2. Tests (T005–T007) before implementation (T008–T014).
- **Polish (Phase 4)**: depends on Phase 3 complete.

### Within User Story 1

- T005–T007 (tests) written first, fail against a stub.
- T008 + T009 (exchanges) before T010 (client wires them together).
- T010 before T011/T012 (import updates depend on the new modules existing).
- T013/T014 (provider removal) independent of the client internals; T014 is [P] with T011/T012.

### Parallel Opportunities

- T002 ∥ T001 (different concerns).
- T004 ∥ T003.
- T005 ∥ T006 ∥ T007 (same file — coordinate; treat as one editing session if conflicts).
- T008 ∥ T009 (different exchange files).
- T014 ∥ T011/T012.
- T015 ∥ T020 during polish.

---

## Implementation Strategy

### MVP = the whole feature (US1)

1. Phase 1 Setup → deps swapped, baseline captured.
2. Phase 2 Foundational → **dedup spike resolved** (do not skip), `gql` seam ready.
3. Phase 3 US1 → tests first, then exchanges → client → import codemods → provider removal.
4. **STOP and VALIDATE**: Phase 4 gates + manual parity + bundle delta.

### Notes

- [P] = different files, no incomplete-task dependencies.
- Commit after each logical group (deps, exchanges, client, codemods, tests).
- The dedup spike (T003) is the one place this migration can genuinely regress behavior — resolve it before writing T010.
- Do not rewrite query bodies; only `gql` import paths change.
- New-dependency governance gate (maintainer sign-off) applies before merge, not during implementation.
