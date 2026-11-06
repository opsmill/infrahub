import { describe, expect, it, vi } from "vitest";

import { generateNodeSchema } from "../../../../../../tests/fake/schema";
import { isNodeReference } from "./is-node-reference";

vi.mock("@/entities/schema/domain/use-cases/get-schema", () => ({
  getSchema: vi.fn((kind: string) => ({
    schema: kind === "BuiltinTag" ? generateNodeSchema({ kind }) : undefined,
  })),
}));

describe("isNodeReference", () => {
  it("should accept an object with a string id and the __typename of a known kind", () => {
    // GIVEN
    const value = { id: "18e5-1", __typename: "BuiltinTag", display_label: "blue" };

    // WHEN
    const result = isNodeReference(value);

    // THEN
    expect(result).toBe(true);
  });

  it.each([
    ["an unknown kind", { id: "18e5-1", __typename: "Order" }],
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
