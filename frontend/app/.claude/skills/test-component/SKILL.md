---
name: test-component
description: Write tests for React components in .tsx files. Use for testing component rendering, user interactions, or when user asks to test React components.
---

# Write Component Tests

Write comprehensive React component tests following the project's testing patterns and best practices.

**Note**: This skill extends the `test-unit` skill with React-specific testing patterns. General testing principles (GIVEN/WHEN/THEN structure, factories, mocking fundamentals) apply from test-unit.

## React-Specific Guidelines

## Test Structure

Use `describe` and `it` with GIVEN/WHEN/THEN comments and the custom render helper from `tests/components/render.tsx`:

```tsx
import { describe, expect, test } from "vitest";

import { render } from "../../../../tests/components/render";
import { ComponentName } from "./component-name";

describe("ComponentName", () => {
  it("shows button when clicked", async () => {
    // GIVEN
    const component = await render(<ComponentName prop="value" />);

    // WHEN
    await component.getByRole("button", { name: "Show" }).click();

    // THEN
    await expect.element(component.getByText("Content")).toBeVisible();
  });
});
```

## Querying Elements

Prefer accessibility-based queries:

```typescript
component.getByRole("button", { name: "Save" });
component.getByRole("heading", { name: "Title" });
component.getByText("Some text");
component.getByTestId("element-id"); // Last resort
```

## When to mock

- API hooks
- Context providers
- Custom hooks with side effects

## What to Test

- Conditional rendering and visibility
- Component-specific interactions
- Error, loading, and empty states
- Prop-driven variations

## Common Patterns

### Conditional Rendering

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

### Interaction and Validation

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

## React-Specific Best Practices

- Use accessibility-first queries (getByRole, getByLabelText) over getByTestId
- Test user interactions and visible outcomes, not internal state
- Use getByTestId only as last resort
- Only test component specific behavior, do not test behavior implemented by radix-ui or react-aria-components
- Follow BDD structure: GIVEN = component render, WHEN = user interaction, THEN = assertion
- Never mix GIVEN/WHEN/THEN comments (e.g., "GIVEN / WHEN") - keep them separate

## File Location

Colocate tests: `.test.tsx` next to the component

```text
src/entities/schema/components/status-badge.tsx
src/entities/schema/components/status-badge.test.tsx
```
