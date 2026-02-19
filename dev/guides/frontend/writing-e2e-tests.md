# Writing E2E Tests

> Part of: `dev/guides/frontend/` | Related: [Component Tests](writing-component-tests.md), [Unit Tests](writing-unit-tests.md)

Step-by-step guide for writing Playwright end-to-end tests following the project's testing patterns and best practices.

## When to Write E2E Tests

Write E2E tests when you need to:

- Test full user workflows across multiple pages (create, edit, delete)
- Verify role-based access control (admin vs read-only)
- Test features that depend on backend state (branches, GraphQL API)
- Validate form submissions that persist data
- Test file uploads, downloads, or other browser-level interactions

**Note**: For testing isolated components, see [Writing Component Tests](writing-component-tests.md). E2E tests should cover integration flows, not individual component behavior.

## Prerequisites

- Understanding of [Playwright](https://playwright.dev/) test framework
- Familiarity with the Infrahub UI and object model
- A running Infrahub instance (local or CI)

## Test Structure

### File Organization

Tests live in `frontend/app/tests/e2e/` organized by feature domain:

```text
tests/e2e/
  objects/           # Object CRUD, details, relationships
  branches/          # Branch management
  proposed-changes/  # Proposed change workflows
  ipam/              # IPAM-specific features
  form/              # Form interaction patterns
  utils/             # Shared helper functions
  auth.setup.ts      # Authentication setup project
```

**File naming**: Use `kebab-case.spec.ts` matching the feature name (e.g., `object-update.spec.ts`, `merge-branch.spec.ts`).

### Basic Test File

```typescript
import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";

const BRANCH_NAME = generateRandomBranchName("my-feature");

test.describe("/objects/InfraDevice - My Feature", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.beforeAll(async ({ request }) => {
    await createBranchAPI(request, BRANCH_NAME);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test("should do something", async ({ page }) => {
    await test.step("navigate to the page", async () => {
      await page.goto(`/objects/InfraDevice?branch=${BRANCH_NAME}`);
    });

    await test.step("perform the action", async () => {
      await page.getByTestId("create-object-button").click();
    });

    await test.step("verify the result", async () => {
      await expect(page.getByText("Device created")).toBeVisible();
    });
  });
});
```

### Describe Blocks

Use URL paths or feature names for describe block labels:

```typescript
test.describe("/objects/:objectKind/:objectId", () => { ... });
test.describe("Branch - Merge action", () => { ... });
```

### Test Steps

Use `test.step()` to break long tests into readable phases:

```typescript
test("should create and verify an object", async ({ page }) => {
  await test.step("navigate to list page", async () => { ... });
  await test.step("open create form", async () => { ... });
  await test.step("fill in required fields", async () => { ... });
  await test.step("save and verify", async () => { ... });
});
```

Step names should use present-tense imperative descriptions.

## Data Isolation

### Branch-per-Test-File Pattern

Every test file should create its own branch to isolate data mutations:

```typescript
const BRANCH_NAME = generateRandomBranchName("feature-prefix");

test.beforeAll(async ({ request }) => {
  await createBranchAPI(request, BRANCH_NAME);
});

test.afterAll(async ({ request }) => {
  await deleteBranchAPI(request, BRANCH_NAME);
});
```

Then navigate with the branch query parameter:

```typescript
await page.goto(`/objects/InfraDevice?branch=${BRANCH_NAME}`);
```

Use `generateRandomBranchName(prefix)` to avoid collisions when tests run in parallel.

### Serial Mode

When tests in a describe block depend on each other (e.g., create then update then delete), configure serial mode:

```typescript
test.describe.configure({ mode: "serial" });
```

This is required for CRUD workflows where later tests depend on data created by earlier tests.

## Authentication

Three pre-configured auth states are available:

```typescript
import { ACCOUNT_STATE_PATH } from "../../constants";

// Admin user - full permissions
test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

// Read-write user - standard permissions
test.use({ storageState: ACCOUNT_STATE_PATH.READ_WRITE });

// Read-only user - view only
test.use({ storageState: ACCOUNT_STATE_PATH.READ_ONLY });
```

Test auth at the describe level. Use nested describes to test different roles:

```typescript
test.describe("when not logged in", () => {
  test("should not show create button", async ({ page }) => { ... });
});

test.describe("when logged in as Admin", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });
  test("should show create button", async ({ page }) => { ... });
});

test.describe("when logged in as Read-Only", () => {
  test.use({ storageState: ACCOUNT_STATE_PATH.READ_ONLY });
  test("should disable edit button", async ({ page }) => { ... });
});
```

## Selectors

Use selectors in this priority order:

### 1. `getByTestId` (preferred for structural elements)

```typescript
page.getByTestId("create-object-button")
page.getByTestId("side-panel-container")
page.getByTestId("object-items")
```

### 2. `getByRole` (preferred for interactive elements)

```typescript
page.getByRole("button", { name: "Save" })
page.getByRole("link", { name: "atl1-core1" })
page.getByRole("option", { name: "Active" })
page.getByRole("textbox", { name: "Name *" })
page.getByRole("combobox", { name: "Site" })
```

### 3. `getByLabel` (for form inputs)

```typescript
page.getByLabel("Name *")
page.getByLabel("Description")
```

### 4. `getByText` (for content verification)

```typescript
page.getByText("Device created")
page.getByText("No data found")
```

### 5. CSS selectors (last resort)

```typescript
page.locator('input[type="file"]')
page.locator("#alert-success-Tenant-created")
```

### Scoping Selectors

Scope selectors to containers to avoid ambiguity:

```typescript
page.getByTestId("side-panel-container").getByLabel("Status")
page.getByTestId("object-items").getByRole("link", { name: "my-tenant" })
```

Use `{ exact: true }` when name matching could be ambiguous:

```typescript
page.getByRole("link", { name: "Cisco IOS", exact: true })
```

## Assertions

### Visibility (most common)

```typescript
await expect(element).toBeVisible();
await expect(element).not.toBeVisible();
await expect(element).toBeHidden();
```

### Content

```typescript
await expect(element).toContainText("some text");
await expect(element).toHaveText("exact text");
await expect(input).toHaveValue("value");
```

### State

```typescript
await expect(button).toBeEnabled();
await expect(button).toBeDisabled();
await expect(checkbox).toBeChecked();
```

### URL

```typescript
await expect(page).toHaveURL(/.*?branch=cr1234/);
```

### Count

```typescript
await expect(page.getByTestId("identifier-checkbox-cell")).toHaveCount(3);
```

## Waiting

Rely on Playwright's auto-waiting through `expect()` assertions. Avoid explicit waits unless absolutely necessary.

### Custom Timeouts for Long Operations

```typescript
await expect(page.getByText("Merge completed")).toBeVisible({
  timeout: 5 * 60 * 1000,
});
```

### Polling for Async Backend Processing

```typescript
while (await page.getByText("No activity found").isVisible()) {
  await page.reload();
  await expect(page.getByText("Loading...")).toBeHidden();
}
```

## Test Annotations

### Slow Tests

Use `test.slow()` for tests that need extra time (3x timeout multiplier):

```typescript
test.slow();
```

### Skipping Known Broken Tests

```typescript
test.fixme("broken test name", async ({ page }) => { ... });
test.describe.fixme("broken feature", () => { ... });
```

## Shared Utilities

### Branch Management

```typescript
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";
import { generateRandomBranchName } from "../../utils";
```

### Adding New Helpers

Place reusable helpers in `tests/e2e/utils/`. Keep helpers generic and not tied to a specific schema or object type. For form-filling helpers that are specific to a test domain, colocate them with the tests that use them or place them in a clearly-named utility file.

## Common Patterns

### CRUD Workflow

```typescript
// Create
await page.getByTestId("create-object-button").click();
await page.getByLabel("Name *").fill("new-name");
await page.getByRole("button", { name: "Save" }).click();
await expect(page.getByText("Tag created")).toBeVisible();

// Edit (from list)
await page.getByTestId("actions-cell-my-object").click();
await page.getByRole("menuitem", { name: "Edit" }).click();

// Edit (from detail page)
await page.getByTestId("edit-button").click();

// Delete
await page.getByTestId("object-details-menu").click();
await page.getByRole("menuitem", { name: "Delete" }).click();
await page.getByTestId("modal-delete-confirm").click();
```

### Dropdown/Select

```typescript
await page.getByTestId("side-panel-container").getByLabel("Status").click();
await page.getByRole("option", { name: "Maintenance" }).click();
```

### 500 Error Guard

Add this to catch unexpected server errors during tests:

```typescript
test.beforeEach(async function ({ page }) {
  page.on("response", async (response) => {
    if (response.status() === 500) {
      await expect(response.url()).toBe("This URL responded with a 500 status");
    }
  });
});
```

## Running Tests

```bash
cd frontend/app

# Run all E2E tests
npm run test:e2e

# Run a specific test file
npx playwright test tests/e2e/objects/object-update.spec.ts

# Run with UI mode for debugging
npx playwright test --ui

# Run with headed browser
npx playwright test --headed
```

## Best Practices

### Do

- Create a branch per test file for data isolation
- Use `test.step()` to structure long tests into readable phases
- Use serial mode for dependent tests (CRUD workflows)
- Scope selectors to containers to avoid ambiguity
- Test multiple user roles when permissions matter
- Use `generateRandomBranchName()` to avoid branch name collisions
- Rely on Playwright's auto-waiting instead of explicit waits
- Use `getByTestId` and `getByRole` as primary selectors

### Don't

- Don't use hardcoded branch names that could collide in parallel runs
- Don't rely on data created by other test files
- Don't use `page.waitForTimeout()` — use assertions that auto-wait
- Don't use `networkidle` waits (fragile and slow)
- Don't test component-level behavior — use component tests for that
- Don't leave test data behind — always clean up in `afterAll`
- Don't use `input[name="..."]` selectors — prefer `getByLabel` or `getByRole("textbox")`

## Quality Checklist

Before submitting your E2E tests:

- [ ] Tests create and delete their own branch for data isolation
- [ ] Tests use `test.step()` for multi-step workflows
- [ ] Serial mode is configured when tests depend on each other
- [ ] Authentication state is set via `test.use({ storageState: ... })`
- [ ] Selectors follow the priority order (testId > role > label > text > CSS)
- [ ] Selectors are scoped to containers when needed for uniqueness
- [ ] No explicit `waitForTimeout` calls — assertions auto-wait
- [ ] Multiple user roles are tested when permissions matter
- [ ] Test file is in the correct domain directory under `tests/e2e/`
- [ ] Test file uses `kebab-case.spec.ts` naming

## Related Resources

- [Writing Component Tests](writing-component-tests.md) - React component tests
- [Writing Unit Tests](writing-unit-tests.md) - TypeScript function tests
- `frontend/app/tests/e2e/utils/graphql.ts` - Branch management helpers
- `frontend/app/tests/constants.ts` - Auth credentials and state paths
- `frontend/app/playwright.config.ts` - Playwright configuration
- Playwright documentation - [playwright.dev](https://playwright.dev)
