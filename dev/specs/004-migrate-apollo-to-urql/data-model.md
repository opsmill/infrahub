# Phase 1 Data Model: Apollo → urql Transport

This feature introduces no domain data entities. The "entities" are the internal transport contracts that must be preserved 1:1. They are documented here because the migration's correctness is defined entirely by these shapes.

## Entity: GraphQL transport client (`graphqlClient`)

The single default-exported client module, consumed by ~95 call sites. Its **interface is preserved**; only its implementation swaps from Apollo to urql.

**Preserved public surface**:

| Method | Input | Output |
|---|---|---|
| `query` | `{ query: DocumentNode \| TypedDocumentNode<D,V> \| string; variables?: V; context?: OperationContext; fetchPolicy?: "no-cache" }` | `Promise<{ data?: D; errors?: Array<{ message: string }> }>` |
| `mutate` | `{ mutation: DocumentNode \| TypedDocumentNode<D,V> \| string; variables?: V; context?: OperationContext }` | `Promise<{ data?: D; errors?: Array<{ message: string }> }>` |

**Type inference rule** (Constitution III): both methods are generic; when passed a `TypedDocumentNode<D,V>` (from `gql.tada`'s `graphql()`), `data` is typed as `D` and `variables` as `V`. Untyped `DocumentNode`/`string` inputs yield `data` as `any`/`unknown` (parity with today's `gql(string)` sites — not made worse).

**Result invariants**:
- On success: `errors` is `undefined` (never `[]`), `data` is populated.
- On GraphQL errors with partial data: **both** `data` and `errors` populated (`errorPolicy: "all"` parity).
- On network error: `data` is `undefined`, error surfaced through the error pipeline.
- `errors[]` elements expose at least `.message` (only field callers read).

## Entity: `OperationContext` (per-call context)

The optional `context` object callers may pass. Only these keys are meaningful:

| Key | Type | Effect |
|---|---|---|
| `branch` | `string \| null` | Part of the per-operation endpoint URL (`CONFIG.GRAPHQL_URL`). Defaults to `"main"`. |
| `date` | `Date \| null` | When present, appends `?at=<ISO8601>` to the endpoint URL. |
| `priority` | `"high" \| "low"` (via `resolvePriority`) | Sets `X-Priority` header. Never set by app call sites today; default `"high"`. |
| `processErrorMessage` | `(message?: string) => void` | Overrides the default error toast for this operation (used to silence errors). |

Any other keys are ignored/passed through.

## Entity: Transport behavior chain (Apollo links → urql exchanges)

One-for-one preservation of the four cross-cutting behaviors:

| Behavior | Apollo (today) | urql (target) | Requirement |
|---|---|---|---|
| Auth header | `authLink` (`setContext`) | `authExchange.addAuthToOperation` | FR-001 |
| Priority header | `priorityLink` (`setContext`) | `mapExchange.onOperation` | FR-002 |
| Dynamic endpoint | `createUploadLink` uri fn | per-op `context.url` read by `fetchExchange` | FR-003 |
| File uploads | `apollo-upload-client` | native `fetchExchange` (multipart) | FR-004 |
| Error routing + refresh | `errorLink` (`onError`) + hand-rolled Observable | `authExchange` (refresh) + `mapExchange.onError` (routing) | FR-005, FR-006 |
| Partial-data retention | `errorPolicy: "all"` | default urql behavior | FR-007 |
| No cache / no dedup | `fetchPolicy: "no-cache"`, `queryDeduplication: false` | omit `cacheExchange`; **dedup gap flagged** | FR-009 |

## Entity: Error catalogue code routing

Unchanged policy, re-homed across two exchanges. Each GraphQL error's `extensions` catalogue code (parsed by the existing `parseCatalogueError`) routes to:

| Code | Policy | Where in urql |
|---|---|---|
| `TOKEN_EXPIRED` | refresh once + replay; persistent → login | `authExchange` (`didAuthError` + `refreshAuth`) |
| `AUTHENTICATION_REQUIRED` | `redirectToLogin()` | `mapExchange.onError` |
| `PERMISSION_DENIED` | silent (route guards handle 403s) | `mapExchange.onError` (no-op) |
| `UNDEFINED_ERROR` | toast + dev-only console warning pointing at the catalogue | `mapExchange.onError` |
| default | `processErrorMessage` override if present, else toast | `mapExchange.onError` |

## Entity: `gql` document producers (no data, authoring surface)

| Producer | Count | Change |
|---|---|---|
| `graphql()` from `gql.tada` → `TypedDocumentNode` | 65 files | none (urql consumes natively) |
| `gql(string)` from `@apollo/client` (wrapping `jsonToGraphQLQuery`) | 29 files | import path → local `gql` re-export from `@urql/core` |
| static `gql\`...\`` template | 1 (test) | rewritten with the test |
