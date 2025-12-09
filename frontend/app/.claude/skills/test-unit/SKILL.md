---
name: test-unit
description: Write unit tests for TypeScript functions in infrahub frontend. Use for testing utilities, domain logic, data transformations, or when user asks to test TypeScript functions.
---

# Write Unit Tests

Write comprehensive unit tests following the project's testing patterns and best practices.

# Guidelines

## Test Structure

Use `describe` and `it` with GIVEN/WHEN/THEN comments:

```typescript
import { describe, expect, it } from "vitest";

describe("functionName", () => {
  it("describes expected behavior", () => {
    // GIVEN
    const input = setupTestData();

    // WHEN
    const result = functionName(input);

    // THEN
    expect(result).toBe(expectedValue);
  });
});
```

## Test Data

**Always use factories from `tests/fake/`:**

```typescript
// Use with overrides
const schema = generateNodeSchema({
  name: "Device",
  namespace: "Infra",
});

const field = buildFormField({
  name: "status",
  defaultValue: { source: { type: "user" }, value: "active" },
});
```

## Mocking

### When to mock

- External dependencies (API calls)
- Complex functions that are tested separately
- Functions with side effects
- Complex initial state dependency

### How to mock

```typescript
import { vi } from "vitest";

// Mock a module
vi.mock("@/api/client", () => ({
  fetchData: vi.fn().mockResolvedValue({ data: "test" }),
}));

// Mock a function
const mockCallback = vi.fn();

// Mock return value
mockCallback.mockReturnValue("result");

// Mock resolved/rejected promise
mockCallback.mockResolvedValue({ data: "async result" });
mockCallback.mockRejectedValue(new Error("Failed"));

// Verify mock was called
expect(mockCallback).toHaveBeenCalledTimes(1);
expect(mockCallback).toHaveBeenCalledWith(expectedArg);
```


## Best Practices

### Do

- Write descriptive test names
- Use factories for test data if reusable
- Keep tests independent
- Test behavior, not implementation
- Test relevant edge cases
- Test error path
- each test should contain GIVEN/WHEN/THEN comments

### Don't

- Hardcode test data unless it's very specific to a given test
- Use vague assertions like `.toBeTruthy()`
- Create tests that depend on execution order
- Never mix GIVEN/WHEN/THEN comments (e.g., "GIVEN / WHEN") - keep them separate

# Your Process

1. **Understand the code** - Read the function being tested
2. **Identify test cases** - Happy path and edge cases
3. **Use factories** - Never hardcode test data
4. **Follow BDD** - GIVEN/WHEN/THEN comments
5. **Verify tests pass** - Run `npm run test`

# File Location

- Colocate tests: `.test.ts` next to the source file
- Example: `src/entities/schema/utils/is-generic-schema.ts` → `src/entities/schema/utils/is-generic-schema.test.ts`

# Output Format

Provide the complete test file content, ready to be written to disk. Include all necessary imports.
