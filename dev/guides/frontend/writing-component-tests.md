# Writing Component Tests

> Part of: `dev/guides/frontend/` | Related: `dev/guidelines/frontend/typescript.md`

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
  test("shows button when clicked", async () => {
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

- **GIVEN**: Set up the component and initial state (component render)
- **WHEN**: Perform user interactions or trigger events
- **THEN**: Assert expected outcomes

**Important**: Never mix GIVEN/WHEN/THEN comments (e.g., "GIVEN / WHEN") - keep them separate.

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
    const component = await render(<StatusBadge status="success" />);

    // THEN
    await expect.element(component.getByText("Success")).toBeVisible();
  });

  test("hides when status is null", async () => {
    // GIVEN
    const component = await render(<StatusBadge status={null} />);

    // THEN
    await expect.element(component.queryByTestId("status-badge")).not.toBeVisible();
  });
});
```

### User Interactions

Test user interactions and their visible outcomes:

```tsx
describe("FormComponent", () => {
  test("shows validation then submits", async () => {
    // GIVEN
    const component = await render(<FormComponent />);

    // WHEN
    await component.getByRole("button", { name: "Save" }).click();

    // THEN
    await expect.element(component.getByText("Name is required")).toBeVisible();

    // WHEN
    await component.getByLabelText("Name").fill("device-1");
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

test("adds item when pressing enter", async () => {
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
- Follow BDD structure: GIVEN = component render, WHEN = user interaction, THEN = assertion
- Keep GIVEN/WHEN/THEN comments separate
- Test component-specific behavior only
- Use descriptive test names that explain what is being tested

### Don't

- Don't use `getByTestId` unless absolutely necessary
- Don't test behavior implemented by third-party libraries
- Don't test internal implementation details
- Don't mix GIVEN/WHEN/THEN comments
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
    const component = await render(<List />);

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

## Quality Checklist

Before submitting your component tests:

- [ ] Tests use GIVEN/WHEN/THEN structure with separate comments
- [ ] Tests use accessibility-first queries (`getByRole`, `getByLabelText`)
- [ ] `getByTestId` is only used as a last resort
- [ ] Tests focus on component-specific behavior
- [ ] Tests verify user-facing outcomes, not internal state
- [ ] Mocks are used for API hooks, context providers, and hooks with side effects
- [ ] Test file is colocated with component (`.test.tsx` next to `.tsx`)
- [ ] Test names clearly describe what is being tested
- [ ] Tests don't test third-party library behavior

## Related Resources

- `dev/guides/frontend/writing-unit-tests.md` - Guide for writing unit tests
- `dev/guidelines/frontend/typescript.md` - TypeScript coding standards
- `frontend/app/tests/components/render.tsx` - Custom render helper implementation
- Vitest documentation - [vitest.dev](https://vitest.dev)
- Testing Library documentation - [testing-library.com](https://testing-library.com)

