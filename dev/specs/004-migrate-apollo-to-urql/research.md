# Phase 0 Research: Apollo Client → urql Transport Migration

All urql facts verified against the official urql docs (source markdown at `github.com/urql-graphql/urql`) and the npm registry, July 2026. All codebase facts verified against `frontend/app/src` at the feature branch head.

## Decision 1 — Target packages

**Decision**: Add `@urql/core@^6` and `@urql/exchange-auth@^3`. Remove `@apollo/client`, `apollo-upload-client`, and `@types/apollo-upload-client`. Keep `graphql@^16` (still required by `gql.tada`).

**Rationale**:
- `@urql/core` (~10.3 KB gz) replaces `@apollo/client` (~51.8 KB gz) — a ~5× reduction, and `@urql/core` is the transport-only core with no React bindings needed.
- File uploads are **native** to `@urql/core@4+`'s `fetchExchange` (GraphQL multipart request spec). The standalone `@urql/exchange-multipart-fetch` package is **deprecated** (last published 2023) and must not be used. This resolves spec Assumption #2: no separate multipart exchange is required; the same multipart-request spec the backend already accepts is emitted by the built-in `fetchExchange`.
- `@urql/exchange-auth@3` provides the token-refresh middleware (Decision 4).

**Alternatives considered**:
- `urql` (React bindings package): rejected — the app uses zero GraphQL hooks; the React `Provider`/hooks are dead weight. `@urql/core` alone suffices.
- `graphql-request` / raw fetch: rejected during grilling — no middleware/exchange model for the auth-refresh loop, priority header, error routing, and uploads.

## Decision 2 — Imperative, provider-free usage

**Decision**: Instantiate a single standalone `@urql/core` `Client` and call `client.query(doc, vars, context).toPromise()` / `client.mutation(doc, vars, context).toPromise()` from inside the preserved adapter. **Remove** the `<ApolloProvider>` wrapper in `src/app/app.tsx` and the two test wrappers (`enum.test.tsx`, `dropdown.test.tsx`) rather than replacing them with urql's React `Provider`.

**Rationale**: All app GraphQL is imperative and fronted by TanStack Query; the Apollo provider is vestigial (nothing consumes an Apollo/urql React context). Removing it keeps the dependency surface at `@urql/core` only.

**Result shape**: `.toPromise()` resolves to an `OperationResult` — `{ data, error, operation, extensions, stale }`. `error` is a `CombinedError | undefined` with `.graphQLErrors` (array of `GraphQLError`, each preserving `.extensions`) and `.networkError`.

## Decision 3 — No caching; dedup risk (the one behavioral gap)

**Decision**: Configure the `Client` with `exchanges: [mapExchange(...), authExchange(...), fetchExchange]` — **`cacheExchange` omitted entirely**. This matches Apollo's `fetchPolicy: "no-cache"`: every operation reaches the network, TanStack Query stays the sole cache.

**Open risk (requires a Phase-0 spike before implementation — see tasks)**: urql's **in-flight deduplication is baked into the `Client` since v4 and has no public off-switch** (unlike Apollo's `queryDeduplication: false`). The dedup key is `hash(query, variables)` and **ignores `context`**. Because this app carries the **branch and point-in-time in `context.url`**, not in variables, two *concurrent* operations with identical query+variables but **different branches/dates** would share a single network request and both receive one branch's data.

- **Likelihood**: non-trivial for Infrahub specifically — side-by-side branch comparison / diff views are core and can issue the same query against two branches at once. TanStack Query dedups upstream by `queryKey` (which includes branch), so identical-branch concurrency is already collapsed before reaching urql; the exposed case is *cross-branch concurrent identical query+vars*.
- **Spike**: reproduce with two concurrent `graphqlClient.query` calls, same document+variables, different `context.branch`; assert both responses reflect their own branch.
- **Candidate mitigations (decide from spike outcome)**: (a) confirm TanStack timing makes true concurrency non-reproducible and accept as-is; (b) fold a branch/date discriminator into the operation so the dedup key differs per branch (verify the backend tolerates it without changing the wire request semantics); (c) per-branch `Client` instances keyed by URL. Mitigation choice is deferred to the spike; the migration must not ship until this is resolved or ruled out.

**SPIKE OUTCOME (resolved).** The hazard **reproduced**: two concurrent identical
query+variables calls on different branches produced **one** `fetch` (dedup),
and both callers received one branch's data. See
`frontend/app/src/shared/api/graphql/graphqlClient.dedup.test.tsx`.

**Mitigation applied: (b), request-key folding — no wire change.** The adapter
builds the operation via `createRequest(query, variables)` and folds the
endpoint URL into `request.key` (`keyedQueryRequest` in `graphqlClient.tsx`),
then calls `client.executeQuery(request, context)`. urql's dedup keys on
`request.key`, so different branches/dates now produce distinct keys and fetch
independently, while identical (query, variables, url) calls still dedup as
intended. The GraphQL request sent over the wire is unchanged (the key is a
client-internal identity only). Mutations are untouched — urql assigns every
mutation a fresh `_instance` and never dedups them. The dedup test is retained
as a permanent regression guard (2 fetches, correct per-branch data).

## Decision 4 — Token refresh via `authExchange` (FR-006)

**Decision**: Implement FR-006 with `@urql/exchange-auth`'s `authExchange(async utils => ({ addAuthToOperation, willAuthError, didAuthError, refreshAuth }))`:
- `addAuthToOperation`: append `Authorization: Bearer <token>` when a token exists (FR-001).
- `didAuthError(error)`: return `true` when a `graphQLErrors[].extensions` catalogue code is `TOKEN_EXPIRED`.
- `refreshAuth`: call the existing refresh-token flow (via TanStack `queryClient.fetchQuery(refreshAccessTokenQueryOptions())`); on success store the new token; **on failure, no token, or a persistent second failure → `redirectToLogin()` and clear credentials**.

**Rationale / how the FR-006 invariants map**:
- **Automatic replay after refresh**: built in — authExchange retries the failed/held operations once `refreshAuth` resolves. (No manual re-issue, unlike today's hand-rolled `retryWithRefreshedToken` Observable.)
- **Exactly one refresh for concurrent ops**: built in — authExchange pauses all operations while a single `refreshAuth` runs (mutex/queue), then replays them.
- **"Exactly one refresh + replay, then bail to login"**: authored via closure state — record the token used before refresh; on entering `refreshAuth`, if the just-failed token is unchanged / the refresh returns no token / the refresh throws, perform `redirectToLogin()` instead of looping. This guards against an infinite refresh loop and expresses the three bail-to-login conditions.

**Alternatives considered**: keep the hand-rolled Observable retry — rejected; authExchange is purpose-built and removes the most error-prone code in the current client.

## Decision 5 — Cross-cutting behaviors as exchanges

**Decision**:
- **Per-operation URL (FR-003)**: pass `{ url: CONFIG.GRAPHQL_URL(branch, date), requestPolicy: 'network-only' }` as the third `context` arg of each `client.query/mutation` call inside the adapter. `fetchExchange` reads `context.url` per operation.
- **Priority header (FR-002)**: a `mapExchange({ onOperation })` that stamps `X-Priority: resolvePriority(operation.context.priority)` into `fetchOptions.headers`. (No call site sets `priority`; the default `high` is preserved, and the seam is kept.)
- **Error routing (FR-005) + partial data (FR-007)**: error side-effects (toast / silent PERMISSION_DENIED / AUTHENTICATION_REQUIRED redirect / UNDEFINED_ERROR dev-warn / `processErrorMessage` override) implemented in `mapExchange({ onError })` reading `operation.context`. Partial data is preserved automatically — urql always surfaces `data` and `error` together (equivalent to Apollo `errorPolicy: "all"`; no config needed).

**Exchange order** (outward to network): `[mapExchange(headers+errors), authExchange, fetchExchange]`. authExchange must sit before the terminating `fetchExchange` and after synchronous exchanges. `fetchExchange` is last.

## Decision 6 — `gql` handling (FR-010)

**Decision**:
- The **65 files using `gql.tada`'s `graphql()`** need **no change** — it produces `TypedDocumentNode`, which `@urql/core`'s `client.query/mutation` consume natively and infer `data` types from. The adapter must be generic over `TypedDocumentNode` to preserve this inference (Constitution III).
- The **29 files using `gql(dynamicString)` from `@apollo/client`** (always wrapping a `jsonToGraphQLQuery` string) switch to a local `gql` re-exported from `@urql/core` (a one-line import-path change per file, mechanical/codemod-able). `@urql/core`'s `gql` returns a compatible `DocumentNode`; `client.query` also accepts a raw string, so the wrapper could even be dropped later — out of scope for v1.
- The 1 static `gql\`...\`` template literal is in a test that is being rewritten anyway.

**Adapter input type**: `DocumentNode | TypedDocumentNode<Data, Vars> | string` (urql accepts all three).

## Decision 7 — Result-shape adapter (FR-008)

**Decision**: The adapter maps urql's `OperationResult` to the preserved Apollo-like shape `{ data, errors }`:
- `errors` = `result.error?.graphQLErrors` **mapped to `Array<{ message }>`**, or **`undefined` when there is no error** (never `[]` — callers use both `if (errors)` and `if (errors?.length)`, and an empty array would make `if (errors)` throw with an empty message).
- `data` = `result.error?.networkError ? undefined : result.data` — preserve partial data on GraphQL errors, but a network error yields no data (matching current behavior where the transport rejects/produces no data on transport failure).
- Adapter methods: `query({ query, variables?, context?, fetchPolicy? })` and `mutate({ mutation, variables?, context? })`, each returning `Promise<{ data, errors }>`. `fetchPolicy` (passed at 6 sites) is accepted and ignored (already the default no-cache behavior).

**Context keys honored**: `branch`, `date` → URL; `priority` → `X-Priority`; `processErrorMessage` → error-toast override. Others pass through/ignored.

## Decision 8 — Force POST for all operations (`preferGetMethod: false`)

**Decision**: Set `preferGetMethod: false` on the urql `Client`.

**Rationale**: `@urql/core@6` defaults `preferGetMethod` to `'within-url-limit'`,
so it sends **queries as GET** whenever the serialized URL fits the length limit
(mutations always POST). The Infrahub backend's `/graphql/<branch>` endpoint
**only accepts POST** — a GET falls through to the SPA catch-all and returns
`index.html` (HTTP 200, `text/html`). urql then fails to parse the HTML as JSON,
throws, and the app's error boundary renders the raw HTML. Apollo always POSTed,
so this only surfaced after the swap. Setting `preferGetMethod: false` forces
POST for every operation, restoring parity. Guarded by a regression test
(`client.test.tsx`: "sends queries as POST").

**Discovered via**: runtime verification in a real browser (the unit suite and
`pnpm build` passed because they don't exercise the live GET→SPA-fallback path).
A reminder that transport migrations need a real end-to-end smoke test, not just
green unit tests.

## Decision 9 — Inject `__typename` on every operation (`formatDocument`)

**Decision**: Add a `mapExchange` whose `onOperation` runs `formatDocument(operation.query)`.

**Rationale**: Apollo's `InMemoryCache` auto-injected `__typename` into every
selection set. urql only does this inside `cacheExchange`, which we omit. The app
reads `node.__typename` in several places — notably the relationship table cell,
which resolves a peer node's schema by its `__typename`. Without injection those
come back `undefined` and the UI shows "Schema for undefined not found" on every
relationship column. `formatDocument` is the same utility urql's `cacheExchange`
uses, so this restores Apollo parity without adding a cache. Guarded by a
regression test (`client.test.tsx`: "injects __typename into selections").

**Discovered via**: runtime browser testing of `/objects/InfraDevice` — again
invisible to the unit suite and `pnpm build`.

## Testing approach (Constitution IV)

- **Rewrite** `graphqlClientApollo.test.ts` (tightly coupled to `ApolloLink`/`execute`/`Observable`) against the urql exchanges: drive the auth/priority/error exchanges directly.
- **New unit coverage for FR-006 (SC-003)**: exactly-one refresh+replay, plus all three bail-to-login paths (persistent expiry after replay, refresh returns no token, refresh throws).
- **Swap** the two component-test wrappers (`enum.test.tsx`, `dropdown.test.tsx`) to render without a provider.
- **Existing browser suite + `betterer` + `biome ci`** must pass unchanged (SC-002).
- **Existing Playwright E2E** covers the user-facing flows (authenticated browse, object CRUD, file upload); no new user-facing behavior is introduced, so no new E2E feature suite is required, but the upload + branch flows must be confirmed green.

## Resolved spec assumptions

- Assumption #1 (authExchange can express the refresh contract): **confirmed** — Decision 4.
- Assumption #2 (multipart exchange follows the backend spec): **superseded** — uploads are native to `@urql/core@4+`; no exchange needed (Decision 1).
- Assumption #3 (`gql` re-export, mechanical import change): **confirmed** — Decision 6.
- New item surfaced: **in-flight dedup gap** (Decision 3) — the one behavior without a 1:1 Apollo equivalent; gated by a spike.
