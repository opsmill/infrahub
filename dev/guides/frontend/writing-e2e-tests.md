# Writing E2E Tests

> Part of: `dev/guides/frontend/` | Related: [Component Tests](writing-component-tests.md), [Unit Tests](writing-unit-tests.md), [`tests/e2e/README.md`](../../../tests/e2e/README.md)

Step-by-step guide for writing end-to-end tests following the project's testing patterns and best
practices. The suite lives at the repo root in `tests/e2e/` and is written in Python with
[pytest-playwright](https://playwright.dev/python/) (async API); the stack is booted by
`infrahub-testcontainers` and the demo dataset is loaded by composable pytest fixtures. This guide
covers how to write a test; the suite's architecture, fixture catalog, and dataset slices are
documented in [`tests/e2e/README.md`](../../../tests/e2e/README.md).

## When to Write E2E Tests

Write E2E tests when you need to:

- Test full user workflows across multiple pages (create, edit, delete)
- Verify role-based access control (admin vs read-only)
- Test features that depend on backend state (branches, GraphQL API)
- Validate form submissions that persist data
- Test file uploads, downloads, or other browser-level interactions

**Note**: For testing isolated components, see [Writing Component Tests](writing-component-tests.md).
E2E tests should cover integration flows, not individual component behavior.

## Minimum bar for new pages

Every new page added under `frontend/app/src/pages/` ships with **at least one happy-path E2E test**
that exercises the full flow:

1. Navigate to the page.
2. Perform the primary user action (select inputs, submit, etc.).
3. Assert the resulting rendered output (rows, nodes, charts, count, etc.).

A test that only checks static text visibility ("page heading is visible") does not satisfy this bar.
Without an end-to-end assertion on rendered data, regressions in fetch logic, query key invalidation,
or visualization wiring can ship undetected.

For features with multiple modes (e.g. a `mode=path` vs `mode=impact` toggle), the happy path for
each mode counts as one test.

## Prerequisites

- Understanding of the [Playwright Python](https://playwright.dev/python/) test framework
- Familiarity with the Infrahub UI and object model
- A running Docker daemon and a locally built Infrahub image (`uv run invoke dev.build`), or an
  already-running Infrahub instance via `INFRAHUB_ADDRESS` — see the
  [Running section of the suite README](../../../tests/e2e/README.md#running)

## Test Structure

### File Organization

Tests live in `tests/e2e/` (repo root) organized by feature domain:

```text
tests/e2e/
  pytest.ini          # dedicated config -- always run with `-c tests/e2e/pytest.ini`
  conftest.py         # stack + client + data fixtures + auth + role pages
  helpers.py          # login(), generate_random_branch_name(), BranchAPI, Deadline, ...
  data/               # the demo dataset as composable async-SDK fixtures
  objects/            # object CRUD, details, relationships
  branches/           # branch management
  proposed-changes/   # proposed change workflows
  ipam/               # IPAM-specific features
  tutorial/           # docs tutorials/guides -- separate CI invocation, runs last
```

**File naming**: Use `test_snake_case.py` matching the feature name (e.g. `test_object_update.py`,
`test_merge_branch.py`).

### Basic Test File

```python
"""One-paragraph docstring: what the file covers and which data it relies on."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from playwright.async_api import expect

from helpers import generate_random_branch_name

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import OrgRegistryHandle
    from helpers import BranchAPI
    from playwright.async_api import Page


class TestMyFeature:
    @pytest.fixture
    async def branch(self, branch_api: BranchAPI, data_org_registry: OrgRegistryHandle) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("my-feature")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_should_do_something(self, admin_page: Page, branch: str) -> None:
        # navigate to the page
        await admin_page.goto(f"/objects/InfraDevice?branch={branch}")

        # perform the action
        await admin_page.get_by_test_id("create-object-button").click()

        # verify the result
        await expect(admin_page.get_by_text("Device created")).to_be_visible()
```

The whole suite is **async**: every test is `async def`, every Playwright action and assertion is
awaited, and everything shares one session-scoped event loop. Never call blocking functions
(`time.sleep`, sync SDK clients) inside a test — they stall the loop for the whole session.

### Classes and comments

Use one `Test...` class per user-facing flow (the port kept one class per legacy `describe` block)
and one `test_...` method per scenario. Where the legacy suite used `test.step()`, use plain inline
comments to mark the phases of a long test.

### Shard marker (required)

Every test file declares exactly one module-level shard marker matching the deepest data slice it
needs — a collection hook fails the run otherwise:

```python
pytestmark = pytest.mark.shard_foundation   # leaf slices only, never loads data_sites
```

The markers (`shard_foundation`, `shard_sites_a`, `shard_sites_b`, `shard_branches_repo`) map to the
4 parallel CI jobs; pick by data tier, see `tests/e2e/pytest.ini` and
`dev/specs/e2e-pytest-sharding.md`.

## Data

### Declare exactly the data you need

The demo dataset is decomposed into session-scoped fixtures (`data_rbac`, `data_org_registry`,
`data_sites`, `data_topology`, ... up to the full `infrastructure_data`), each returning a typed
handle of name→id maps. Depend on the **shallowest** slice that satisfies the test — that keeps the
per-domain stacks fast and the CI shards balanced. The fixture catalog and the slice DAG live in
[`tests/e2e/README.md`](../../../tests/e2e/README.md#fixture-catalog).

### Branch-per-test-file pattern

Every test file should create its own branch to isolate data mutations, via a function-scoped
fixture wrapping `branch_api` (see the basic test file above), then navigate with the branch query
parameter:

```python
await admin_page.goto(f"/objects/InfraDevice?branch={branch}")
```

Use `generate_random_branch_name(prefix)` to avoid collisions. It appends a **hex** suffix on
purpose: Playwright's `name=` option substring-matches, and the branch selector renders the current
branch name on every page, so a suffix that can spell a word the suite locates by (like "save")
would make locators ambiguous. Don't replace it with a random-word or base36 suffix.

### No serial mode — make each test self-contained

pytest's definition order is **not contractual** (fixture parametrization, `pytest-randomly`, and
`pytest-xdist` all reshuffle it), so don't depend on one test's side effects in another. Each test
creates the branches/objects it needs in its own fixture (or inline via `branch_api`) and cleans up
in the fixture teardown. A legacy setup-only "test" (no assertions, just creating a branch) becomes
inline setup rather than a separate test.

## Authentication

Four page fixtures are available; pick per test by parameter, mirroring the legacy
`test.use({ storageState })` blocks:

```python
async def test_anonymous(self, page: Page) -> None: ...            # not logged in
async def test_as_admin(self, admin_page: Page) -> None: ...       # full permissions
async def test_as_editor(self, read_write_page: Page) -> None: ... # standard permissions
async def test_as_viewer(self, read_only_page: Page) -> None: ...  # view only
```

The storage states are built once per role by `helpers.login()`; the read-write/read-only roles need
only the `data_rbac` slice (their accounts), not the full dataset. Test different roles as separate
test methods (or separate classes) rather than nesting.

## Selectors

Use selectors in this priority order:

### 1. `get_by_test_id` (preferred for structural elements)

```python
page.get_by_test_id("create-object-button")
page.get_by_test_id("object-items")
```

### 2. `get_by_role` (preferred for interactive elements)

```python
page.get_by_role("button", name="Save")
page.get_by_role("link", name="atl1-core1")
page.get_by_role("option", name="Active")
page.get_by_role("textbox", name="Name *")
page.get_by_role("combobox", name="Site")
```

### 3. `get_by_label` (for form inputs)

```python
page.get_by_label("Name *")
page.get_by_label("Description")
```

### 4. `get_by_text` (for content verification)

```python
page.get_by_text("Device created")
page.get_by_text("No data found")
```

### 5. CSS selectors (last resort)

```python
page.locator('input[type="file"]')
page.locator("#alert-success-Tenant-created")
```

### Scoping Selectors

Scope selectors to containers to avoid ambiguity:

```python
page.get_by_test_id("object-items").get_by_role("link", name="my-tenant")
```

Use `exact=True` when name matching could be ambiguous:

```python
page.get_by_role("link", name="Cisco IOS", exact=True)
```

When a regex name matcher contains a literal `/`, escape it (`\/`) — Playwright serializes the
pattern into a `/.../`-delimited selector and an unescaped slash ends it early:

```python
page.get_by_role("link", name=re.compile(r"10\.0\.0\.0\/16.*IP Prefix"))
```

## Assertions

### Visibility (most common)

```python
await expect(element).to_be_visible()
await expect(element).not_to_be_visible()
await expect(element).to_be_hidden()
```

### Content

```python
await expect(element).to_contain_text("some text")
await expect(element).to_have_text("exact text")
await expect(input_locator).to_have_value("value")
```

### State

```python
await expect(button).to_be_enabled()
await expect(button).to_be_disabled()
await expect(checkbox).to_be_checked()
```

### URL

```python
await expect(page).to_have_url(re.compile(r".*\?branch=cr1234"))
```

### Count

```python
await expect(page.get_by_test_id("identifier-checkbox-cell")).to_have_count(3)
```

## Waiting

Rely on Playwright's auto-waiting through `expect()` assertions. Avoid explicit waits unless
absolutely necessary — and never `time.sleep()` (it stalls the shared event loop).

### Custom Timeouts for Long Operations

```python
await expect(page.get_by_text("Merge completed")).to_be_visible(timeout=5 * 60 * 1000)
```

### Polling for Async Backend Processing

Reload-poll loops must be bounded — use the `Deadline` helper from `helpers.py`, which raises with a
descriptive message when the budget runs out and yields to the event loop between attempts:

```python
deadline = Deadline("activity to be indexed", timeout=180.0)
while await page.get_by_text("No activity found").is_visible():
    await deadline.tick()
    await page.reload()
    await expect(page.get_by_text("Loading...")).to_be_hidden()
```

## Test Annotations

### Skipping Known Broken Tests

Use `pytest.mark.skip` with a reason that names the cause (the equivalent of the legacy
`test.fixme`):

```python
@pytest.mark.skip(reason="flaky upstream ordering, see #1234")
async def test_broken(self, admin_page: Page) -> None: ...
```

## Shared Utilities

`tests/e2e/helpers.py` is the shared toolbox:

- `generate_random_branch_name(prefix)` — collision-free, locator-safe branch names
- `BranchAPI` (via the `branch_api` fixture) — create/merge/delete throwaway branches over the API
- `Deadline` — bounded reload-poll loops
- `login(page, username, password)` — the storage-state builder (rarely needed directly)
- `get_data_table_row(page, name)` — locate a data-table row by its link name
- `select_combobox_option(page, label, option)` / `select_pool(page, pool_name)` — form helpers
- `save_screenshot_for_docs(page, filename)` — docs screenshots
  (`UPDATE_DOCS_SCREENSHOTS=1`, tutorial suite)

Keep new helpers generic and not tied to a specific schema or object type. For form-filling helpers
specific to a test domain, colocate them with the tests that use them.

## Common Patterns

### CRUD Workflow

```python
# Create
await page.get_by_test_id("create-object-button").click()
await page.get_by_label("Name *").fill("new-name")
await page.get_by_role("button", name="Save").click()
await expect(page.get_by_text("Tag created")).to_be_visible()

# Edit (from list)
await page.get_by_test_id("actions-cell-my-object").click()
await page.get_by_role("menuitem", name="Edit").click()

# Edit (from detail page)
await page.get_by_test_id("edit-button").click()

# Delete
await page.get_by_test_id("object-details-menu").click()
await page.get_by_role("menuitem", name="Delete").click()
await page.get_by_test_id("modal-delete-confirm").click()
```

### Dropdown/Select

```python
await page.get_by_label("Status").click()
await page.get_by_role("option", name="Maintenance").click()
```

### 500 Error Guard

Collect unexpected server errors during a flow and assert none happened. Register the listener
inside the (async) test or an async fixture — listener registration goes through the Playwright
connection and needs the running loop:

```python
def _install_500_guard(page: Page) -> list[str]:
    server_errors: list[str] = []

    def _record_500(response: Response) -> None:
        if response.status == 500:
            server_errors.append(response.url)

    page.on("response", _record_500)
    return server_errors


async def test_flow(self, admin_page: Page) -> None:
    server_errors = _install_500_guard(admin_page)
    ...
    assert not server_errors
```

## Running Tests

Run every command below from the **repository root** (not `frontend/app`). Always pass
`-c tests/e2e/pytest.ini` (it isolates the suite from the root pytest config) and run
single-process — the stack is a session fixture. Full invocations, including the
`INFRAHUB_TESTING_IMAGE_VER` / `INFRAHUB_ADDRESS` modes and response-delay runs, are in the
[suite README](../../../tests/e2e/README.md#running).

```bash
# All E2E tests (against a locally built image)
INFRAHUB_TESTING_IMAGE_VER=local INFRAHUB_TESTING_DOCKER_PULL=false \
  uv run pytest -c tests/e2e/pytest.ini tests/e2e

# A specific test file
INFRAHUB_TESTING_IMAGE_VER=local INFRAHUB_TESTING_DOCKER_PULL=false \
  uv run pytest -c tests/e2e/pytest.ini tests/e2e/objects/test_object_update.py

# Headed browser
INFRAHUB_TESTING_IMAGE_VER=local INFRAHUB_TESTING_DOCKER_PULL=false \
  uv run pytest -c tests/e2e/pytest.ini tests/e2e --headed --browser chromium
```

When debugging a failure locally, run with `--pdb` (see the root `AGENTS.md`): a failure freezes the
session with the testcontainers stack, the SDK clients, and the browser page still alive, so you can
inspect the live stack from a second shell instead of re-running the whole boot.

Failed authenticated tests leave a trace/video/screenshot under `test-results/`.

## Best Practices

### Do

- Create a branch per test file (via a fixture) for data isolation
- Depend on the shallowest data slice that satisfies the test
- Declare the file's shard marker (`pytestmark = pytest.mark.shard_<name>`)
- Structure long tests with inline phase comments
- Scope selectors to containers to avoid ambiguity
- Test multiple user roles when permissions matter
- Use `generate_random_branch_name()` to avoid branch name collisions
- Rely on Playwright's auto-waiting instead of explicit waits
- Use `get_by_test_id` and `get_by_role` as primary selectors
- Run `uv run ruff check tests/e2e && uv run ruff format tests/e2e` before committing

### Don't

- Don't use hardcoded branch names that could collide across runs
- Don't rely on data created by other tests or test files — pytest ordering is not contractual
- Don't use `page.wait_for_timeout()` or `time.sleep()` — use assertions that auto-wait
- Don't use `networkidle` waits (fragile and slow)
- Don't write unbounded reload-poll loops — use `Deadline`
- Don't test component-level behavior — use component tests for that
- Don't leave test data behind — clean up in the fixture teardown
- Don't use `input[name="..."]` selectors — prefer `get_by_label` or `get_by_role("textbox")`

## Quality Checklist

Before submitting your E2E tests:

- [ ] Test file is in the correct domain directory under `tests/e2e/` and named `test_snake_case.py`
- [ ] The file declares exactly one shard marker matching its data tier
- [ ] Tests depend on the shallowest data-slice fixtures they need
- [ ] Tests create and delete their own branch (fixture) for data isolation
- [ ] Each test is self-contained — no reliance on ordering or another test's side effects
- [ ] Authentication is chosen via the page fixture (`page` / `admin_page` / `read_write_page` / `read_only_page`)
- [ ] Selectors follow the priority order (testId > role > label > text > CSS) and are scoped when needed
- [ ] No blocking calls or unbounded polling — assertions auto-wait, loops use `Deadline`
- [ ] Multiple user roles are tested when permissions matter
- [ ] `ruff check` and `ruff format` pass on `tests/e2e`

## Related Resources

- [`tests/e2e/README.md`](../../../tests/e2e/README.md) — suite architecture, fixture catalog,
  dataset slices, running modes, and the TS→Python porting recipe
- [Writing Component Tests](writing-component-tests.md) — React component tests
- [Writing Unit Tests](writing-unit-tests.md) — TypeScript function tests
- `tests/e2e/helpers.py` — shared helpers (branches, deadlines, form helpers)
- `tests/e2e/pytest.ini` — suite configuration and shard marker registry
- Playwright Python documentation — [playwright.dev/python](https://playwright.dev/python/)
