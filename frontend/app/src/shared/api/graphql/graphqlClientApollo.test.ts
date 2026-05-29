import { describe, expect, it } from "vitest";

import { bumpAuthRetryCount } from "./graphqlClientApollo";

describe("bumpAuthRetryCount", () => {
  // Minimal stand-in for Apollo's Operation — only the two methods the
  // helper touches. Keeping it local avoids importing the full Apollo
  // Operation type just for a unit test.
  function makeOperation(initial: Record<string, unknown> = {}) {
    let ctx: Record<string, unknown> = { ...initial };
    return {
      getContext: () => ctx,
      setContext: (patch: Record<string, unknown>) => {
        ctx = { ...ctx, ...patch };
      },
    };
  }

  it("returns 1 and stores the counter on the first call", () => {
    // GIVEN an operation with no prior auth-retry count
    const operation = makeOperation();

    // WHEN we bump
    const count = bumpAuthRetryCount(operation);

    // THEN the helper reports the first attempt and persists it
    expect(count).toBe(1);
    expect(operation.getContext().authRetryCount).toBe(1);
  });

  it("returns 2 on the second call within the same operation", () => {
    // GIVEN an operation that already failed once
    const operation = makeOperation();
    bumpAuthRetryCount(operation);

    // WHEN we bump again (simulates a TOKEN_EXPIRED that came back
    // after the refreshed token was already used to replay once)
    const count = bumpAuthRetryCount(operation);

    // THEN the caller sees >1 and can break the loop
    expect(count).toBe(2);
  });

  it("preserves unrelated context keys", () => {
    // GIVEN an operation carrying caller-set context
    const operation = makeOperation({ branch: "main", processErrorMessage: "fn" });

    // WHEN we bump
    bumpAuthRetryCount(operation);

    // THEN the bump does not erase the existing keys
    expect(operation.getContext().branch).toBe("main");
    expect(operation.getContext().processErrorMessage).toBe("fn");
    expect(operation.getContext().authRetryCount).toBe(1);
  });
});
