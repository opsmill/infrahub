# Contract — Marketplace Proxy REST API

**Feature**: infp-528-schema-marketplace-page
**Base path**: `/api/marketplace` (mounted under Infrahub's FastAPI app)
**Auth**: All endpoints require `get_current_user` (Infrahub session/API-token).
**Content-Type**: `application/json` unless noted.

This document is the authoritative contract for the Infrahub-side proxy. Model names reference `data-model.md` §1. Field casing is snake_case (matching upstream and Infrahub conventions).

---

## Endpoint Index

| Method | Path | Purpose | Spec mapping |
|--------|------|---------|--------------|
| GET | `/api/marketplace/schemas` | List Marketplace schemas | FR-007, FR-010-011 |
| GET | `/api/marketplace/schemas/{namespace}/{name}` | Schema detail + versions | FR-008, FR-010-011 |
| GET | `/api/marketplace/schemas/versions/{version_id}/content` | Fetch a pinned version's YAML body | FR-010-011 |
| GET | `/api/marketplace/collections` | List collections | FR-007, FR-010-011 |
| GET | `/api/marketplace/collections/{namespace}/{name}` | Collection detail + items | FR-008, FR-010-011 |
| GET | `/api/marketplace/tags` | Tag dictionary with counts | FR-010-011 |
| GET | `/api/marketplace/status` | Proxy + upstream health | FR-013-015 |
| POST | `/api/marketplace/install` | Trigger Prefect install workflow | FR-017-022 |
| GET | `/api/marketplace/cli-snippet` | Render the `infrahubctl` alternative | FR-030-033 |

---

## 1. `GET /api/marketplace/schemas`

Proxies `GET {MARKETPLACE_URL}/api/v1/schemas`. Cursor pagination is pass-through.

**Query parameters**:

| Name | Type | Required | Default | Notes |
|------|------|----------|---------|-------|
| `search` | string | no | — | Full-text search; forwarded verbatim to upstream |
| `tags` | csv of strings | no | — | Tag slugs |
| `limit` | int | no | `20` | 1..50 |
| `after` | string | no | — | Opaque cursor from previous `page_info.end_cursor` |

**200 OK** — `MarketplaceSchemasListResponse` (data-model §1.11)

**Errors**:
- `502 Bad Gateway` — upstream unreachable or returned 5xx; body: `{ "detail": "marketplace_unreachable" }`
- `504 Gateway Timeout` — upstream exceeded 10s timeout
- `500` — misconfiguration (e.g., `marketplace_url` invalid); body: `{ "detail": "marketplace_misconfigured" }`

**Caching**: short-TTL (30s) in-memory cache keyed on `(search, tags, limit, after)`. Cache is scoped per Infrahub backend process; no distributed cache required.

---

## 2. `GET /api/marketplace/schemas/{namespace}/{name}`

Proxies `GET {MARKETPLACE_URL}/api/v1/schemas/{namespace}/{name}`.

**Path parameters**: `namespace` (string), `name` (string).

**200 OK** — `MarketplaceSchemaDetail` (data-model §1.6)

**Errors**:
- `404 Not Found` — upstream returned 404; body: `{ "detail": "schema_not_found" }`
- `502` / `504` — as above.

---

## 3. `GET /api/marketplace/schemas/versions/{version_id}/content`

Proxies `GET {MARKETPLACE_URL}/api/v1/schemas/versions/{version_id}/content`. Used by the frontend's detail view (preview) and internally by the install workflow.

**Path parameters**: `version_id` (UUID string).

**200 OK** — `MarketplaceVersionContent` (data-model §1.7). Response body is JSON wrapping the YAML content string (not the raw YAML bytes).

**Errors**:
- `404` — version not found.
- `502` / `504`.

**Caching**: NOT cached (see plan.md scope risk #2 — download audits).

---

## 4. `GET /api/marketplace/collections`

Proxies `GET {MARKETPLACE_URL}/api/v1/collections`. Same pagination + filtering semantics as `/schemas`.

**200 OK** — `MarketplaceCollectionsListResponse` (data-model §1.11).

---

## 5. `GET /api/marketplace/collections/{namespace}/{name}`

**200 OK** — `MarketplaceCollectionDetail` (data-model §1.10).

---

## 6. `GET /api/marketplace/tags`

Proxies `GET {MARKETPLACE_URL}/api/v1/tags/counts`.

**200 OK**:
```json
{
  "tags": [
    { "id": "uuid", "name": "network", "count": 12 },
    { "id": "uuid", "name": "dcim", "count": 8 }
  ]
}
```

---

## 7. `GET /api/marketplace/status`

Reports proxy configuration + upstream reachability. Serves FR-013-015 (configuration-error state).

**200 OK**:
```json
{
  "marketplace_url": "https://marketplace.infrahub.app",
  "url_configured": true,
  "url_scheme_valid": true,
  "upstream_reachable": true,
  "checked_at": "2026-04-23T14:55:12Z"
}
```

**Failure modes** (still 200; the body reports the problem so the UI can render a config-error state):
- `url_configured: false` — env var unset or empty.
- `url_scheme_valid: false` — URL does not start with `http://` or `https://`.
- `upstream_reachable: false` — health-check to upstream `/health` failed.

---

## 8. `POST /api/marketplace/install`

Triggers the Prefect `MARKETPLACE_SCHEMA_INSTALL` workflow.

**Request body**: `MarketplaceInstallRequest` (data-model §1.12).

**Example**:
```json
{
  "repository_id": "e1a5...",
  "branch_name": "main",
  "items": [
    { "kind": "schema", "namespace": "infrahub", "name": "vlan-translation", "semver": "1.0.0" }
  ]
}
```

**202 Accepted** — `MarketplaceInstallResponse` (data-model §1.12).
```json
{
  "task_id": "9b21...",
  "message": "Install queued; poll task status for progress."
}
```

**Errors**:
- `400 Bad Request` — invalid payload (empty `items`, malformed semver, unknown `kind`).
- `403 Forbidden` — authenticated user lacks write permission on the target repository; body: `{ "detail": "repository_write_forbidden" }`.
- `404 Not Found` — `repository_id` does not resolve, or `branch_name` doesn't exist on that repo.
- `409 Conflict` — `repository_id` resolves to a `CoreReadOnlyRepository` (never a valid install target); body: `{ "detail": "repository_not_writable" }`.
- `502` / `504` — upstream Marketplace unreachable when resolving version IDs prior to queuing (optional pre-validation).

**Progress polling**: the client polls the existing task GraphQL query using the returned `task_id` (Prefect flow run id). See `backend/infrahub/graphql/mutations/tasks.py` for the existing pattern.

---

## 9. `GET /api/marketplace/cli-snippet`

Generates the `infrahubctl` alternative command block for the no-writable-repo state (FR-030-033). Uses `infrahubctl marketplace download` from `opsmill/infrahub-sdk-python#952`.

**Query parameters**:

| Name | Type | Required | Notes |
|------|------|----------|-------|
| `items` | repeated `kind:namespace/name@semver` | yes (1..50) | e.g., `items=schema:infrahub/vlan-translation@1.0.0` |
| `branch_name` | string | no | Default: `main`. Used only for the `--branch` flag in the generated `infrahubctl schema load` command. |
| `output_dir` | string | no | Default: `./schemas`. Passed as `-o` to `infrahubctl marketplace download`. |

**200 OK**:
```json
{
  "downloads": [
    {
      "kind": "schema",
      "namespace": "infrahub",
      "name": "vlan-translation",
      "semver": "1.0.0",
      "command": "infrahubctl marketplace download infrahub/vlan-translation -v 1.0.0"
    }
  ],
  "load_command": "infrahubctl schema load ./schemas --branch main",
  "rendered": "infrahubctl marketplace download infrahub/vlan-translation -v 1.0.0\ninfrahubctl schema load ./schemas --branch main"
}
```

The `rendered` string is the one-click copy target; `downloads[].command` and `load_command` are also exposed so the frontend can render per-line copy buttons.

Rules for rendering:
- **Schema items** → one `infrahubctl marketplace download <ns>/<name> -v <semver>` line each (`-v` omitted if the user selected "latest").
- **Collection items** → one `infrahubctl marketplace download <ns>/<name>` line; `-v` is NOT passed (collections are version-less). Add `-c` if the identifier might collide with a schema namespace — the backend can check upstream to decide whether `-c` is needed.
- All downloads share `-o <output_dir>` unless it is the default (`./schemas`), in which case omit the flag for cleanliness.
- A single trailing `infrahubctl schema load <output_dir> --branch <branch>` applies everything.
- If the backend is configured with a non-default `INFRAHUB_MARKETPLACE_URL`, the rendered commands include `--marketplace-url <configured_url>` so the CLI hits the same Marketplace the UI is showing.

**Errors**:
- `400` — no items, >50 items, or malformed `kind:ns/name@semver`.

**Caching**: not cached (cheap server-side rendering).

---

## Cross-cutting concerns

### Error taxonomy

| Outcome | HTTP | `detail` value |
|---------|------|----------------|
| Upstream 5xx or network failure | 502 | `marketplace_unreachable` |
| Upstream timeout | 504 | `marketplace_timeout` |
| Upstream 404 | 404 | `<resource>_not_found` |
| Backend misconfiguration | 500 | `marketplace_misconfigured` |
| Bad request | 400 | `invalid_request` or specific code |
| Permission check failed | 403 | `repository_write_forbidden` |
| Read-only repo target | 409 | `repository_not_writable` |

Error bodies NEVER echo internal traces or database structure (Principle VI).

### Upstream URL construction

All upstream calls use `config.SETTINGS.marketplace.url` (env: `INFRAHUB_MARKETPLACE_URL`) joined with `/api/v1/<path>`. In practice, the Infrahub backend delegates the HTTP to `infrahub_sdk.marketplace.MarketplaceClient(base_url=...)`; Infrahub only owns the URL resolution, the Pydantic-level input validation on Infrahub endpoints, and the error-code translation. Validate the URL at startup (scheme `http`/`https`); log a warning if invalid and make `/api/marketplace/status` report `url_scheme_valid: false`.

### Timeouts and retries

Per-request upstream timeout: 10s. Retry once on network error with 500ms backoff. No retries on 4xx/5xx bodies from upstream.

### Rate limiting (defensive)

Apply Infrahub's existing per-user rate limit on `/api/marketplace/*` endpoints if one exists; otherwise, no new rate limit is added (scope).

### Observability

- Log one INFO line per proxy call: `marketplace.proxy method=GET path=/schemas upstream_status=200 duration_ms=123`.
- On failure, log at WARNING with upstream URL (never with secrets).
- Emit a Prefect artifact on install start/completion/failure capturing the `MarketplaceInstallPayload` and outcome.

### Security

- Proxy NEVER forwards client cookies or `Authorization` headers upstream.
- Upstream calls are strictly GET for read endpoints; install does not touch upstream beyond reading version content.
- All inputs pass through Pydantic validation before use in upstream URL construction (Principle VI).
