---
title: Running & writing tests
icon: beaker
---

# Running & writing tests for frontend

!!!info Before we start
If you have never run Infrahub tests before, we highly suggest to follow the [frontend guide](getting-started.md).
!!!

We're expecting to see proper tests for each feature/bugfix you make. If you're not sure how to write these tests, this page is made to help you get started.

Infrahub frontend has 3 types of testing:

- [E2E tests](#end-to-end-e2e-tests)
- [Integration tests (Documentation WIP)](#integration-tests)
- [Unit tests (Documentation WIP)](#unit-tests)

## end-to-end (E2E) tests

Infrahub uses [Playwright](https://playwright.dev/) for E2E testing.

### Folder structure

E2E tests are located in `/frontend/tests/e2e` and are structured based on routing.

For example, a test linked to the route `/objects/:objectname/:objectid` will be found in the `/objects/[objectname]/[objectid]` folder.

### Writing E2E tests

[Playwright](https://playwright.dev/) is our E2E testing tool. It can automatically generate tests as you perform actions in the browser, making it a quick way to start testing:

```shell
npx playwright codegen
```

To run a specific test, substitute `test` with `test.only`, or use the --grep 'test name' CLI parameter:

```ts
...
test.only('test name', async ({ page }) => {
  expect(response.ok).toBe(true);
});
// or
npx playwright test --grep 'test name'
```

To disable a specific test, substitute `test` with `test.skip`:

```ts
test.skip('test name', async ({ page }) => {
  expect(response.ok).toBe(true);
});
```

### Debugging E2E tests

To debug a test, you need to run tests in debug mode. You can pause script execution using:

```ts
await page.pause();
```

To continue, press 'Resume' button in the page overlay or call `playwright.resume()` in the DevTools console.

At the end of each test, all traces are saved for exploration in `/frontend/playwright-report`. You can open `index.html` in a browser or run `npx playwright show-report`.

You can find a tutorial on how to use Trace viewer GUI [here](https://playwright.dev/docs/trace-viewer).

### Best practices

1. Prioritize user-facing attributes and avoid selectors tied to implementation:

```ts
// ❌
page.locator("[href='/objects/CoreOrganization'] > .group")

// ✅
page.getByRole("button", { name: "Save" });
```

2. Structure tests with steps for better readability:

```shell
# headless mode
npm run test:e2e 

# non-headless mode (headed)
npm run test:e2e:headed

# Debug mode
npm run test:e2e:debug

# UI mode
npm run test:e2e:ui
```

## Integration tests

```sh
npm run cypress:run:component
```

## Unit tests

```sh
npm run test

# same with coverage
npm run test:coverage
```
