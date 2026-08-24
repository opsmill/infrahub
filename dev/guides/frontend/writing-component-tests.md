# Writing Component Tests

> Part of: `dev/guides/frontend/` | Related: [TypeScript Standards](../../guidelines/frontend/typescript.md)

Step-by-step guide for writing React component tests following the project's testing patterns and best practices.

## When to Write Component Tests

Write component tests when you need to:

- Test component rendering and visibility
- Verify user interactions and behavior
- Test conditional rendering based on props
- Validate error, loading, and empty states
- Ensure component-specific functionality works correctly

**Note**: This guide covers React-specific testing patterns. General testing principles (GIVEN/WHEN/THEN structure, factories, mocking fundamentals) apply from unit testing practices.

## Prerequisites

- Understanding of Vitest testing framework
- Familiarity with React Testing Library patterns
- Knowledge of accessibility-first querying
- Understanding of BDD (Behavior-Driven Development) structure

## Test Structure

Use `describe` and `test` (or `it`) with GIVEN/WHEN/THEN comments and the custom render helper from `tests/components/render.tsx`:

```tsx
import { describe, expect, test } from "vitest";

import { render } from "../../../../tests/components/render";
import { ComponentName } from "./component-name";

describe("ComponentName", () => {
  test("shows content when the button is clicked", async () => {
    // GIVEN
    const component = await render(<ComponentName prop="value" />);

    // WHEN
    await component.getByRole("button", { name: "Show" }).click();

    // THEN
    await expect.element(component.getByText("Content")).toBeVisible();
  });
});
```

### GIVEN/WHEN/THEN Structure

Follow BDD structure consistently:

- **GIVEN**: Arrange the inputs and initial state (props, schema, URL/route state, mocks)
- **WHEN**: The single action that triggers the expectation
- **THEN**: Assert the expected outcomes

**Important**:

- Never mix GIVEN/WHEN/THEN comments (e.g., "GIVEN / WHEN") - keep them separate.
- Every test has **exactly one** of each marker - always a GIVEN, a WHEN, and a THEN.
- The WHEN is whatever triggers the expectation:
  - When a **user interaction** triggers it, that interaction is the WHEN and the render is part of
    the GIVEN setup.
  - When the **render itself** produces what you assert (a render-only test, no interaction), the
    render is the WHEN and the GIVEN arranges its inputs.
- A test that needs a second WHEN/THEN is exercising a multi-phase flow - split it into separate,
  single-phase tests instead of chaining WHEN → THEN → WHEN → THEN in one test.

## Querying Elements

Prefer accessibility-based queries in this order:

1. **getByRole** - Most accessible, tests what users interact with
2. **getByLabelText** - For form inputs
3. **getByText** - For visible text content
4. **getByTestId** - Last resort only

```typescript
// ✅ Preferred: Accessibility-first
component.getByRole("button", { name: "Save" });
component.getByRole("heading", { name: "Title" });
component.getByLabelText("Name");
component.getByText("Some text");

// ❌ Avoid unless necessary
component.getByTestId("element-id"); // Last resort
```

### Why Accessibility-First?

- Tests match how users interact with your component
- Catches accessibility issues early
- More resilient to refactoring
- Encourages better component design

## What to Test

Focus on testing component-specific behavior:

- Conditional rendering and visibility
- Component-specific interactions
- Error, loading, and empty states
- Prop-driven variations
- User-facing outcomes

**Do not test**:

- Behavior implemented by third-party libraries (e.g., radix-ui, react-aria-components)
- Internal implementation details
- Library functionality that's already tested

## Common Patterns

### Conditional Rendering

Test that components render correctly based on props or state:

```tsx
describe("StatusBadge", () => {
  test("renders success state", async () => {
    // GIVEN
    const status = "success";

    // WHEN
    const component = await render(<StatusBadge status={status} />);

    // THEN
    await expect.element(component.getByText("Success")).toBeVisible();
  });

  test("hides when status is null", async () => {
    // GIVEN
    const status = null;

    // WHEN
    const component = await render(<StatusBadge status={status} />);

    // THEN
    await expect.element(component.queryByTestId("status-badge")).not.toBeVisible();
  });
});
```

### User Interactions

Test user interactions and their visible outcomes:

Each test covers a single phase. Don't chain WHEN → THEN → WHEN → THEN - split a multi-step flow
into one test per outcome:

```tsx
describe("FormComponent", () => {
  test("shows a validation error when the required field is empty", async () => {
    // GIVEN
    const component = await render(<FormComponent defaultValues={{ name: "" }} />);

    // WHEN
    await component.getByRole("button", { name: "Save" }).click();

    // THEN
    await expect.element(component.getByText("Name is required")).toBeVisible();
  });

  test("submits when the required field is filled", async () => {
    // GIVEN
    const component = await render(<FormComponent defaultValues={{ name: "device-1" }} />);

    // WHEN
    await component.getByRole("button", { name: "Save" }).click();

    // THEN
    await expect.element(component.getByText("Saved")).toBeVisible();
  });
});
```

### Testing with User Events

Use `userEvent` from `vitest/browser` for keyboard interactions:

```tsx
import { userEvent } from "vitest/browser";

test("adds an item when pressing enter", async () => {
  // GIVEN
  const component = await render(<List />);
  const input = component.getByPlaceholder("Add a new item + hit 'enter'");

  // WHEN
  await input.fill("test item");
  await userEvent.keyboard("{enter}");

  // THEN
  await expect.element(component.getByText("test item")).toBeVisible();
});
```

### Tooltip hover tests: park the pointer afterwards

In browser mode the pointer position persists across tests in the same file.
A test that ends with the pointer on a tooltip trigger leaves that tooltip
open; after a layout shift in a later render, the stale overlay can cover a
target and make its `hover()` fail actionability checks (symptom: a
`TimeoutError` that only reproduces in full-file runs, never solo).

After asserting a tooltip, park the pointer away from the trigger with
`initPointerTracking(component.locator)` (from `tests/components/utils.ts`)
so the tooltip closes before the next test renders. Example:
`src/entities/preferences/ui/user-preferences-card.test.tsx`.

### Asserting unauthorized messages

`UnauthorizedScreen` renders the custom `unauthorizedMessage` (passed via
`RequireGlobalPermission`) inside a collapsed `Accordion` — the message is
not in the DOM until the accordion is expanded. Click the accordion title
first:

```tsx
await component.getByText("You can't access this view").click();
await expect
  .element(component.getByText("You don't have permission to edit global preferences"))
  .toBeVisible();
```

## When to Mock

Mock external dependencies that have side effects:

- **API hooks** - Mock data fetching hooks
- **Context providers** - Mock context values when needed
- **Custom hooks** - Mock hooks with side effects (network calls, browser APIs)

### Mocking Example

```tsx
import { vi } from "vitest";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";

vi.mock("@/entities/branches/ui/branches-provider");

describe("TaskStatus", () => {
  const useCurrentBranchMock = vi.mocked(useCurrentBranch);

  test("renders task status", async () => {
    // GIVEN
    useCurrentBranchMock.mockReturnValue({
      currentBranch: generateBranch({ name: "branch1" }),
      setCurrentBranch: () => {},
    });

    // WHEN
    const component = await render(<TaskStatus />);

    // THEN
    await expect.element(component.getByRole("link")).toBeVisible();
  });
});
```

## File Location

Colocate tests with components using `.test.tsx` extension:

```text
src/entities/schema/components/status-badge.tsx
src/entities/schema/components/status-badge.test.tsx
```

## Best Practices

### Do

- Use accessibility-first queries (`getByRole`, `getByLabelText`) over `getByTestId`
- Test user interactions and visible outcomes, not internal state
- Follow BDD structure: GIVEN = arrange props/state (and the render when an interaction follows), WHEN = the action that triggers the expectation, THEN = assertion
- Give every test exactly one GIVEN, one WHEN, and one THEN - split multi-phase flows into separate tests
- Keep GIVEN/WHEN/THEN comments separate
- Test component-specific behavior only
- Use descriptive test names that explain what is being tested

### Don't

- Don't use `getByTestId` unless absolutely necessary
- Don't test behavior implemented by third-party libraries
- Don't test internal implementation details
- Don't mix GIVEN/WHEN/THEN comments
- Don't repeat a marker within one test (two WHENs/THENs)
- Don't test library functionality that's already tested

## Example: Complete Test File

```tsx
import { describe, expect, test } from "vitest";
import { userEvent } from "vitest/browser";

import { render } from "../../../../tests/components/render";
import { List } from "./list";

describe("List Component", () => {
  test("renders empty list state correctly", async () => {
    // GIVEN
    const defaultValue: string[] = [];

    // WHEN
    const component = await render(<List defaultValue={defaultValue} />);

    // THEN
    await expect.element(component.getByPlaceholder("Add a new item + hit 'enter'")).toBeVisible();
    await expect.element(component.getByText("Empty list")).toBeVisible();
  });

  test("adds new item when pressing enter", async () => {
    // GIVEN
    let items: string[] = [];
    const component = await render(<List onChange={(newItems) => (items = newItems)} />);
    const input = component.getByPlaceholder("Add a new item + hit 'enter'");

    // WHEN
    await input.fill("test item");
    await userEvent.keyboard("{enter}");

    // THEN
    await expect.element(component.getByText("test item")).toBeVisible();
    await expect.element(input).toHaveValue("");
    expect(items).toEqual(["test item"]);
  });

  test("removes item when clicking delete button", async () => {
    // GIVEN
    let items: string[] = ["test item"];
    const component = await render(
      <List defaultValue={items} onChange={(newItems) => (items = newItems)} />
    );

    // WHEN
    await component.getByRole("button", { name: "Remove" }).click();

    // THEN
    await expect.element(component.getByText("Empty list")).toBeVisible();
    await expect.element(component.baseElement).not.toHaveTextContent("test item");
    expect(items).toEqual([]);
  });
});
```

## The suite runs as a dev build

Vitest serves the app through Vite in dev mode, so `import.meta.env.DEV` is `true` in every
component test — including tests of a production build's behaviour. Any code branching on it takes
the dev branch here and cannot be exercised the other way from a component test. E2E is the layer
that runs a real build (the docker stack), so that is where the production branch is observable.

Put policy that depends on the environment in a pure function under `domain/rules/` and unit-test
its branches directly; leave the component test to prove the wiring. When a component test can
only reach one branch, say which one and why in the test, and state the precondition rather than
assuming it:

```ts
// Vitest serves through Vite in dev mode, so the dev branch is the only one reachable here.
expect(systemPrefersDark()).toBe(false); // stated, so a passing assertion cannot be a coincidence
```

## Troubleshooting

### `mockClear is not a function` in CI

Symptom: `frontend-tests` fails with `TypeError: vi.mocked(...).mockClear is not
a function` (or `.mockReturnValue` / `.mockResolvedValue`), in a test file you
did not touch, and passes on re-run. The file it lands on is random.

Cause: Vite discovered a dependency part-way through the run, re-optimized, and
reloaded the page. The reload drops every `vi.mock()` registration made before
it, so `vi.mocked(...)` hands back the real function. Look just above the
failures for the fingerprint — `dependencies optimized: …` followed by
`optimized dependencies changed. reloading` and `[vitest] Vite unexpectedly
reloaded a test`. **This is not your breakage**; re-run the job on the same SHA
to confirm.

`frontend/app/vitest.config.ts` guards against this in two layers, and the
comment above `optimizeDeps` there is the authority — read it before changing
anything:

- `optimizeDeps.entries` widens Vite's initial scan to all of `src`. Browser
  mode otherwise seeds the scan with the test files only, so a dependency is
  missed whenever no test imports its module. This layer covers anything
  statically reachable, so a new component pulling in a new dependency needs no
  config change at all.
- `optimizeDeps.include` pre-bundles the remainder: imports whose specifier is
  not a literal. Every entry here resolves from `frontend/app`, so a dependency
  owned by a workspace package (`@infrahub/ui`, `@infrahub/graph`,
  `infrahub-schema-visualizer`) needs the nested `"<owner> > <dep>"` form. A
  bare specifier that does not resolve is dropped with a `Failed to resolve
  dependency` warning and protects nothing.

If a reload still happens, add the dependencies named in the log line to
`include` — but check first whether widening the scan is the better answer,
since that scales and the list does not.

Reproduce and verify locally with CI's own command and a cold optimizer cache —
plain `vitest run` does not reload, which makes this look CI-only:

```bash
cd frontend/app && rm -rf node_modules/.vite && pnpm test:coverage 2>&1 | tee /tmp/vitest.log
```

All three of these must be `0`:

```bash
grep -c 'Failed to resolve dependency' /tmp/vitest.log
grep -c 'dependencies optimized' /tmp/vitest.log
grep -c 'unexpectedly reloaded' /tmp/vitest.log
```

Nested entries land in `node_modules/.vite/vitest/<hash>/deps/` as
`owner_n_dep.js` (for example `infrahub-schema-visualizer_n_@dagrejs_dagre.js`),
so looking there for a bare package name gives a false negative.

## Quality Checklist

Before submitting your component tests:

- [ ] Every test has exactly one GIVEN, one WHEN, and one THEN, as separate comments (WHEN = whatever triggers the expectation)
- [ ] Tests use accessibility-first queries (`getByRole`, `getByLabelText`)
- [ ] `getByTestId` is only used as a last resort
- [ ] Tests focus on component-specific behavior
- [ ] Tests verify user-facing outcomes, not internal state
- [ ] Mocks are used for API hooks, context providers, and hooks with side effects
- [ ] Test file is colocated with component (`.test.tsx` next to `.tsx`)
- [ ] Test names clearly describe what is being tested
- [ ] Tests don't test third-party library behavior
- [ ] Test file type-checks cleanly — no implicit `any` in render-helper signatures, mock callbacks, or wrapper components. The project has pre-existing `tsc` errors unrelated to your work, but new test files must not add to the count. Verify with `pnpm exec tsc --noEmit -p tsconfig.json` before committing.

## Related Resources

- [Writing Unit Tests](writing-unit-tests.md) - Guide for writing unit tests
- [TypeScript Standards](../../guidelines/frontend/typescript.md) - TypeScript coding standards
- `frontend/app/tests/components/render.tsx` - Custom render helper implementation
- Vitest documentation - [vitest.dev](https://vitest.dev)
- Testing Library documentation - [testing-library.com](https://testing-library.com)
