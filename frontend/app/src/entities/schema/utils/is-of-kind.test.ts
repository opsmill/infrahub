import { describe, expect, it } from "vitest";

import { isOfKind } from "@/entities/schema/utils/is-of-kind";

import { generateNodeSchema } from "../../../../tests/fake/schema";

describe("isOfKind", () => {
  it("should match when schema has the exact kind", () => {
    // GIVEN
    const schema = generateNodeSchema({ kind: "TestKind" });

    // WHEN
    const result = isOfKind("TestKind", schema);

    // THEN
    expect(result).toBe(true);
  });

  it("should match when schema inherits from the kind", () => {
    // GIVEN
    const schema = generateNodeSchema({
      kind: "Child",
      inherit_from: ["ParentKind"],
    });

    // WHEN
    const result = isOfKind("ParentKind", schema);

    // THEN
    expect(result).toBe(true);
  });

  it("should not match when schema has different kind and no inheritance", () => {
    // GIVEN
    const schema = generateNodeSchema({ kind: "Different" });

    // WHEN
    const result = isOfKind("TestKind", schema);

    // THEN
    expect(result).toBe(false);
  });

  it("should match all parent kinds when schema inherits from multiple", () => {
    // GIVEN
    const schema = generateNodeSchema({
      kind: "Child",
      inherit_from: ["Parent1", "Parent2"],
    });

    // WHEN
    const isParent1 = isOfKind("Parent1", schema);
    const isParent2 = isOfKind("Parent2", schema);

    // THEN
    expect(isParent1).toBe(true);
    expect(isParent2).toBe(true);
  });
});
