# Implementation Plan: Schema Marketplace Integration — Dedicated Page + Backend Proxy

**Branch**: `infp-528-schema-marketplace-page` | **Date**: 2026-04-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/infp-528-schema-marketplace-page/spec.md`

## Summary

Replace Infrahub's first-run schema wizard modal with a dedicated **Schema Marketplace page**, a persistent **home-page tile** linking to it (onboarding CTA when no user schemas are loaded), and a **backend REST proxy** to `https://marketplace.infrahub.app` so the frontend never calls the Marketplace cross-origin. Installs commit selected schemas to a user-chosen writable `CoreRepository` via a Prefect workflow; when no writable repository exists, the page blocks UI install and presents a copy-pasteable `infrahubctl` alternative that applies the schema live without a Git commit path.

Prior art: `atg-01-config-wizard` branch. Prior backend code assumed a **GraphQL** Marketplace API and a modal wizard UX. The live Marketplace is a **REST API** under `/api/v1/*` — the prior client, models, and proxy contract are almost entirely incorrect and MUST be rewritten. Git commit mechanics and the Prefect workflow registration are reusable.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.9 (frontend), Python 3.8+ (`infrahubctl` in `python_sdk` submodule).
**Primary Dependencies**:
- Backend: FastAPI 0.121.1, Pydantic 2.10, `pydantic-settings`, `httpx` via `InfrahubHTTP` adapter, Prefect (workflow orchestration), GitPython.
- Frontend: React 19.2, Vite 8.0, Tailwind 4.2, TanStack Query, Apollo Client (existing), `gql.tada`.
- CLI: Typer. **New**: `infrahubctl marketplace download` command from `opsmill/infrahub-sdk-python#952` (branch `knotty-dibble`). Adds a REST-based Marketplace client that auto-detects schemas vs collections, pins versions with `-v <semver>`, writes to `--output-dir` (default `./schemas`), and honors `--marketplace-url` / `INFRAHUB_MARKETPLACE_URL`. Chains with the existing `infrahubctl schema load` to apply. **Used only by end users on their own machines for the no-writable-repo UI alternative** (FR-030-034) — NOT shelled out by the Infrahub backend.
- Shared SDK library: `infrahub_sdk.marketplace` (public Python module). The Infrahub backend **imports Python functions** from the SDK for listing, detail, and content-download operations rather than running the CLI as a subprocess. PR #952 currently keeps these as private helpers inside `infrahub_sdk/ctl/marketplace.py`; a small refactor on the SDK side exposes them as a public module. See "SDK coordination" below.
**Storage**: Neo4j 5.28 for `CoreRepository` / `CoreReadOnlyRepository` nodes; local filesystem worktrees for Git operations.
**Testing**: pytest 9.0 (unit + functional), Vitest 4.1 (frontend unit), Playwright 1.56 (E2E).
**Target Platform**: Linux server (backend + Prefect worker), modern browsers (frontend).
**Project Type**: Web application (backend + frontend + submoduled CLI).
**Performance Goals**:
- Marketplace list endpoint response < 2s at p95 (including upstream call + cache).
- Install workflow completes a typical single-schema install in < 15s.
- `/api/menu` unchanged in performance (new entry is a constant-cost addition).
**Constraints**:
- Cross-origin: frontend MUST NOT call `marketplace.infrahub.app` directly (CORS-restricted upstream).
- Install flow MUST be idempotent and leave the target repository unchanged on any failure before the commit lands.
- Generated files (`backend/infrahub/core/protocols.py`, `backend/infrahub/core/schema/generated/`, `frontend/app/src/shared/api/`) are regenerated, never hand-edited.
- Marketplace upstream performs download audit logging; pass file downloads through the proxy (do not cache bodies aggressively) to avoid undercounting.
**Scale/Scope**:
- Marketplace currently lists low-100s of schemas and <100 collections; pagination (cursor) must still be honored as catalog grows.
- One home-page tile, one new dedicated page, one backend router (3-5 endpoints), one Prefect workflow (reused/adapted), one new config field, one repointed home-page link.

### Resolved unknowns (from research.md)

- Marketplace API contract: REST at `/api/v1/*`, cursor pagination, anonymous read, no GraphQL. OpenAPI available at `/api/openapi.json`.
- Repository distinction: `CoreRepository` (writable, has `default_branch`) vs `CoreReadOnlyRepository` (has `ref`) are distinct kinds; filter by kind for writability.
- Git commit path: reuse `InfrahubRepository` + `Worktree`; commit logic from prior `tasks.py` is reusable, only download URLs change.
- Config: add a `MarketplaceSettings` subsection in `backend/infrahub/config.py` with `url: str = "https://marketplace.infrahub.app"` → env `INFRAHUB_MARKETPLACE_URL`. Chosen to match the env-var name used by the new `infrahubctl marketplace download` command (SDK PR #952) so a single exported variable configures both backend and CLI consistently.
- Frontend nav: menu is API-driven (`GET /api/menu`). Add the Schema Marketplace entry from the backend menu generator, not the frontend.
- CLI alternative: the `infrahubctl marketplace download` command (SDK PR #952) makes this clean — one command downloads by `namespace/name` (auto-detecting schema vs collection), and `infrahubctl schema load <dir>` applies the result. No curl step and no scope risk around URL support.
- `getObjectPermissions({ kind: "CoreRepository", branchName })` is the existing pattern for write-permission checks in the frontend.
- **SDK submodule coupling**: this feature depends on `opsmill/infrahub-sdk-python#952` (branch `knotty-dibble`) being merged (or the `python_sdk` submodule being bumped to that PR's commit) before release. Block final release of infp-528 on PR #952 landing.
- **SDK coordination — public `infrahub_sdk.marketplace` module**: the Infrahub backend imports Marketplace logic from the SDK, not from `infrahub_sdk/ctl/marketplace.py` (which is CLI-coupled via Typer/rich). PR #952 as-currently-structured keeps the Marketplace HTTP helpers private (`_detect_item_type`, `_download_schema`, `_download_collection`). A small refactor MUST expose them as a public module `infrahub_sdk.marketplace` with:
  - `class MarketplaceClient(base_url: str, http: httpx.AsyncClient | None = None)`
  - `async def list_schemas(search=None, tags=None, limit=20, after=None) -> SchemasListResponse`
  - `async def list_collections(...) -> CollectionsListResponse`
  - `async def get_schema(namespace, name) -> SchemaDetail`
  - `async def get_collection(namespace, name) -> CollectionDetail`
  - `async def list_tags() -> list[TagCount]`
  - `async def fetch_schema_content(namespace, name, version=None) -> bytes` (returns YAML bytes — no disk I/O, no `typer.Exit`, no `rich.Console`)
  - `async def fetch_collection_bundle(namespace, name) -> CollectionPayload` (parsed dict; no disk I/O)
  - Pydantic models for the list/detail responses, shared with the CLI layer.

  The CLI command (`infrahubctl marketplace download`) becomes a thin wrapper over this public module, handling disk writes and Typer-specific concerns. The Infrahub backend then imports `MarketplaceClient` directly into `backend/infrahub/marketplace/client.py` (which becomes a thin adapter — or is removed entirely) and into `backend/infrahub/marketplace/tasks.py` (replacing any HTTP code). This is a deliberate Principle VII application: one Marketplace client, shared between CLI and backend.

  Coordinate with the SDK PR author to either land the refactor on `knotty-dibble` pre-merge or open a follow-up PR immediately after. If the SDK refactor is not ready when the backend work starts, the backend work can proceed against a local copy of the public API (behind `backend/infrahub/marketplace/sdk_shim.py`) that gets deleted once the SDK exposes the real module.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Notes |
|---|-----------|--------|-------|
| I | Schema-Driven Integrity | ✅ PASS | Feature does not introduce new node kinds. Installed schemas are user content committed to a Git repo; existing repository-sync applies them to the graph through the schema layer. |
| II | Branch-Safe by Default | ✅ PASS | Install flow commits to a user-selected branch on the target repository; the Prefect workflow accepts `branch_name` and queries repo nodes with branch/temporal filters via existing SDK patterns. Merge behavior is "N/A — schemas flow into the graph via existing repo-sync, which is already branch-aware". Documented in `data-model.md`. |
| III | Type Safety & Explicit Contracts | ✅ PASS | New REST endpoints defined as Pydantic models (backend) and consumed via generated TS types (`pnpm codegen`). No `any` in frontend code. Contracts drafted before implementation (Phase 1). |
| IV | Test Discipline | ✅ PASS | Unit tests for marketplace client + models, functional tests for the proxy endpoints + install workflow, Vitest for frontend hooks/components, Playwright E2E for the full "install from Marketplace" golden path. Existing `InfrahubHTTP` adapter pattern lets us use an adapter rather than raw mocks. |
| V | Query Performance & Efficiency | ✅ PASS | No new Cypher beyond what the existing repo-lookup pattern uses. Marketplace list endpoint implements short-TTL in-memory cache (30s) to avoid N calls per page view. Downloads stream through the proxy (no full in-memory buffering of arbitrarily large bundles). |
| VI | Security & Input Boundaries | ✅ PASS | Proxy endpoints require `get_current_user`. Install endpoint validates: user is authenticated, target repository kind is `CoreRepository` (not read-only), user has write permission on that repo. Marketplace URL validated at startup (scheme `http`/`https`). No secrets committed. Marketplace proxy does not forward arbitrary user-controlled headers upstream. |
| VII | Simplicity & Maintainability | ✅ PASS | Reuses existing patterns: `InfrahubHTTP` for upstream HTTP, `WorkflowDefinition` for long-running install, `HomeCard` widget convention for the tile, TanStack Query for data fetching. No new dependencies. Prior wizard branch code is adapted rather than duplicated. |

**Complexity justification**: None required. All gates pass with no deviations.

## Project Structure

### Documentation (this feature)

```text
specs/infp-528-schema-marketplace-page/
├── plan.md              # This file
├── research.md          # Phase 0 output (consolidated findings)
├── data-model.md        # Phase 1 output (entities + state transitions)
├── quickstart.md        # Phase 1 output (dev/testing walkthrough)
├── contracts/
│   └── marketplace-proxy-api.md   # Phase 1 output (proxy REST contract)
└── checklists/
    └── requirements.md  # Already generated by /speckit.specify
```

### Source Code (repository root)

```text
backend/infrahub/
├── api/
│   ├── __init__.py                          # Mount marketplace router
│   └── marketplace.py                       # REWRITE — proxy endpoints (list, detail, content, install)
├── marketplace/
│   ├── __init__.py
│   ├── client.py                            # THIN ADAPTER — instantiates infrahub_sdk.marketplace.MarketplaceClient with the Infrahub-configured base_url + httpx client. May be dropped entirely if the SDK's client is a drop-in fit.
│   ├── models.py                            # DROP — reuse Pydantic models from infrahub_sdk.marketplace (single source of truth shared with the CLI).
│   ├── install_payload.py                   # NEW — workflow parameter model (frozen, Infrahub-internal)
│   └── tasks.py                             # ADAPT — Git commit flow reused; Marketplace I/O replaced by calls to infrahub_sdk.marketplace.MarketplaceClient.
├── config.py                                # ADD MarketplaceSettings subsection (INFRAHUB_MARKETPLACE_URL)
├── menu/
│   └── <generator>.py                       # ADD Schema Marketplace menu entry
└── workflows/
    └── catalogue.py                         # KEEP — MARKETPLACE_SCHEMA_INSTALL registration

backend/tests/
├── unit/marketplace/
│   ├── test_client.py                       # REWRITE — REST fixtures
│   └── test_models.py                       # REWRITE — new model shapes
├── functional/marketplace/
│   ├── test_api_marketplace.py              # NEW — proxy endpoint tests (auth, 502, filtering)
│   └── test_install_task.py                 # NEW — install workflow tests (success, rollback, wrong repo kind)
└── integration_docker/marketplace/
    └── test_install_e2e.py                  # NEW — full commit + repo-sync path

frontend/app/src/
├── pages/
│   └── schema-marketplace/
│       ├── index.tsx                        # NEW — route component, lazy-loaded
│       └── index.test.tsx
├── entities/
│   ├── schema-marketplace/
│   │   ├── api/
│   │   │   └── marketplace.queries.ts       # NEW — REST via fetchUrl + TanStack Query
│   │   ├── types.ts                         # NEW — TS types (ideally codegen'd from backend Pydantic)
│   │   ├── hooks/
│   │   │   ├── use-writable-repositories.ts # NEW — detects usable install targets
│   │   │   └── use-has-user-schemas.ts      # NEW — drives the tile CTA state
│   │   └── ui/
│   │       ├── marketplace-page.tsx         # NEW — list + detail + install drawer
│   │       ├── marketplace-schema-card.tsx  # NEW
│   │       ├── marketplace-collection-card.tsx # NEW
│   │       ├── install-drawer.tsx           # NEW — UI install panel (repo picker)
│   │       ├── cli-alternative.tsx          # NEW — infrahubctl command block with copy
│   │       └── prerequisite-state.tsx       # NEW — no-writable-repo state
│   └── homepage/ui/
│       ├── getting-started.tsx              # MODIFY — repoint "Schema Library" link to /schema-marketplace
│       └── schema-marketplace-widget.tsx    # NEW — HomeCard tile
├── app/router.tsx                           # MODIFY — add /schema-marketplace lazy route

frontend/app/tests/e2e/
└── schema-marketplace.spec.ts               # NEW — Playwright: no-repo blocked, install golden path, tile CTA

docs/docs/topics/
└── schema.mdx                               # MODIFY — add Schema Marketplace section + env var note

changelog/
└── +schema-marketplace.added.md             # NEW — towncrier fragment
```

**Structure Decision**: Web application layout (backend + frontend). The backend follows Infrahub's existing `api/ + <domain>/` split and registers a Prefect workflow via `workflows/catalogue.py`. The frontend follows Feature-Sliced (`src/pages/` + `src/entities/`). No new top-level directories are needed.

Generated files (`backend/infrahub/core/protocols.py`, `frontend/app/src/shared/api/`) regenerated after adding REST models; touched via `uv run invoke backend.generate` and `pnpm codegen`, not hand-edited.

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified.

None. Constitution Check passes with no deviations.

## Phases

### Phase 0 — Research (done)

See `research.md` for the consolidated findings from parallel research agents covering: current Marketplace API, Infrahub backend repository model + Git commit path, backend config pattern, frontend home-page structure + navigation, `infrahubctl schema` commands, and prior-branch reuse assessment.

All NEEDS CLARIFICATION resolved. No open questions blocking Phase 1.

### Phase 1 — Design & Contracts (done)

- `data-model.md` — entities, state transitions, validation rules.
- `contracts/marketplace-proxy-api.md` — REST proxy contract (methods, paths, request/response, error taxonomy).
- `quickstart.md` — developer walkthrough (run the backend, install a schema from Marketplace, verify in target repo).

### Phase 2 — Tasks (NOT in this command)

`/speckit.tasks` will decompose this plan into an ordered, dependency-aware task list. This command stops at the end of Phase 1.

## Known scope risks (deferred, not resolved)

1. **SDK PR #952 (`infrahubctl marketplace download`) must land before this feature ships**. The CLI alternative depends on it. Mitigation: `/speckit.tasks` will include an early task to bump the `python_sdk` submodule to either the merged commit or the `knotty-dibble` branch head for pre-merge testing. Coordinate with the SDK PR author (same team).
2. **Marketplace download audit logging** — caching downloads in the proxy would undercount; plan is to cache metadata only (short TTL, 30s) and stream file bodies through.
3. **Install progress granularity** — Prefect flow states are coarse (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`). If Product wants finer-grained stages (fetching / committing / pushing) surfaced, the task emits sub-state via Prefect artifacts. Default MVP uses the coarse states.
