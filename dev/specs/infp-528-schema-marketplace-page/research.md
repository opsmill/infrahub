# Phase 0 Research — Schema Marketplace Integration

**Feature**: infp-528-schema-marketplace-page
**Date**: 2026-04-23

This document consolidates the findings from parallel research agents dispatched by `/speckit.plan`. All NEEDS CLARIFICATION items from the spec are resolved below.

---

## R-1. Current Marketplace API (live at `https://marketplace.infrahub.app`)

**Decision**: Treat the Marketplace as a **REST API** at `/api/v1/*`. Use the documented endpoints below from the Infrahub backend proxy. Do not build against GraphQL.

**Rationale**: The live Marketplace is a FastAPI app (backed by SQLAlchemy + SQLite on Cloudflare D1) serving a React SPA at `/` and REST at `/api/v1/*`. OpenAPI spec available at `https://marketplace.infrahub.app/api/openapi.json`. Read endpoints accept anonymous access; `Authorization: Bearer imkt_...` tokens are only needed for write ops or `users/me`. CORS is enabled with a curated `allowed_origins` list — this is precisely why the Infrahub frontend cannot call it cross-origin (FR-008, FR-010).

**Endpoints used by the Infrahub proxy** (upstream):

| Upstream | Purpose | Pagination |
|----------|---------|------------|
| `GET /api/v1/schemas?search=&tags=&limit=&after=` | List schemas | Cursor (`page_info.end_cursor`) |
| `GET /api/v1/schemas/{namespace}/{name}` | Schema detail (includes full `versions[]`) | — |
| `GET /api/v1/schemas/versions/{version_id}/content` | Raw YAML body | — |
| `GET /api/v1/schemas/{namespace}/{name}/versions/{semver}/download` | Download a specific version | — |
| `GET /api/v1/collections?search=&tags=&limit=&after=` | List collections | Cursor |
| `GET /api/v1/collections/{namespace}/{name}` | Collection detail (ordered items) | — |
| `GET /api/v1/collections/{namespace}/{name}/download` | Bundled install (all member schemas) | — |
| `GET /api/v1/tags` · `/api/v1/tags/counts` | Tag dictionary + counts | — |
| `GET /api/v1/catalog/resolve?ref=ns/name` | Disambiguate schema vs collection by ref | — |

**Representative list item** (from `/api/v1/schemas`):
```json
{
  "id": "cdccd721-...",
  "namespace": "infrahub",
  "name": "vlan-translation",
  "display_name": "VLAN Translation",
  "description": "...",
  "visibility": "public",
  "download_count": 12,
  "upvote_count": 4,
  "fork_count": 1,
  "viewer_has_upvoted": false,
  "created_at": "...",
  "updated_at": "...",
  "author": { "id": "...", "username": "...", "avatar_url": "..." },
  "tags": [ { "id": "...", "name": "network" } ],
  "latest_version": {
    "id": "...",
    "semver": "1.0.0",
    "status": "published",
    "changelog": "...",
    "download_count": 3,
    "download_url": "/api/v1/schemas/infrahub/vlan-translation/versions/1.0.0/download",
    "created_at": "..."
  }
}
```

**Alternatives considered**:
- Treating the Marketplace as a static GitHub-backed repo: **rejected** — the live service is a real FastAPI+DB app, not a static index.
- Building against GraphQL (as the prior `atg-01-config-wizard` branch did): **rejected** — there is no GraphQL endpoint on the live Marketplace. All prior GraphQL queries (`SCHEMAS_QUERY`, `COLLECTIONS_QUERY`, etc.) are dead code.

---

## R-2. Prior-branch reuse assessment (`atg-01-config-wizard`)

**Decision**: ADAPT the router; DROP the standalone client and models in favor of importing `infrahub_sdk.marketplace` (the SDK's public Python module); KEEP the Prefect workflow registration.

**Reuse disposition**:

| File | Disposition | Why |
|------|-------------|-----|
| `backend/infrahub/api/marketplace.py` | ADAPT | Router skeleton + auth dependency + workflow dispatch are reusable. Rewrite endpoint shapes to match REST upstream; delegate all Marketplace I/O to `infrahub_sdk.marketplace.MarketplaceClient`; add explicit `502`/`404` translation. |
| `backend/infrahub/marketplace/client.py` | THIN ADAPTER or DROP | GraphQL-based client is dead. Replace with either (a) a thin wrapper that instantiates `infrahub_sdk.marketplace.MarketplaceClient` with the Infrahub-configured `base_url` and a shared `httpx.AsyncClient`, or (b) nothing at all — consumers import the SDK directly. Decision at implementation time based on whether we need Infrahub-specific cross-cutting (e.g., logging/metrics) around every call. |
| `backend/infrahub/marketplace/models.py` | DROP | Models live in the SDK (`infrahub_sdk.marketplace`) as the single source of truth shared with the CLI. Infrahub backend imports them rather than defining parallel shapes. |
| `backend/infrahub/marketplace/tasks.py` | ADAPT | The Git worktree / commit / push flow is genuinely reusable (wizard-agnostic). Replace the HTTP code with `await client.fetch_schema_content(...)` / `await client.fetch_collection_bundle(...)` from the SDK module. |
| `backend/infrahub/workflows/catalogue.py` (entry only) | KEEP | Two-line registration of `MARKETPLACE_SCHEMA_INSTALL`. No wizard coupling. |
| `backend/tests/unit/marketplace/test_client.py` | DROP | Deleted alongside the client; the SDK owns client-level tests. Infrahub backend tests focus on the proxy router and the install task. |
| `backend/tests/unit/marketplace/test_models.py` | DROP | Deleted alongside the models. |

**Rationale**: The wizard UX went away, but the file boundaries (router, client, models, tasks, workflow) and the error + auth patterns are correct and match Infrahub's existing conventions. Only the domain content (API shapes) needs to be redone.

---

## R-3. Infrahub backend repository model

**Decision**:
- Distinguish writable repositories by **kind**: `CoreRepository` (writable, has `default_branch`) vs `CoreReadOnlyRepository` (read-only, has `ref`). Both inherit from `CoreGenericRepository`.
- Reuse `InfrahubRepository` + `Worktree` for local Git operations (`backend/infrahub/git/repository.py`, `backend/infrahub/git/worktree.py`).
- The install task writes schema YAML files into the worktree, runs `git add`/commit, and calls `InfrahubRepository.push()` — the existing repository-sync pipeline then picks up the commit and applies the schema to the graph.
- Permissions: the frontend filters the repository picker using `getObjectPermissions({ kind: "CoreRepository", branchName })`. The backend re-verifies kind + write permission server-side before committing (FR-027).

**Rationale**:
- The concrete kinds are defined in `backend/infrahub/core/constants/infrahubkind.py` and the generated protocols in `backend/infrahub/core/protocols.py` (lines 519-526). The frontend can filter by `kind == "CoreRepository"`.
- `InfrahubRepositoryIntegrator.import_schema_files()` (`backend/infrahub/git/integrator.py:510-581`) is the existing schema-load path from a repo commit. For marketplace installs we don't call it directly — the commit itself is what we produce; the existing repo-sync picks it up.

**Alternatives considered**:
- Using a single kind with a read-only flag: **rejected** — Infrahub's model is two distinct kinds, aligning with that is less surprising.
- Bypassing Git entirely and calling `sdk.schema.load()` directly from the backend: **rejected** for the UI install path (user explicitly wants schemas to flow through Git commits into their repo), **accepted** as the mechanism behind the `infrahubctl` CLI alternative.

---

## R-4. Backend configuration pattern

**Decision**: Create a new `MarketplaceSettings` subclass in `backend/infrahub/config.py` with one field `url: str = "https://marketplace.infrahub.app"` → env var `INFRAHUB_MARKETPLACE_URL`. Validate scheme at startup via a `@field_validator` (accept only `http://` or `https://`). Handlers read `config.SETTINGS.marketplace.url`.

**Rationale**:
- Infrahub uses `pydantic_settings.BaseSettings` with each subsection carrying its own prefix. A `MarketplaceSettings` class with `env_prefix="INFRAHUB_MARKETPLACE_"` produces `INFRAHUB_MARKETPLACE_URL` from field `url`.
- Naming **must** match `opsmill/infrahub-sdk-python#952`, which adds `infrahubctl marketplace download --marketplace-url` and reads the same `INFRAHUB_MARKETPLACE_URL` env var. A single exported variable configures both backend and CLI, so the CLI snippet the UI renders will pick up the operator's override without a second step.
- Plain `str` (not `HttpUrl`) matches existing URL fields like `telemetry_endpoint` and `public_url`.

**Alternatives considered**:
- Putting the field on `MainSettings` as `marketplace_url`: **rejected** — produces `INFRAHUB_MAIN_MARKETPLACE_URL` which diverges from the CLI's `INFRAHUB_MARKETPLACE_URL` and would force operators to set two variables.
- Using `pydantic.HttpUrl`: **rejected** — inconsistent with existing URL fields; plain `str` + a small validator is simpler.

---

## R-5. Workflow / task framework

**Decision**: Reuse the existing Prefect-based workflow system. Keep `MARKETPLACE_SCHEMA_INSTALL` registered in `backend/infrahub/workflows/catalogue.py`. The install endpoint calls `get_workflow().submit_workflow(...)` and returns a `task_id`; the frontend polls task status via the existing task GraphQL query (`PrefectTask.read_flow_runs()` in `backend/infrahub/task_manager/task.py`).

**Rationale**:
- This is Infrahub's canonical pattern for long-running API-triggered work (cite: `backend/infrahub/graphql/mutations/tasks.py:72`).
- No new dependency; no new polling infrastructure on the frontend.
- Rollback semantics (FR-020): on any failure before the commit lands, the task aborts without pushing. The worktree is ephemeral; nothing needs cleanup in the target repo.

**Alternatives considered**:
- Synchronous install with a long-held HTTP request: **rejected** — unreliable for large bundles and blocks a FastAPI worker.
- Emitting finer-grained sub-states via Prefect artifacts: **deferred** — coarse states (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`) suffice for MVP; revisit if UX demands staged progress (fetching/committing/pushing).

---

## R-6. Frontend architecture & home page

**Decisions**:

- **Page route**: `src/pages/schema-marketplace/index.tsx`, lazy-loaded from `src/app/router.tsx`. Mounted at `/schema-marketplace`.
- **Entity slice**: `src/entities/schema-marketplace/` following the existing pattern — `api/`, `types.ts`, `hooks/`, `ui/`.
- **Home tile**: new widget `src/entities/homepage/ui/schema-marketplace-widget.tsx`, using the existing `HomeCard` wrapper. Tile is **persistent** (always present) per FR-003; onboarding CTA surfaces only when `use-has-user-schemas` returns `false`.
- **"Schema Library" link repoint**: update the single match in `src/entities/homepage/ui/getting-started.tsx:115` from `https://github.com/opsmill/schema-library/` to `/schema-marketplace` (internal route).
- **Main navigation entry**: the sidebar menu is API-driven via `GET /api/menu`. Add the Schema Marketplace entry server-side (where Infrahub's built-in menu is generated). Frontend renders automatically.
- **Data fetching**: TanStack Query wrapping REST calls via `fetchUrl` (same pattern the prior wizard branch used for its marketplace module). GraphQL is unnecessary here — the backend exposes REST.
- **Permissions for repo picker**: `getObjectPermissions({ kind: "CoreRepository", branchName })` and `permission.update.isAllowed`.

**Rationale**:
- The existing home page uses a grid of `HomeCard` tiles (`ProposedChangesWidget`, `GitRepositoriesWidget`, etc.). A Schema Marketplace tile is a natural peer.
- Feature-Sliced layers present in this codebase are `src/pages/`, `src/entities/`, `src/shared/` — no `features/` or `widgets/` directories. All new code goes under `entities/schema-marketplace/` and `pages/schema-marketplace/`.
- API-driven menu means we do not touch `src/entities/navigation/` at all.

**Alternatives considered**:
- Apollo/GraphQL for marketplace data: **rejected** — backend proxy is REST; no reason to wrap it in GraphQL.
- Revive the prior branch's modal wizard components: **rejected** — replacement, not reuse. The page has a fundamentally different UX (persistent, non-blocking, post-setup-friendly).

---

## R-7. `infrahubctl` CLI alternative

**Decision**: Use `infrahubctl marketplace download` + `infrahubctl schema load` from `opsmill/infrahub-sdk-python#952` (branch `knotty-dibble`). Two invocations, no `curl` step. The `python_sdk` submodule MUST be pinned to the merged commit (or, pre-merge, to `knotty-dibble` HEAD) as part of this feature's rollout.

**What PR #952 adds** (per its summary):
- `infrahubctl marketplace download <namespace>/<name> [-v <semver>] [-c|--collection] [-o <dir>] [--marketplace-url <url>]`
- Auto-detects schema vs collection (probes both endpoints); `--collection` forces the collection path on `namespace/name` collisions.
- Writes files to `./schemas/` by default.
- Honors `--marketplace-url` flag, `marketplace_url` key in `infrahubctl.toml`, and `INFRAHUB_MARKETPLACE_URL` env var — **same env var as the Infrahub backend after R-4**.
- Clean error taxonomy: invalid input (exit 1), not found (exit 1), version not found (exit 1), network (exit 2). CI-friendly.
- REST-based (no GraphQL), matching R-1.

**Rationale**:
- Eliminates the `curl` two-step and removes a scope risk. The UX collapses to two `infrahubctl` commands per install.
- Env-var alignment means a single `INFRAHUB_MARKETPLACE_URL` export reconfigures both the web UI proxy and the CLI for mirror/test environments.
- `infrahubctl schema load` already exists and accepts directories — pairs naturally with `marketplace download`'s `./schemas/` output.

**Sample command block** the UI renders for a single selected schema:

```shell
# Download schema 'infrahub/vlan-translation@1.0.0' from the Marketplace
infrahubctl marketplace download infrahub/vlan-translation -v 1.0.0

# Apply to your Infrahub instance (requires INFRAHUB_ADDRESS + INFRAHUB_API_TOKEN)
infrahubctl schema load ./schemas --branch main
```

For multiple selected schemas, the UI renders one `infrahubctl marketplace download` per item into a shared output directory, then a single `infrahubctl schema load` over that directory.

For a collection, a single `infrahubctl marketplace download <ns>/<name>` line replaces all member downloads.

**Open questions** (non-blocking):
- Does `marketplace download` deduplicate when the same schema appears in multiple selected collections? If not, `infrahubctl schema load` handles idempotency anyway. Verify during implementation.

**Alternatives considered**:
- Two-step `curl` + `infrahubctl schema load`: **rejected** — now unnecessary given PR #952.
- Execute the CLI from the web UI: **rejected** — out of scope per spec; huge security surface.
- Add a `--load` convenience flag to `marketplace download`: PR #952 explicitly deferred this; accept the two-command flow for now.

---

## Open questions (non-blocking)

1. **Backend menu entry label + icon**: will follow naming used elsewhere in Infrahub's menu generator; exact UX copy to be confirmed during implementation (no impact on architecture).
2. **Tile visual design**: `/speckit.tasks` will surface a quick design spike; the tile uses the existing `HomeCard` component so customization is limited to the content block.
3. **Download-audit impact of short-TTL metadata cache**: Marketplace maintainers have not published rate-limit policy; if download-count undercounting becomes an issue, the proxy can skip caching for detail endpoints.
