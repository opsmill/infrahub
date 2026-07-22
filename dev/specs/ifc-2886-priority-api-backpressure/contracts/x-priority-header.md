# Contract: `X-Priority` request header & `429` admission response

**Feature**: IFC-2886 | Applies to: every HTTP endpoint served by the Infrahub API (except the excluded liveness/scrape/static paths below).

This is a **transport-layer contract**. It adds one request header and one possible response outcome. It does **not** change any REST/GraphQL request body, GraphQL schema, or existing 2xx/4xx/5xx semantics of the handlers themselves.

> **Naming note**: the middle tier was renamed `normal` → `medium` after this contract was written. The shipped header values are `high` / `medium` / `low`; read `normal` as `medium` below.

## Request: `X-Priority` (new, optional)

| Property | Value |
|----------|-------|
| Header name | `X-Priority` |
| Direction | Client → Server |
| Required | No (optional) |
| Allowed values | `high`, `normal`, `low` (case-insensitive, surrounding whitespace trimmed) |
| Default when absent | `normal` |
| Default when empty/invalid | `normal` (FR-006) |
| Trust model (v1) | Cooperative / first-party. Any caller may claim `high`; no server-side enforcement that the claim is legitimate. |

**Classification rules** (FR-006):
- `X-Priority: high` → class `high`.
- `X-Priority: normal` → class `normal`.
- `X-Priority: low` → class `low`.
- Header absent, empty, whitespace-only, or any other value → class `normal`, and the request is counted as "no/invalid priority" for adoption tracking (FR-OBS-7).

**Excluded paths** (admission is bypassed entirely — never classified, never shed): `/health`, `/metrics`, and the static/docs set `/assets`, `/favicons`, `/docs`, `/api/schema`. Non-HTTP scopes (WebSocket, lifespan) are never affected.

## Response: `429 Too Many Requests` (new outcome)

Emitted **instead of** invoking the handler when the admission layer sheds the request (FR-007). No handler work is performed; no downstream DB query runs.

**Status**: `429 Too Many Requests`

**Headers**:
| Header | Value |
|--------|-------|
| `Retry-After` | Integer seconds (from `INFRAHUB_API_BACKPRESSURE_RETRY_AFTER_SECONDS`, default `1`). Always present on a shed response. |
| `Content-Type` | `application/json` |

**Body** — matches the existing Infrahub error envelope (`backend/infrahub/api/exception_handlers.py`), REST vs GraphQL selected by request path:

REST envelope:
```json
{
  "data": null,
  "errors": [
    { "message": "Server is shedding load; retry later.", "extensions": { "code": 429 } }
  ]
}
```

GraphQL envelope (for GraphQL paths):
```json
{
  "data": null,
  "errors": [
    { "message": "Server is shedding load; retry later.", "extensions": { "code": 429 } }
  ]
}
```

**Shed reasons** (internal, surfaced only via metrics — not in the response body): `codel` (adaptive shed from sustained sojourn) or `backstop` (per-class waiter cap exceeded). See `metrics.md` (FR-OBS-2).

## Behavioural guarantees (acceptance-testable)

| ID | Guarantee |
|----|-----------|
| C-1 | A request with a valid `X-Priority` is classified into the matching class; missing/invalid → `normal`. (FR-006) |
| C-2 | When capacity is available, requests of every class are admitted and the handler runs normally (no behaviour change vs today). (SC-006) |
| C-3 | When shed, the response is exactly `429` + a `Retry-After` header, and the handler never executed (no side effects, no DB work). (FR-007, SC-004) |
| C-4 | Under sustained overload, `high` is shed last (≈0%), `low` first, `normal` second. (FR-005, SC-002) |
| C-5 | A burst shorter than the CoDel `interval` yields zero sheds. (FR-003, SC-003) |
| C-6 | Excluded paths (`/health`, `/metrics`) are never shed. |
| C-7 | Client disconnect while queued leaks no slot and cannot deadlock the pool. (FR-008) |

## Compatibility

- **Backward compatible**: existing clients that never send `X-Priority` are treated as `normal` and see no change under normal load. The layer ships inert (SC-006).
- **No GraphQL schema change**; **no request/response body change** for non-shed requests.
- **New/changed public surface**: the `X-Priority` request header and the `429 + Retry-After` outcome — both flagged as an API/public-interface governance gate for review.
