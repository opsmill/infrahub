# Writing Unit Tests

> Part of: `dev/guides/frontend/` | Related: [TypeScript Standards](../../guidelines/frontend/typescript.md)

Step-by-step guide for writing unit tests for TypeScript functions following the project's testing patterns and best practices.

## When to Write Unit Tests

Write unit tests when you need to:

- Test utility functions and helpers
- Test domain logic and business rules
- Test data transformations and formatting
- Test pure functions with predictable inputs and outputs
- Verify edge cases and error handling
- Test functions independently of React components

**Note**: For testing React components, see [Writing Component Tests](./writing-component-tests.md). This guide focuses on testing TypeScript functions, utilities, and domain logic.

## Prerequisites

- Understanding of Vitest testing framework
- Familiarity with TypeScript
- Understanding of BDD (Behavior-Driven Development) structure
- Knowledge of mocking patterns

## Test Structure

Use `describe` and `it` (or `test`) with GIVEN/WHEN/THEN comments:

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

### GIVEN/WHEN/THEN Structure

Follow BDD structure consistently:

- **GIVEN**: Set up test data and initial conditions
- **WHEN**: Execute the function being tested
- **THEN**: Assert the expected outcome

**Important**: Never mix GIVEN/WHEN/THEN comments (e.g., "GIVEN / WHEN") - keep them separate.

## Test Data

### Always Use Factories

**Always use factories from `tests/fake/`** instead of hardcoding test data. Factories provide:

- Consistent test data structure
- Easy customization through overrides
- Maintainability when data structures change
- Reusability across tests

### Adding Factories

Location: `frontend/app/tests/fake/`

**When to add:** If you create test data that could be reused across multiple tests, add it as a factory.

**How to add:**
1. Check existing files in `tests/fake/` for related factories
2. Add to existing file if domain matches, otherwise create new file
3. Use `generate*` naming convention
4. Accept optional overrides parameter for customization

### Using Factories with Overrides

Factories accept overrides to customize test data:

```typescript
import { generateNodeSchema } from "../../../../tests/fake/schema";
import { buildFormField } from "../../../../tests/fake/form";

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

### Example: Using Factories

```typescript
import { describe, expect, it } from "vitest";

import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";

import { generateGenericSchema, generateNodeSchema } from "../../../../tests/fake/schema";

describe("isGenericSchema", () => {
  it("should return true for a generic schema", () => {
    // GIVEN
    const schema = generateGenericSchema();

    // WHEN
    const result = isGenericSchema(schema);

    // THEN
    expect(result).toBe(true);
  });

  it("should return false for a non-generic schema", () => {
    // GIVEN
    const schema = generateNodeSchema();

    // WHEN
    const result = isGenericSchema(schema);

    // THEN
    expect(result).toBe(false);
  });
});
```

## Mocking

### When to Mock

Mock external dependencies and complex functions:

- **External dependencies** - API calls, network requests
- **Complex functions** - Functions that are tested separately
- **Functions with side effects** - File system, browser APIs, timers
- **Complex initial state dependency** - When setup is expensive or complex

### How to Mock

Use Vitest's `vi` utilities for mocking:

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

// Mock resolved promise
mockCallback.mockResolvedValue({ data: "async result" });

// Mock rejected promise
mockCallback.mockRejectedValue(new Error("Failed"));

// Verify mock was called
expect(mockCallback).toHaveBeenCalledTimes(1);
expect(mockCallback).toHaveBeenCalledWith(expectedArg);
```

### Mocking Example

```typescript
import { describe, expect, it, vi } from "vitest";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getBranchTaskStatusFromApi } from "@/entities/tasks/api/get-branch-task-status-from-api";

vi.mock("@/entities/branches/ui/branches-provider");
vi.mock("@/entities/tasks/api/get-branch-task-status-from-api");

describe("TaskStatus", () => {
  const useCurrentBranchMock = vi.mocked(useCurrentBranch);
  const getBranchTaskStatusFromApiMock = vi.mocked(getBranchTaskStatusFromApi);

  it("handles task status correctly", () => {
    // GIVEN
    useCurrentBranchMock.mockReturnValue({
      currentBranch: generateBranch({ name: "branch1" }),
      setCurrentBranch: () => {},
    });
    getBranchTaskStatusFromApiMock.mockResolvedValue({
      data: { InfrahubTaskBranchStatus: { count: 1 } },
      loading: false,
      networkStatus: NetworkStatus.ready,
    });

    // WHEN
    const result = getTaskStatus();

    // THEN
    expect(result).toBeDefined();
  });
});
```

## What to Test

Focus on testing function behavior:

- **Happy path** - Normal operation with valid inputs
- **Edge cases** - Boundary conditions, empty inputs, null values
- **Error handling** - Invalid inputs, error conditions
- **Data transformations** - Input/output transformations
- **Business logic** - Domain rules and validations

### Example: Comprehensive Test Coverage

```typescript
import { describe, expect, it } from "vitest";

import {
  generateAttributeSchema,
  generateRelationshipSchema,
} from "../../../../../tests/fake/schema";
import { shouldAllowEmptySubmission } from "./shouldAllowEmptySubmission";

describe("shouldAllowEmptySubmission", () => {
  it("returns true when all attributes are read-only", () => {
    // GIVEN: A schema where all attributes are read-only
    const schema = {
      attributes: [
        generateAttributeSchema({ name: "number_pool_attr", read_only: true }),
        generateAttributeSchema({ name: "computed_attr", read_only: true }),
      ],
    } as ModelSchema;

    // WHEN
    const result = shouldAllowEmptySubmission(schema);

    // THEN
    expect(result).toBe(true);
  });

  it("returns false when some attributes are not read-only", () => {
    // GIVEN: A schema with some editable attributes
    const schema = {
      attributes: [
        generateAttributeSchema({ name: "editable_attr", read_only: false }),
        generateAttributeSchema({ name: "read_only_attr", read_only: true }),
      ],
    } as ModelSchema;

    // WHEN
    const result = shouldAllowEmptySubmission(schema);

    // THEN
    expect(result).toBe(false);
  });

  it("returns true when schema has no attributes", () => {
    // GIVEN: A schema with no attributes (only relationships)
    const schema = {
      attributes: [],
    } as ModelSchema;

    // WHEN
    const result = shouldAllowEmptySubmission(schema);

    // THEN
    expect(result).toBe(true);
  });
});
```

## File Location

Colocate tests with source files using `.test.ts` extension:

```text
src/entities/schema/utils/is-generic-schema.ts
src/entities/schema/utils/is-generic-schema.test.ts
```

## Best Practices

### Do

- Write descriptive test names that explain what is being tested
- Use factories for test data if reusable
- Keep tests independent - each test should run in isolation
- Test behavior, not implementation details
- Test relevant edge cases and error paths
- Use GIVEN/WHEN/THEN comments in each test
- Use specific assertions (e.g., `.toBe()`, `.toEqual()`) instead of vague ones

### Don't

- Don't hardcode test data unless it's very specific to a given test
- Don't use vague assertions like `.toBeTruthy()` or `.toBeFalsy()`
- Don't create tests that depend on execution order
- Don't mix GIVEN/WHEN/THEN comments (e.g., "GIVEN / WHEN") - keep them separate
- Don't test implementation details - focus on behavior
- Don't skip testing error paths

## Example: Complete Test File

```typescript
import { describe, expect, it } from "vitest";

import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";

import { generateGenericSchema, generateNodeSchema } from "../../../../tests/fake/schema";

describe("isGenericSchema", () => {
  it("should return true for a generic schema", () => {
    // GIVEN
    const schema = generateGenericSchema();

    // WHEN
    const result = isGenericSchema(schema);

    // THEN
    expect(result).toBe(true);
  });

  it("should return false for a non-generic schema", () => {
    // GIVEN
    const schema = generateNodeSchema();

    // WHEN
    const result = isGenericSchema(schema);

    // THEN
    expect(result).toBe(false);
  });

  it("should return false for null input", () => {
    // GIVEN
    const schema = null;

    // WHEN
    const result = isGenericSchema(schema);

    // THEN
    expect(result).toBe(false);
  });
});
```

## Testing Process

Follow this process when writing unit tests:

1. **Understand the code** - Read the function being tested to understand its purpose and behavior
2. **Identify test cases** - Determine happy path and edge cases to test
3. **Use factories** - Never hardcode test data; use factories from `tests/fake/`
4. **Follow BDD** - Structure tests with GIVEN/WHEN/THEN comments
5. **Verify tests pass** - Run `npm run test` to ensure tests pass

## Quality Checklist

Before submitting your unit tests:

- [ ] Tests use GIVEN/WHEN/THEN structure with separate comments
- [ ] Tests use factories from `tests/fake/` instead of hardcoded data
- [ ] Test names clearly describe what is being tested
- [ ] Tests cover happy path and relevant edge cases
- [ ] Error paths are tested when applicable
- [ ] Tests are independent and can run in any order
- [ ] Tests use specific assertions (not `.toBeTruthy()`)
- [ ] Mocks are used appropriately for external dependencies
- [ ] Test file is colocated with source file (`.test.ts` next to `.ts`)
- [ ] Tests focus on behavior, not implementation details

## Related Resources

- [Writing Component Tests](writing-component-tests.md) - Guide for writing component tests
- [TypeScript Standards](../../guidelines/frontend/typescript.md) - TypeScript coding standards
- `frontend/app/tests/fake/` - Test data factories
- Vitest documentation - [vitest.dev](https://vitest.dev)
