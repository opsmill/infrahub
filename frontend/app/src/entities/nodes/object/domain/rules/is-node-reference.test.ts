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
    ["no __typename", { id: "18e5-1" }],
    ["a numeric id", { id: 1, __typename: "BuiltinTag" }],
    ["a string hfid", { id: "18e5-1", __typename: "BuiltinTag", hfid: "blue" }],
    ["an object display_label", { id: "18e5-1", __typename: "BuiltinTag", display_label: {} }],
  ])("should reject an object with %s", (_, value) => {
    // WHEN
    const result = isNodeReference(value);

    // THEN
    expect(result).toBe(false);
  });
});
