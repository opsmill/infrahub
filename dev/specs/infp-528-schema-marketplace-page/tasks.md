---

description: "Task breakdown for infp-528 Schema Marketplace Integration"
---

# Tasks: Schema Marketplace Integration — Dedicated Page + Backend Proxy

**Input**: Design documents from `/specs/infp-528-schema-marketplace-page/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/marketplace-proxy-api.md](./contracts/marketplace-proxy-api.md), [quickstart.md](./quickstart.md)

**Tests**: Included. The Infrahub constitution (Principle IV — Test Discipline) requires unit, functional, and end-to-end coverage for every feature. The spec's "Independent Test" criteria per user story drive the test list.

**External coordination**: This feature depends on `opsmill/infrahub-sdk-python#952` (branch `knotty-dibble`) and a small follow-up SDK refactor that exposes a public `infrahub_sdk.marketplace` Python module. Flagged in T001–T003.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: User story this task serves (US1, US2, US3, US4, US5) — mirrors spec.md priorities
- File paths are absolute from the repo root

## Path Conventions

- **Backend**: `backend/infrahub/...`, `backend/tests/...`
- **Frontend**: `frontend/app/src/...`, `frontend/app/tests/...`
- **SDK submodule**: `python_sdk/...` (shared with `opsmill/infrahub-sdk-python`)
- **Docs / changelog**: `docs/`, `changelog/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Wire up the SDK dependency, scaffold new directories, establish the changelog fragment. No user story is blocked by this phase alone, but all stories depend on it.

- [ ] T001 Coordinate with SDK PR #952 author to refactor `infrahub_sdk/ctl/marketplace.py` into a public `infrahub_sdk.marketplace` module (class `MarketplaceClient` + list/detail/content helpers per plan.md "SDK coordination"). Track the SDK-side work as a linked issue; do NOT block T002.
- [ ] T002 Bump the `python_sdk` submodule pointer to the `knotty-dibble` branch HEAD (pre-merge) or the merged commit of PR #952. Commit submodule update separately in `python_sdk` with a message referencing infp-528.
- [ ] T003 If T001 is not yet landed, create `backend/infrahub/marketplace/sdk_shim.py` implementing the minimal public surface (`MarketplaceClient`, list/detail/content functions, Pydantic response models) locally. Delete when the SDK module is available.
- [X] T004 [P] Create backend feature directory: `backend/infrahub/marketplace/__init__.py` (empty) and remove any stale files left over from prior branches if present.
- [X] T005 [P] Scaffold frontend entity directory structure: `frontend/app/src/entities/schema-marketplace/{api,domain,hooks,ui,queries}/` with empty `index.ts` files following `dev/knowledge/frontend/entities-structure.md`.
- [X] T006 [P] Create Towncrier changelog fragment: `changelog/+schema-marketplace.added.md` with a one-line summary "Added a dedicated Schema Marketplace page with a backend proxy to install schemas from the Infrahub Marketplace."
- [ ] T007 [P] Delete stale unit test files from the prior wizard branch if they linger on disk: `backend/tests/unit/marketplace/test_client.py` and `backend/tests/unit/marketplace/test_models.py` (per research.md §R-2 — SDK owns these tests now).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Configuration, backend scaffolding, and routing infrastructure that every user story depends on.

**⚠️ CRITICAL**: No user-story phase can begin until this phase is complete.

### Backend config & routing

- [X] T008 Add `MarketplaceSettings` Pydantic settings subclass to `backend/infrahub/config.py` with `url: str = "https://marketplace.infrahub.app"` and `env_prefix="INFRAHUB_MARKETPLACE_"`. Attach as `marketplace: MarketplaceSettings = MarketplaceSettings()` on the top-level `Settings` class. Add a `@field_validator("url")` rejecting non-http(s) schemes with a WARNING (log only; do not raise — broken config still allows the backend to boot and surfaces via `/api/marketplace/status`).
- [X] T009 [P] Create `backend/infrahub/marketplace/install_payload.py` with Infrahub-internal install models per data-model.md §1.12–§1.13: `MarketplaceInstallItem`, `MarketplaceInstallRequest`, `MarketplaceInstallResponse`, `MarketplaceInstallPayload` (all frozen; branch_name, repository_id, items; payload mirrors request plus `marketplace_url`, `initiator_username`, `initiator_user_id`).
- [X] T010 [P] Create `backend/infrahub/marketplace/client.py` as a thin factory: `def make_marketplace_client(http: httpx.AsyncClient | None = None) -> MarketplaceClient` that resolves `config.SETTINGS.marketplace.url` and instantiates `infrahub_sdk.marketplace.MarketplaceClient` (or the `sdk_shim.py` equivalent). Keep this file small — its only job is URL resolution + wiring.
- [X] T011 Create `backend/infrahub/api/marketplace.py` with a FastAPI `APIRouter` (prefix `/api/marketplace`, `get_current_user` dependency on every endpoint). No endpoint bodies yet — just the router + dependency wiring.
- [X] T012 Mount the marketplace router from `backend/infrahub/api/__init__.py` (or wherever other routers are registered — check neighboring routers for the pattern).

### Backend menu entry

- [X] T013 [P] Locate the backend menu generator (the module that produces the response body for `GET /api/menu` — grep for `menu` under `backend/infrahub/menu/` or similar). Add a top-level Schema Marketplace entry pointing to `/schema-marketplace` with an appropriate icon (e.g., `store` or `package`) at a sensible position in the nav order.

### Frontend routing

- [X] T014 Register a lazy route for `/schema-marketplace` in `frontend/app/src/app/router.tsx` pointing at `src/pages/schema-marketplace/index.tsx` (page file itself is created in a later story phase; route registration is foundational).
- [X] T015 [P] Create a placeholder `frontend/app/src/pages/schema-marketplace/index.tsx` that renders a bare "Schema Marketplace" heading — lets the route resolve to a real component during foundation. Later stories replace the body.

### Shared data layer (no story-specific logic)

- [X] T016 [P] Create `frontend/app/src/entities/schema-marketplace/api/marketplace.queries.ts` with `fetchUrl`-based REST clients for `GET /api/marketplace/status`, `/schemas`, `/schemas/{ns}/{name}`, `/schemas/versions/{version_id}/content`, `/collections`, `/collections/{ns}/{name}`, `/tags`, plus `POST /api/marketplace/install` and `GET /api/marketplace/cli-snippet`. Types imported from the codegen'd `frontend/app/src/shared/api/rest/types.generated.ts`.
- [X] T017 [P] Create `frontend/app/src/entities/schema-marketplace/types.ts` re-exporting generated types plus the hand-written UI view models (`InstallDrawerState`, `CliAlternative`) per data-model.md §2.

### Codegen sweep

- [ ] T018 Run `uv run invoke backend.generate` to regenerate `backend/infrahub/core/protocols.py` and `backend/infrahub/core/schema/generated/`. Commit regenerated files.
- [ ] T019 Run `cd frontend/app && pnpm codegen` to regenerate `frontend/app/src/shared/api/rest/types.generated.ts` with the new marketplace models. Commit regenerated files.

### Permission helpers (shared across stories)

- [X] T020 [P] Create `frontend/app/src/entities/schema-marketplace/hooks/use-writable-repositories.ts` — TanStack Query hook returning the list of `CoreRepository` nodes the current user has write permission to (filters out `CoreReadOnlyRepository`, applies `getObjectPermissions({ kind: "CoreRepository", branchName }).update.isAllowed`).
- [X] T021 [P] Create `frontend/app/src/entities/schema-marketplace/hooks/use-has-user-schemas.ts` — returns `boolean` indicating whether any user-defined schema nodes exist on the active branch (drives the home-tile onboarding CTA state).

**Checkpoint**: Foundation ready. All user stories can now proceed. The placeholder page resolves; the menu entry appears; config is in place; the router exists.

---

## Phase 3: User Story 1 — Install initial schemas from a dedicated page (Priority: P1) 🎯 MVP

**Goal**: A fresh Infrahub instance (no user schemas) exposes the Schema Marketplace page, users can browse + install a first schema from a configured writable repo, and the install is committed via a Prefect workflow.

**Independent Test**: Start a blank Infrahub instance with one `CoreRepository` configured; confirm no modal appears on login, the home tile shows onboarding CTA, the page lists Marketplace items, and installing a schema produces a commit in the target repo.

### Backend — proxy read endpoints

- [X] T022 [P] [US1] Implement `GET /api/marketplace/status` in `backend/infrahub/api/marketplace.py` per contracts §7: returns `{marketplace_url, url_configured, url_scheme_valid, upstream_reachable, checked_at}`. Performs a 2s health-probe to upstream `/health`; swallows errors into the boolean.
- [X] T023 [P] [US1] Implement `GET /api/marketplace/schemas` in `backend/infrahub/api/marketplace.py` per contracts §1: proxies via `make_marketplace_client().list_schemas(search, tags, limit, after)`. 30s in-memory TTL cache keyed on query params. Map upstream errors per contracts "Error taxonomy" (502/504/500).
- [X] T024 [P] [US1] Implement `GET /api/marketplace/schemas/{namespace}/{name}` in `backend/infrahub/api/marketplace.py` per contracts §2. No caching. 404 translation when upstream returns 404.
- [X] T025 [P] [US1] Implement `GET /api/marketplace/schemas/versions/{version_id}/content` per contracts §3. No caching (avoid download-count undercount per plan.md risk #2).

### Backend — install endpoint + workflow

- [X] T026 [US1] Implement `POST /api/marketplace/install` in `backend/infrahub/api/marketplace.py` per contracts §8. Validation order: (1) Pydantic parse of `MarketplaceInstallRequest`; (2) resolve `repository_id` on the target branch; (3) 409 if resolved kind is `CoreReadOnlyRepository`; (4) 404 if branch missing; (5) 403 if user lacks write permission on the repo; (6) submit Prefect workflow; (7) return 202 with `task_id`.
- [X] T027 [P] [US1] Implement `install_marketplace_schemas` flow in `backend/infrahub/marketplace/tasks.py`: `@flow(name="marketplace-schema-install", flow_run_name="install-{items_summary}")`. Accepts `MarketplaceInstallPayload`. Orchestrates fetch → commit → push. Use `@task` sub-units for `fetch-marketplace-item` and `commit-schemas-to-repo`. All names kebab-case per `dev/knowledge/backend/async-tasks.md`.
- [X] T028 [US1] Add a `fetch-marketplace-item` `@task` in `backend/infrahub/marketplace/tasks.py` that calls `client.fetch_schema_content(namespace, name, version)` (or `fetch_collection_bundle` for collections) from `infrahub_sdk.marketplace`. Returns parsed YAML bytes + target filename. NO shelling out to `infrahubctl`.
- [X] T029 [US1] Add a `commit-schemas-to-repo` `@task` in `backend/infrahub/marketplace/tasks.py` that: obtains an `InfrahubRepository` for `repository_id`, opens a worktree on `branch_name`, writes schema files under `schemas/<name>.yml` (collections go under `schemas/<collection_name>/<schema_name>.yml`), auto-bootstraps `.infrahub.yml` if missing with `{schemas: [schemas]}`, stages + commits with author=initiator, pushes. On any exception: DO NOT push; worktree is cleaned up — repo remote is unchanged (FR-020).
- [X] T030 [US1] Register `MARKETPLACE_SCHEMA_INSTALL` in `backend/infrahub/workflows/catalogue.py` with `WorkflowDefinition(name="marketplace-schema-install", type=WorkflowType.CORE, module="infrahub.marketplace.tasks", function="install_marketplace_schemas")`. Confirm any existing stale entry from the prior branch is updated to the new function signature.

### Frontend — Marketplace page (list + install)

- [X] T031 [P] [US1] Create `frontend/app/src/entities/schema-marketplace/ui/marketplace-schema-card.tsx` — a tile rendering one `MarketplaceSchemaSummary` (name, description, version, tags). Pure; no hooks (per `dev/knowledge/frontend/react.md` — React Compiler handles memoization).
- [X] T032 [P] [US1] Create `frontend/app/src/entities/schema-marketplace/ui/install-drawer.tsx` — the repo picker + branch selector + confirm flow. Consumes `use-writable-repositories`; calls `POST /api/marketplace/install`; renders the `InstallDrawerState` machine (idle → submitting → pending → running → completed/failed). Polls task status via the existing task GraphQL query using the returned `task_id`.
- [X] T033 [P] [US1] Create `frontend/app/src/entities/schema-marketplace/ui/marketplace-page.tsx` — the main page body: list of `MarketplaceSchemaSummary` rendered as cards, click opens the install drawer. Uses TanStack Query on `fetchSchemas()`.
- [X] T034 [US1] Replace the placeholder in `frontend/app/src/pages/schema-marketplace/index.tsx` with a component that renders `<MarketplacePage/>` from `entities/schema-marketplace/ui`. Wrap in route-level suspense + error boundary.

### Frontend — home tile + repoint legacy link

- [X] T035 [P] [US1] Create `frontend/app/src/entities/homepage/ui/schema-marketplace-widget.tsx` — a `HomeCard` tile. Uses `use-has-user-schemas`: default label "Browse the Schema Marketplace"; when false, renders the onboarding-CTA state "Get started — install your first schema" (FR-003, FR-004). Links to `/schema-marketplace`.
- [X] T036 [P] [US1] Register the new widget in the home page layout file (`frontend/app/src/pages/homepage.tsx` or equivalent — grep for imports of `ProposedChangesWidget`, `GitRepositoriesWidget`). Place the tile in a reasonable grid slot matching existing `col-span-1` widgets.
- [X] T037 [US1] Modify `frontend/app/src/entities/homepage/ui/getting-started.tsx:115` — change the "Schema Library" link's `to` prop from `https://github.com/opsmill/schema-library/` to the internal route `/schema-marketplace`. Update the label too if it needs to track the Marketplace name (keep "Schema Library" or rename to "Schema Marketplace" — match the widget's label).

### Tests — US1

- [X] T038 [P] [US1] Unit test `backend/tests/unit/marketplace/test_install_payload.py` — validates `MarketplaceInstallRequest` (empty items rejected, >50 items rejected, malformed semver rejected, `kind` enum enforced).
- [ ] T039 [P] [US1] Functional test `backend/tests/functional/marketplace/test_api_marketplace_reads.py` — covers `GET /status`, `GET /schemas`, `GET /schemas/{ns}/{name}`, `GET /schemas/versions/{vid}/content`. Patch `infrahub_sdk.marketplace.MarketplaceClient` with an async adapter double (not a mock per Principle IV); assert error translation (502/504/404).
- [ ] T040 [P] [US1] Functional test `backend/tests/functional/marketplace/test_api_marketplace_install.py` — covers `POST /install` success (202 + task_id), 400 (empty items), 404 (missing repo), 409 (read-only repo), 403 (no write permission), 502 (upstream unreachable during pre-validation). Use real Prefect test harness; invoke the flow via `.fn` per testing.md:344-352.
- [ ] T041 [P] [US1] Functional test `backend/tests/functional/marketplace/test_install_task.py` — exercises the install flow on a test repository fixture: success writes files + commits + pushes; failure during fetch leaves repo untouched; failure during push leaves repo untouched (rollback invariant).
- [ ] T042 [P] [US1] Integration-Docker test `backend/tests/integration_docker/marketplace/test_install_e2e.py` — full stack: install a known marketplace schema into a fixture repo, verify the repo-sync pipeline picks it up and the schema appears in the graph.
- [ ] T043 [P] [US1] Frontend unit test `frontend/app/src/entities/schema-marketplace/ui/install-drawer.test.tsx` — renders each `InstallDrawerState`; assert transitions on mocked task-status responses.
- [ ] T044 [P] [US1] Frontend unit test `frontend/app/src/entities/homepage/ui/schema-marketplace-widget.test.tsx` — tile renders default label when `use-has-user-schemas` returns true; renders onboarding CTA when it returns false.
- [ ] T045 [P] [US1] Playwright E2E `frontend/app/tests/e2e/schema-marketplace-install.spec.ts` — Golden path per quickstart.md §3: fresh instance → home tile shows onboarding CTA → click → marketplace page lists items → pick one → pick writable repo → confirm → install succeeds → tile no longer shows onboarding CTA. Also assert no modal appears on any refresh.

**Checkpoint**: User Story 1 is fully functional and testable in isolation. MVP complete.

---

## Phase 4: User Story 2 — Install additional schemas after initial setup (Priority: P1)

**Goal**: An operator on an instance with existing schemas can install additional Marketplace schemas without any setup/first-run gating; duplicate installs are prevented.

**Independent Test**: On an instance with at least one schema already loaded, open `/schema-marketplace`, install a different schema into the same or a different repo, verify the new commit lands and existing schemas are untouched; attempt to install the same schema a second time — UI blocks with "already installed" indicator.

### Already-installed detection

- [ ] T046 [US2] Extend `backend/infrahub/api/marketplace.py` with a helper that, given a list of Marketplace identifiers, determines which are already committed under `schemas/` in any configured `CoreRepository` the user has read access to. Expose via a new field on the schema summary / detail responses (`already_installed: bool`, optional `installed_in: list[{repository_id, branch_name, path}]`). Per contracts §1-2.
- [X] T047 [P] [US2] Update `frontend/app/src/entities/schema-marketplace/ui/marketplace-schema-card.tsx` to render an "Already installed" badge and disable the install action when `already_installed=true`. FR-009.
- [ ] T048 [P] [US2] Update `install-drawer.tsx` to short-circuit: if the user clicks install on an already-installed schema, show a warning dialog instead of proceeding. FR-009.

### Tests — US2

- [ ] T049 [P] [US2] Functional test `backend/tests/functional/marketplace/test_already_installed.py` — detection helper returns `true` when schema is committed, `false` otherwise, and correctly scopes to repos the user can read.
- [ ] T050 [P] [US2] Playwright E2E `frontend/app/tests/e2e/schema-marketplace-additional.spec.ts` — Second install scenario: preload one schema, verify page is reachable without first-run flow, install a second different schema, assert the first is unchanged; attempt re-install of the first, assert blocked with the badge.

**Checkpoint**: User Stories 1 AND 2 both work independently. Initial + additional install paths covered.

---

## Phase 5: User Story 3 — Browse and compare schemas before installing (Priority: P2)

**Goal**: Users can discover schemas via list + detail views showing full descriptions, tag filters, search, and a preview of files that would be committed.

**Independent Test**: Open the page, apply a tag filter, search by text, open a detail view, verify the full description and file list render and match upstream.

### Backend — list/collection endpoints

- [X] T051 [P] [US3] Implement `GET /api/marketplace/collections` in `backend/infrahub/api/marketplace.py` per contracts §4 (cursor pagination, tag/search filtering).
- [X] T052 [P] [US3] Implement `GET /api/marketplace/collections/{namespace}/{name}` per contracts §5.
- [X] T053 [P] [US3] Implement `GET /api/marketplace/tags` per contracts §6 (returns `{tags: [{id, name, count}]}`).

### Frontend — browse UX

- [X] T054 [P] [US3] Create `frontend/app/src/entities/schema-marketplace/ui/marketplace-collection-card.tsx` — card variant for `MarketplaceCollectionSummary`.
- [ ] T055 [P] [US3] Create `frontend/app/src/entities/schema-marketplace/ui/marketplace-detail.tsx` — detail drawer/route showing full description, version list, and the file list that would be committed (FR-008).
- [X] T056 [US3] Extend `marketplace-page.tsx` with: (a) tag-filter sidebar driven by `/api/marketplace/tags`, (b) text search box wired to `/api/marketplace/schemas?search=`, (c) a tab or toggle for Schemas vs Collections, (d) cursor-based "Load more" pagination (do not use page numbers).

### Tests — US3

- [ ] T057 [P] [US3] Functional test `backend/tests/functional/marketplace/test_api_marketplace_browse.py` — lists + filtering + pagination cursor round-trips correctly.
- [ ] T058 [P] [US3] Frontend unit test `frontend/app/src/entities/schema-marketplace/ui/marketplace-page.test.tsx` — filters + search + pagination state transitions.
- [ ] T059 [P] [US3] Playwright E2E `frontend/app/tests/e2e/schema-marketplace-browse.spec.ts` — tag filter + search + detail view + file-list assertion.

**Checkpoint**: Browse/compare UX complete. Users can explore the full Marketplace before committing.

---

## Phase 6: User Story 4 — Blocked UI install when no writable repository, with CLI alternative (Priority: P1)

**Goal**: When no writable `CoreRepository` exists, install controls are disabled, the prerequisite state distinguishes "no repos" from "read-only only", and users see copy-pasteable `infrahubctl marketplace download` + `infrahubctl schema load` commands for their selection.

**Independent Test**: Per quickstart.md §4 — fresh instance OR read-only-only instance → open page → select schemas → confirm install is disabled, CLI alternative block is shown with commands; run commands locally and verify schemas apply.

### Backend — CLI snippet generator

- [X] T060 [US4] Implement `GET /api/marketplace/cli-snippet` in `backend/infrahub/api/marketplace.py` per contracts §9. Input: repeated `items` query param as `kind:ns/name@semver` + optional `branch_name` + optional `output_dir`. Output: `{downloads[], load_command, rendered}`. Generation rules: one `infrahubctl marketplace download <ns>/<name> [-v <semver>]` per schema; collections omit `-v`; all commands share `-o <dir>` only if non-default; trailing `infrahubctl schema load <dir> --branch <branch>`; inject `--marketplace-url <url>` if `INFRAHUB_MARKETPLACE_URL` differs from default.

### Frontend — prerequisite state + CLI alternative block

- [X] T061 [P] [US4] Create `frontend/app/src/entities/schema-marketplace/ui/prerequisite-state.tsx` — renders two distinct states based on `use-writable-repositories`: (a) "no repositories configured" with link to repo creation, (b) "all repositories are read-only" with distinct copy. Both states link to the repo management page. FR-022.
- [X] T062 [P] [US4] Create `frontend/app/src/entities/schema-marketplace/ui/cli-alternative.tsx` — fetches `/api/marketplace/cli-snippet` based on selection; renders per-line + full-block copy actions; includes the inline explanation from FR-033 about how the CLI path bypasses the Git commit requirement.
- [X] T063 [US4] Integrate prerequisite state + CLI alternative into `marketplace-page.tsx`: when `use-writable-repositories` returns an empty list, disable all install controls (install buttons hidden or disabled with tooltip), render `<PrerequisiteState/>` and `<CliAlternative selection={...}/>`. FR-019, FR-020, FR-021.
- [X] T064 [US4] Ensure the repository picker inside `install-drawer.tsx` filters out `CoreReadOnlyRepository` (FR-020) and repos the user lacks write permission on (FR-021). Read-only repos MAY appear in the picker as disabled with a tooltip "read-only — cannot install", but MUST NOT be selectable.

### Tests — US4

- [X] T065 [P] [US4] Functional test `backend/tests/functional/marketplace/test_cli_snippet.py` — exercises contracts §9 happy paths (single schema, multiple schemas, collection, custom output_dir, custom marketplace_url injection), rejects empty/oversize/malformed inputs with 400.
- [ ] T066 [P] [US4] Frontend unit test `frontend/app/src/entities/schema-marketplace/ui/prerequisite-state.test.tsx` — asserts the three branches: no repos, read-only-only, install-enabled. Assert distinct copy per branch.
- [ ] T067 [P] [US4] Frontend unit test `frontend/app/src/entities/schema-marketplace/ui/cli-alternative.test.tsx` — asserts per-line and full-block copy actions, rendering of `--version`, `-o`, `--marketplace-url` flags, and the FR-033 explanation block.
- [ ] T068 [P] [US4] Playwright E2E `frontend/app/tests/e2e/schema-marketplace-cli-alternative.spec.ts` — no-repos state: page shows prerequisite state + CLI block; select schemas and assert generated command matches expected pattern; copy to clipboard works. Read-only-only state: prerequisite copy distinguishes. Once a writable repo is added, install controls become enabled.

**Checkpoint**: Users are never dead-ended when they lack a writable repo. The CLI escape hatch works end-to-end.

---

## Phase 7: User Story 5 — Clear feedback on Marketplace and Git failures (Priority: P2)

**Goal**: Connectivity failures, install failures, and misconfiguration each surface clear actionable messages within bounded time; no indefinite spinners; failed installs leave repos unchanged.

**Independent Test**: Per quickstart.md §9 rollback scenarios — (a) block egress to Marketplace → page shows error within 10s; (b) set `INFRAHUB_MARKETPLACE_URL` to garbage → page shows config-error state; (c) abort Prefect flow mid-install → repo unchanged.

### Backend — error taxonomy audit

- [X] T069 [P] [US5] Audit all endpoints in `backend/infrahub/api/marketplace.py` for compliance with the contracts "Error taxonomy" table: every error path returns a JSON body with `{detail: "<machine-readable-code>"}`; error messages never leak tracebacks, DB structure, or upstream internals (Principle VI).
- [ ] T070 [P] [US5] Verify the Prefect install flow's failure mode emits a Prefect artifact capturing the failure reason + step, so the UI's task-status poll receives useful context (data-model.md §6).

### Frontend — error states

- [X] T071 [P] [US5] Create a connectivity-error state in `marketplace-page.tsx` triggered by 502/504 from `/api/marketplace/schemas`. Render within 10s (assert in T073).
- [X] T072 [P] [US5] Create a configuration-error state in `marketplace-page.tsx` triggered by `/api/marketplace/status` reporting `url_scheme_valid: false` or `url_configured: false`.
- [X] T073 [P] [US5] Update `install-drawer.tsx` to render a failure panel on task `FAILED` state, surfacing the Prefect artifact's failure context + a "retry" action.

### Tests — US5

- [ ] T074 [P] [US5] Functional test `backend/tests/functional/marketplace/test_error_paths.py` — every error code in the contracts table returns the documented `{detail: ...}`; no traceback leaks under any simulated upstream failure.
- [ ] T075 [P] [US5] Frontend unit test for error states in `marketplace-page.test.tsx` — connectivity error, config error, install-failed states render correctly and include action affordances.
- [ ] T076 [P] [US5] Playwright E2E `frontend/app/tests/e2e/schema-marketplace-errors.spec.ts` — blocks outbound marketplace traffic, asserts error state within 10s (SC-004); flips config env to an invalid URL, asserts config-error surfaces; induces Git push failure, asserts repo unchanged (SC-005).

**Checkpoint**: All failure modes have clean, bounded-time, user-actionable responses.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, docs site updates, final lint/format/type passes, and cross-story validation.

- [X] T077 [P] Add a "Schema Marketplace" section to `docs/docs/topics/schema.mdx` covering: what the Marketplace is, the home tile, how to install via UI, how to install via CLI for no-writable-repo scenarios (pointing to the new `infrahubctl marketplace download` command), and the `INFRAHUB_MARKETPLACE_URL` operator override.
- [ ] T078 [P] Add a Docusaurus reference entry for the env var `INFRAHUB_MARKETPLACE_URL` alongside other `INFRAHUB_*` settings in `docs/docs/reference/configuration.mdx`.
- [X] T079 [P] Update the changelog fragment `changelog/+schema-marketplace.added.md` with the final user-facing description (not the internal scope).
- [ ] T080 Run `uv run invoke format` and `uv run invoke lint` — fix any issues. Zero ruff / mypy errors per constitution.
- [ ] T081 Run `cd frontend/app && pnpm biome:fix && pnpm typecheck` — zero Biome or TS errors.
- [ ] T082 Run the full quickstart walkthrough end-to-end manually (quickstart.md §§1–9). Any discrepancy is a task to fix, not a doc patch.
- [ ] T083 Verify every acceptance scenario in spec.md §User Scenarios passes — spot-check US1–US5. Fix any gaps before calling the feature complete.
- [ ] T084 Confirm with the SDK PR #952 author that `infrahub_sdk.marketplace` is public on their branch; if so, delete `backend/infrahub/marketplace/sdk_shim.py` (if it existed) and bump the submodule to the merged commit. Re-run T018/T019 codegen.
- [ ] T085 [P] Accessibility pass on the new page and widget — keyboard navigation, ARIA roles on cards/drawer, color contrast on the "read-only" badges and the CLI-block copy button.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** — no dependencies; start immediately. T001 (SDK coordination) runs in parallel with T002–T007.
- **Foundational (Phase 2)** — depends on Setup. Blocks all user stories.
- **User Stories (Phases 3–7)** — all depend on Foundational. Can run in parallel if team capacity allows; otherwise sequentially.
- **Polish (Phase 8)** — depends on all user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Foundational only. No cross-story dependencies.
- **US2 (P1)**: Foundational only. Reuses US1's cards/drawer — soft dependency; tasks don't edit the same files simultaneously.
- **US3 (P2)**: Foundational only. Adds list/detail features independent of install flow.
- **US4 (P1)**: Foundational only. CLI snippet endpoint is standalone; prerequisite/cli-alternative components reuse US1's `use-writable-repositories`.
- **US5 (P2)**: Foundational only. Error handling is orthogonal to business flow; works once a proxy endpoint is in place.

All five stories can proceed in parallel after Phase 2 completes. The three P1 stories (US1, US2, US4) are the MVP scope.

### Within each story

- Tests per constitution (Principle IV) are written alongside implementation, not deferred. For backend: unit → functional → integration_docker. For frontend: vitest → Playwright E2E.
- Models before services before endpoints (Python).
- Domain hooks before UI components (frontend entity layering per `dev/knowledge/frontend/entities-structure.md`).

### Parallel Opportunities

- All [P] tasks in a phase run concurrently.
- Phase 1: T002 + T003 + T004 + T005 + T006 + T007 (only T001 is serial because it's external).
- Phase 2: T008 → (T009, T010, T013, T015, T016, T017, T020, T021 in parallel) → T011 → T012 → T014, T018, T019.
- Phases 3–7 can each have their backend and frontend sub-tracks worked on simultaneously by different developers.

---

## Parallel Example: User Story 1

```text
# Backend sub-track (one developer):
T022 [P] GET /status
T023 [P] GET /schemas
T024 [P] GET /schemas/{ns}/{name}
T025 [P] GET /schemas/versions/{vid}/content
# Serial: T026 → T027 → T028 → T029 → T030

# Frontend sub-track (another developer):
T031 [P] marketplace-schema-card.tsx
T032 [P] install-drawer.tsx
T033 [P] marketplace-page.tsx
# Serial: T034 (page entry) → T035 (tile) || T036 (layout) || T037 (link repoint)

# Testing sub-track (third developer):
T038–T045 all [P]
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 4 — the two blocking P1s)

1. Complete **Phase 1**: Setup (coordinate SDK, scaffold, changelog).
2. Complete **Phase 2**: Foundational (config, router, menu, hooks, codegen).
3. Complete **Phase 3 (US1)**: Golden-path install.
4. Complete **Phase 6 (US4)**: Blocked state + CLI alternative.
5. **STOP and VALIDATE**: fresh-instance + writable-repo → install; fresh-instance + no-repo → CLI path works.
6. Ship MVP.

### Incremental Delivery

1. MVP (US1 + US4) → ship.
2. Add US2 (additional-install + already-installed detection) → ship.
3. Add US3 (browse/filter) → ship.
4. Add US5 (error polish) → ship final.
5. Polish (Phase 8) bundled with final ship.

### Parallel Team Strategy

With three developers post-Phase-2:

- Dev A: US1 end-to-end (backend install + frontend drawer + tile).
- Dev B: US4 end-to-end (cli-snippet backend + prerequisite state + cli alternative).
- Dev C: US3 browse UX + US5 error polish.

US2 drops into Dev A's track after US1 since the code surfaces overlap.

---

## Notes

- [P] tasks touch different files and have no unmet dependencies on incomplete tasks.
- Every task states an exact file path; many of those files don't exist yet — creating them is part of the task.
- Per Principle IV, unit/functional/Playwright tests are required alongside implementation, not deferred.
- Per Principle I, never hand-edit generated files: regenerate via T018 / T019 / T084.
- Commit after each task or logical group. Use conventional commits (`feat(marketplace): ...`) per the git-workflow guideline.
- Submodule bumps (T002, T084) are separate commits from application code changes.
