import { describe, expect, it } from "vitest";

import { isNodeRelationshipMany } from "@/entities/nodes/object/utils/is-node-relationship-many";
import type {
  NodeAttribute,
  NodeRelationshipMany,
  NodeRelationshipOne,
} from "@/entities/nodes/types";

describe("isNodeRelationshipMany", () => {
  it("should return true for a cardinality-many relationship", () => {
    // GIVEN
    const value: NodeRelationshipMany = {
      edges: [{ node: { id: "1", hfid: null, display_label: "Tag A", __typename: "BuiltinTag" } }],
    };

    // WHEN
    const result = isNodeRelationshipMany(value);

    // THEN
    expect(result).toBe(true);
  });

  it("should return true for a cardinality-many relationship with empty edges", () => {
    // GIVEN
    const value: NodeRelationshipMany = { edges: [] };

    // WHEN
    const result = isNodeRelationshipMany(value);

    // THEN
    expect(result).toBe(true);
  });

  it("should return false for a cardinality-one relationship", () => {
    // GIVEN
    const value: NodeRelationshipOne = {
      node: { id: "1", hfid: null, display_label: "Device A", __typename: "InfraDevice" },
    };

    // WHEN
    const result = isNodeRelationshipMany(value);

    // THEN
    expect(result).toBe(false);
  });

  it("should return false for an attribute", () => {
    // GIVEN
    const value: NodeAttribute = { value: "test" };

    // WHEN
    const result = isNodeRelationshipMany(value);

    // THEN
    expect(result).toBe(false);
  });

  it("should return false for a primitive value", () => {
    // GIVEN
    const value = null;

    // WHEN
    const result = isNodeRelationshipMany(value);

    // THEN
    expect(result).toBe(false);
  });
});
