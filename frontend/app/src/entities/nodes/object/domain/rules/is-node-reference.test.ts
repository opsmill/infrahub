import { describe, expect, it } from "vitest";

import { isNodeReference } from "./is-node-reference";

describe("isNodeReference", () => {
  it("should accept an object with a string id and a string __typename", () => {
    // GIVEN
    const value = { id: "18e5-1", __typename: "BuiltinTag", display_label: "blue" };

    // WHEN
    const result = isNodeReference(value);

    // THEN
    expect(result).toBe(true);
  });

  it.each([
    ["an object without __typename", { id: "18e5-1" }],
    ["an object without id", { __typename: "BuiltinTag" }],
    ["an object with a numeric id", { id: 1, __typename: "BuiltinTag" }],
    ["an array", ["18e5-1", "BuiltinTag"]],
    ["a string", "18e5-1"],
    ["null", null],
  ])("should reject %s", (_, value) => {
    // WHEN
    const result = isNodeReference(value);

    // THEN
    expect(result).toBe(false);
  });
});
