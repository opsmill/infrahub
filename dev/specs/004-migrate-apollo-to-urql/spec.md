# Feature Specification: Migrate GraphQL Transport from Apollo Client to urql

**Feature Branch**: `migrate-apollo-to-urql-infp-563`

**Created**: 2026-07-27

**Status**: Draft

**Input**: User description: "Migrate the frontend GraphQL transport from Apollo Client to urql to reduce bundle size while preserving all existing transport behavior"

## Context

The frontend uses `@apollo/client` as a **transport-only** GraphQL layer. It uses none of Apollo's headline features:

- **No Apollo hooks** — all data-fetching hooks (`useQuery`, `useMutation`) come from TanStack Query, not Apollo.
- **No Apollo cache** — the client runs with `fetchPolicy: "no-cache"` and `queryDeduplication: false`; TanStack Query is the sole caching and request-deduplication authority.
- **No subscriptions, reactive variables, or manual cache reads/writes.**

Apollo is invoked imperatively — 63 `graphqlClient.query()` and 32 `graphqlClient.mutate()` call sites — behind a single client module. What Apollo actually provides is: a GraphQL transport, the `gql` tag (~33 files), and a link chain performing four jobs: auth-header injection, priority-header stamping, error routing with a token-refresh-and-replay loop, and multipart file uploads.

Because the heavyweight features are unused, the dependency's bundle cost is not justified. This feature swaps the transport to urql — whose exchange model is a direct analogue to Apollo's link chain — to shed bundle weight while keeping observable behavior identical.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Behavior-identical transport swap with a lighter bundle (Priority: P1)

The frontend continues to run every GraphQL query, mutation, file upload, and error/authentication flow exactly as before, but ships a smaller JavaScript bundle. Because a GraphQL transport cannot be partially swapped, the entire migration is one shippable, independently verifiable slice: replace the transport behind the existing imperative client interface, re-express the four transport behaviors, and change nothing observable to end users.

**Why this priority**: This is the whole feature. There is no smaller slice that delivers the value (a lighter bundle) without also being a complete, behavior-preserving swap. Delivering it makes the product measurably lighter with zero user-facing change.

**Independent Test**: Run the full existing browser test suite plus targeted transport-behavior tests before and after the swap; confirm all pass unchanged and that the production bundle's compressed size decreases. Exercise the app manually across authenticated browsing, object create/update/delete, file upload, and a forced token expiry — behavior is indistinguishable from the Apollo build.

**Acceptance Scenarios**:

1. **Given** an authenticated user browsing objects, **When** any existing query or mutation runs after the transport swap, **Then** it returns the same data and errors, applies the same headers (authorization, priority), and targets the same branch/time-scoped endpoint as before.
2. **Given** an operation whose access token has expired, **When** the server returns a token-expired error, **Then** the transport refreshes the token exactly once, replays the operation, and — if the replay still fails auth, the refresh returns no token, or the refresh itself fails — redirects the user to login and surfaces an error rather than hanging.
3. **Given** a form that uploads a file, **When** the user submits it, **Then** the multipart upload succeeds exactly as it did with the previous transport.
4. **Given** a GraphQL response that carries both partial data and errors, **When** the operation resolves, **Then** the partial data is retained (not discarded) and each error is routed by its catalogue code to the same policy as before (toast, silent permission-denied, redirect, or developer warning on an unrecognized code).
5. **Given** the production build is generated before and after the migration, **When** their compressed bundle sizes are compared, **Then** the post-migration bundle is smaller.

### Edge Cases

- **Token expiry mid-flight**: a single refresh + replay per operation; never more than one refresh attempt for the same operation.
- **Refresh returns no token / refresh throws / expiry persists after replay**: user is redirected to login and an error is surfaced; the request never hangs indefinitely.
- **File upload combined with an expired token**: the multipart operation is replayed successfully after the token refresh.
- **Response with both data and errors present**: partial data is preserved (matching the current retain-data-on-error behavior).
- **Unrecognized error catalogue code**: routed to the fallback policy (developer-visible warning in development builds, generic user notification otherwise).
- **No token present**: the authorization header is omitted entirely rather than sent empty.
- **Caller-supplied error-message override**: a per-operation error-handling override still fires instead of the default notification when provided.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST attach an authorization credential to every GraphQL operation when a valid access token is present, and MUST omit it entirely when no token is present.
- **FR-002**: The system MUST stamp every GraphQL operation with the request-priority indicator derived from the operation's context, falling back to the default priority when none is specified.
- **FR-003**: The system MUST resolve each operation's GraphQL endpoint per-operation from the operation's branch and point-in-time context.
- **FR-004**: Users MUST be able to upload files through GraphQL operations exactly as before (multipart uploads continue to function).
- **FR-005**: The system MUST route each GraphQL error to its existing policy based on the error's catalogue code — user notification, silent handling for permission-denied, redirect-to-login for authentication-required, and a developer-visible warning for unrecognized codes — and MUST honor a per-operation error-message override when the caller provides one.
- **FR-006**: On a token-expired error, the system MUST refresh the access token once and replay the operation. It MUST perform at most one refresh-and-replay per operation. If the replayed operation still returns token-expired, if the refresh returns no access token, or if the refresh fails, the system MUST redirect the user to login and surface an error — never leaving the operation pending.
- **FR-007**: The system MUST retain partial data returned alongside GraphQL errors rather than discarding the response (preserving the current retain-data-on-error behavior).
- **FR-008**: The migration MUST NOT change any of the 95 existing call sites' observable inputs or outputs; the imperative query/mutate interface they depend on MUST be preserved so no call-site logic changes.
- **FR-009**: The system MUST NOT introduce any GraphQL-layer response caching or request deduplication; the existing cache/dedup authority remains solely responsible, and every GraphQL operation continues to reach the network as it does today.
- **FR-010**: The GraphQL query-authoring approach (the query-document tag used across ~33 modules) MUST remain usable with at most a mechanical import-path change, so query definitions are not rewritten.

### Key Entities

- **GraphQL transport client**: the internal module exposing an imperative query/mutate interface to the rest of the app. Its interface (call signature and returned data/errors shape) is preserved; only its implementation changes.
- **Transport behavior chain**: the ordered set of cross-cutting behaviors applied to every operation — authorization, priority, endpoint resolution, error routing/refresh, and file-upload handling. Each behavior is preserved one-for-one.
- **Query document tag**: the mechanism used to author GraphQL query strings across the codebase; must remain in place with no rewrite of query bodies.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The production JavaScript bundle's compressed size is smaller after the migration than before, verified by comparing a build produced immediately before and immediately after the change. (Direction-only target; the exact reduction is recorded from the first before/after comparison.)
- **SC-002**: 100% of the pre-existing frontend automated checks (browser test suite, TypeScript-regression gate, format/lint gate) pass unchanged after the migration.
- **SC-003**: The token-refresh flow has explicit automated coverage proving all four of its invariants: exactly one refresh-and-replay, plus each of the three bail-to-login conditions (persistent expiry after replay, refresh returns no token, refresh fails).
- **SC-004**: Zero end-user-observable behavioral differences across the primary flows — authenticated browsing, object create/update/delete, file upload, and token-expiry recovery — confirmed by manual verification against the pre-migration build.
- **SC-005**: The heavyweight GraphQL-client dependency and its upload companion are fully removed from the dependency manifest, with no remaining imports referencing them.

## Assumptions

- The chosen transport's authentication-middleware capability can express the current refresh-and-replay contract, including the exactly-one-retry guarantee and all three bail-to-login conditions. (To be confirmed during planning.)
- The chosen transport's multipart-upload capability follows the same multipart request specification the backend already expects, so no backend change is required. (To be confirmed during planning.)
- The query-document tag can be provided from a local re-export so existing query modules change only their import path (or are updated by a mechanical codemod), without rewriting query bodies.
- TanStack Query remains the sole caching and request-deduplication layer; this migration does not alter caching semantics.
- No new subscription or real-time capability is introduced; none exists today.
- This is a frontend-only change: no backend, GraphQL schema, database, or CI/CD workflow changes are required.

## Governance Gates Crossed

- **New dependency** (Ask First): adds the urql core transport and its authentication and multipart-upload companions; removes `@apollo/client` and `apollo-upload-client`. Requires maintainer sign-off before merge.
- **Authentication (adjacent)**: reimplements the token-refresh-and-replay *mechanism* (not the authentication *policy*); requires auth-aware review.
- Not crossed: database/schema changes, GraphQL schema changes, CI/CD workflow changes.

## Out of Scope (v1)

- Adopting the new transport's document/normalized cache or its React hooks (the client stays transport-only).
- Rewriting the 95 imperative call sites to the new transport's native API (the preserved interface makes this unnecessary).
- Migrating any data fetching away from TanStack Query.
- Introducing GraphQL subscriptions or real-time features.
