import { describe, expect, it } from "vitest";

import { throwGraphQLErrors } from "./throw-graphql-errors";

describe("throwGraphQLErrors", () => {
  it("throws every message joined", () => {
    // GIVEN
    const errors = [{ message: "first" }, { message: "second" }];

    // WHEN
    const call = () => throwGraphQLErrors(errors);

    // THEN
    expect(call).toThrow("first; second");
  });

  it("does nothing without errors", () => {
    // GIVEN
    const errors = undefined;

    // WHEN
    const call = () => throwGraphQLErrors(errors);

    // THEN
    expect(call).not.toThrow();
  });
});
