# Contract: Outbound `X-Priority` Header

**Feature**: IFC-2890 | **Type**: Frontend outbound-request contract

This contract governs the `X-Priority` header the frontend emits. It is observable at the transport boundary (the outbound HTTP request), which is where it MUST be asserted — not at the injection internals.

## Header

- **Name**: `X-Priority` (sent title-cased; backend matches case-insensitively).
- **Allowed values**: `high` | `low`. No other value, ever, from a frontend origin.
- **Default**: `high`, applied when no opt-in is declared.

## Per-transport guarantees

### GraphQL (Apollo)

```
GIVEN an Apollo operation with no `priority` in its context
WHEN the operation is sent
THEN the outbound request carries `X-Priority: high`

GIVEN an Apollo operation with context `{ priority: 'low' }`
WHEN the operation is sent
THEN the outbound request carries `X-Priority: low`

GIVEN an operation that receives 401 and is replayed after token refresh
WHEN the replay is sent
THEN the replay carries the same `X-Priority` value as the original

GIVEN a multipart file-upload mutation
WHEN it is sent (via the shared upload link)
THEN it carries `X-Priority: high` (or `low` if declared)
```

### REST (`openapi-fetch`)

```
GIVEN a REST call with no `priority` option
WHEN it is sent
THEN the outbound request carries `X-Priority: high`

GIVEN a REST call with option `{ priority: 'low' }`
WHEN it is sent
THEN the outbound request carries `X-Priority: low`

GIVEN a REST call that receives 401 and is replayed from its stored clone
WHEN the clone is replayed
THEN the replay carries the same `X-Priority` value as the original
```

### Raw fetch (`fetchUrl`)

```
GIVEN a `fetchUrl` call to an Infrahub-API URL with no priority arg
WHEN it is sent
THEN the outbound request carries `X-Priority: high`

GIVEN a `fetchUrl` call with `{ priority: 'low' }`
WHEN it is sent
THEN the outbound request carries `X-Priority: low`

GIVEN a request whose target host is NOT the Infrahub API
      (the request URL's origin differs from INFRAHUB_API_SERVER_URL's origin)
WHEN it is sent
THEN it carries NO `X-Priority` header
```

> The external-host guard compares **origins** (scheme + host + port), not a URL substring, to avoid both false leaks and false suppression (critique E3).

### GraphiQL fetcher

```
GIVEN a GraphiQL sandbox request
WHEN it is sent
THEN it carries `X-Priority: high`
```

## Query-class guarantees (FR-005 / SC-002)

```
GIVEN a watched live-status poll (task list, task status,
      proposed-change details, proposed-change events, branch action state)
WHEN it fetches on its interval
THEN it carries `X-Priority: high`
AND none of these queries is declared `low`

GIVEN the frontend's full request mix
WHEN any frontend-origin request is observed on any transport
THEN it carries either `high` or `low` — never `normal`, never absent
```

## Non-goals

- No request body, method, endpoint, or GraphQL-schema change.
- No change to the backend's parsing of the header (already accepts `high`/`normal`/`low`).
