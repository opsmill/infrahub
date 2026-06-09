<!-- markdownlint-disable MD013 -->
# Infrahub e2e suite (pytest-playwright + infrahub-testcontainers)

This is the Python e2e suite that is replacing the legacy TypeScript Playwright
suite (`frontend/app/tests/e2e/`). It drives the same browser flows with
[`pytest-playwright`](https://playwright.dev/python/docs/test-runners) but:

- spins up Infrahub with **infrahub-testcontainers** instead of
  `invoke dev.start dev.load-infra-schema dev.load-infra-data
  dev.infra-git-import dev.infra-git-create`, and
- loads the dataset through **composable pytest fixtures**, so every test
  declares exactly the data it needs.

The two CI jobs (`E2E-testing-playwright` and `E2E-testing-pytest-playwright`)
run side by side until this suite reaches parity; then the TypeScript job is
removed.

## Running

```bash
# Default: infrahub-testcontainers boots a fresh stack and the fixtures load data.
# Requires a local image: `uv run invoke dev.build`, then point testcontainers at it.
INFRAHUB_TESTING_IMAGE_VER=local INFRAHUB_TESTING_DOCKER_PULL=false \
  uv run pytest -c tests/e2e/pytest.ini tests/e2e

# Headed / debugging
INFRAHUB_TESTING_IMAGE_VER=local INFRAHUB_TESTING_DOCKER_PULL=false \
  uv run pytest -c tests/e2e/pytest.ini tests/e2e --headed --browser chromium

# Against an already-running, already-provisioned Infrahub (e.g. one started
# the old way with `invoke dev.start dev.load-infra-*`). The container is NOT
# booted and the data fixtures become no-ops.
INFRAHUB_ADDRESS=http://localhost:8000 \
  uv run pytest -c tests/e2e/pytest.ini tests/e2e
```

`-c tests/e2e/pytest.ini` is required: it isolates this suite from the root
`pyproject.toml` pytest config (coverage, xdist, asyncio-auto, global timeout).

Run **single-process** (no `pytest -n`): the Infrahub stack is a session-scoped
fixture, so each `pytest-xdist` worker would boot its own container. The legacy
TS suite ran 4 workers against one shared server; the equivalent here is one
process driving one stack.

## Architecture

```
tests/e2e/
  pytest.ini          # dedicated config (browser, artifacts, junit, maxfail)
  conftest.py         # stack + client + data fixtures + auth + role pages
  constants.py        # credentials, admin token, base-schema file list
  helpers.py          # login(), generate_random_branch_name(), BranchAPI
  test_login.py       # ported login.spec.ts
  branches/           # ported branches/*.spec.ts
  objects/            # ported objects/**/*.spec.ts
```

The suite lives at the repo root (`tests/e2e/`) and **not** under
`backend/tests/` on purpose: `backend/tests/conftest.py` has autouse session
fixtures that start an in-process backend, which we must not inherit.

### Fixture catalog

The harness is fully **synchronous** (sync SDK client + sync `infrahubctl`
subprocesses) so it coexists cleanly with pytest-playwright's synchronous
`page` fixture — no event-loop juggling.

| Fixture | Scope | Replaces | Notes |
|---|---|---|---|
| `infrahub_app` / `infrahub_port` / `infrahub_address` | session | `invoke dev.start` | One stack for the whole session. Honors `INFRAHUB_ADDRESS` if set. |
| `infrahub_client` | session | — | Admin `InfrahubClientSync`. |
| `schema_base` | session | `invoke dev.load-infra-schema` (schema) | Loads all `models/base/*.yml` as one set. |
| `infrastructure_menu` | session | `invoke dev.load-infra-schema` (menu) | `infrahubctl menu load models/base_menu.yml`. |
| `infrastructure_data` | session | `invoke dev.load-infra-data` | Runs the real `models/infrastructure_edge.py` (medium profile: 5 sites, 6 devices/site, BGP mesh, 5 branch scenarios) — byte-faithful to today's dataset, not a reimplementation. |
| `demo_edge_repo` | session | `invoke dev.infra-git-import dev.infra-git-create` | Registers + syncs the `demo-edge` repo via the SDK `GitRepo` helper. |
| `branch_api` | function | `tests/e2e/utils/graphql.ts` | Create/merge/delete throwaway branches via the API. |
| `page` | function | anonymous Playwright page | Unauthenticated; base URL points at the stack. |
| `admin_page` / `read_write_page` / `read_only_page` | function | `test.use({ storageState })` | Logged-in pages; storage states are built once per role by `login()` (port of `auth.setup.ts`). |

A test depends only on the fixtures it needs:

- `merge-branch` needs no demo data → uses `branch_api` + `admin_page` only.
- `login` (token refresh / initial-page redirect) needs the tag `blue` and the
  `atl1-delete-upstream` branch → depends on `infrastructure_data`.
- `object-list` needs tags/groups/devices → depends on `infrastructure_data`.

## Porting a TypeScript spec — recipe

1. **Locate the data dependency** (see taxonomy below) and pick the fixtures.
   Self-contained spec → `branch_api` + a role page. Needs demo objects →
   add `infrastructure_data`. Needs the repo/artifacts → add `demo_edge_repo`.
2. **Pick the page**: `test.use({ storageState: ADMIN })` → `admin_page`;
   READ_WRITE → `read_write_page`; READ_ONLY → `read_only_page`; no
   `storageState` → the default `page`.
3. **Translate the calls** (Playwright TS → Python):

   | TypeScript | Python |
   |---|---|
   | `page.getByRole("button", { name: "x", exact: true })` | `page.get_by_role("button", name="x", exact=True)` |
   | `page.getByText("x")` / `getByLabel` / `getByTestId` | `page.get_by_text("x")` / `get_by_label` / `get_by_test_id` |
   | `page.locator("#id")` | `page.locator("#id")` |
   | `await expect(loc).toBeVisible()` | `expect(loc).to_be_visible()` |
   | `.not.toBeVisible()` / `.toBeDisabled()` / `.toContainText()` | `.not_to_be_visible()` / `.to_be_disabled()` / `.to_contain_text()` |
   | `loc.first()` | `loc.first` |
   | `page.route(url, async route => …)` | `page.route(url, handler)` (sync handler) |
   | `route.fetch()` / `route.fulfill({json})` / `route.fallback()` | `route.fetch()` / `route.fulfill(json=…)` / `route.fallback()` |
   | `context.waitForEvent("page")` | `with context.expect_page() as info: …; info.value` |
   | `{ timeout: 5*60*1000 }` | `to_be_visible(timeout=5 * 60 * 1000)` |
   | `createBranchAPI(request, name)` | `branch_api.create(name)` |

4. **Branch lifecycle**: replace `beforeAll`/`afterAll` branch create/delete
   with a function-scoped fixture (see `TestObjectList.branch_name`).
5. **Naming**: one `Test…` class per `test.describe`, one `test_…` method per
   `test(...)`. Keep `test.step` blocks as inline comments.
6. Run `uv run ruff check tests/e2e && uv run ruff format tests/e2e`, then the spec.

## Data-dependency taxonomy (from the legacy suite)

- **(a) Self-contained** — create+delete their own branch and objects
  (`branches/merge-branch`, most `objects/list/*`, `object-template/*`,
  `role-management/*`, `objects/hierarchy/*`, `file-upload`). Need only the
  stack + `branch_api`.
- **(b) Branch-isolated but rely on common seeded objects** — devices
  `atl1-*`, tags `blue/green/red`, prefixes `10.x`, ASNs (most `objects/*`,
  `ipam` pool specs). Need `infrastructure_data`.
- **(c) Depend on specific pre-seeded branches** — `atl1-delete-upstream`,
  `den1-maintenance-conflict`, `platform-conflict` (`branches/*`, `breadcrumb`,
  `login`, `activities/global-activities-filters`, `proposed-changes_*`). Need
  `infrastructure_data`.
- **(d) Mutate main / leave residue** — `objects/profiles/multi-profiles`,
  `resource-manager/resource-pool`, `webhook`, `triggers`, docs tutorials.
  Order/isolation matters; prefer their own branch or run last.
- **(e) External / heavy infra** — `repository/repository-objects` (clones a
  GitHub repo), `objects/artifact*`, `proposed-changes` checks/diff. Need
  `demo_edge_repo` and async-effect polling.

## Migration status

Pilot complete (this PR): `login`, `branches/merge-branch`,
`objects/list/object-list` — proving auth, the branch lifecycle, CRUD,
navigation, route mocking, and both no-data and full-data fixture paths.

Remaining domains to port (counts from the legacy suite, 80 specs total):
`objects` 26 (list 6, hierarchy 4, profiles 3, convert/file-upload/CoreGraphQLQuery 1 each, 8 top-level),
`ipam` 9, `role-management` 5, `docs-regression-check` 5, `branches` 5 (1 done),
`object-template` 4, root-level 4 (1 done: login), `proposed-changes` 3,
`activities` 3, `schema` 2, `resource-manager` 2, `profile` 2, `groups` 2,
`form` 2, `webhook` 1, `triggers` 1, `tasks` 1, `repository` 1, `menu` 1,
`events` 1.

Carry over the legacy suite's skips as `@pytest.mark.skip` so coverage maps
1:1: `tasks/tasks-view`, `docs-regression-check/guides/resource_manager_guide`,
`events/events-rules-actions`, `triggers` "update the matches",
`proposed-changes` comment/merge sub-tests (all `fixme` today).

### Not yet ported from the harness

- **`docs-regression-check`** ran as a serial, single-worker Playwright project
  after the main suite, gated on `UPDATE_DOCS_SCREENSHOTS`. Port as a separately
  marked, serial group with a `save_screenshot_for_docs` helper writing to
  `docs/docs/media/`.
- **Response-delay stress mode** (`INFRAHUB_MISC_RESPONSE_DELAY=1`): the legacy
  job generated artifacts against a fast backend, then restarted Infrahub with a
  1s/GraphQL-request delay. With testcontainers, set the env before the stack
  boots (no restart needed) and widen Playwright's expect timeout when active.
