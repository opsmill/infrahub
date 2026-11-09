import { describe, expect, it } from "vitest";

import { isSortableRelationship } from "@/entities/nodes/sort/domain/rules/is-sortable-relationship";

import { generateRelationshipSchema } from "../../../../../../tests/fake/schema";

describe("isSortableRelationship", () => {
  it("accepts a cardinality-one relationship", () => {
    // GIVEN
    const relationship = generateRelationshipSchema({
      name: "site",
      peer: "LocationSite",
      cardinality: "one",
    });

    // WHEN
    const result = isSortableRelationship(relationship);

    // THEN
    expect(result).toBe(true);
  });

  it("rejects a cardinality-many relationship", () => {
    // GIVEN
    const relationship = generateRelationshipSchema({
      name: "interfaces",
      peer: "LocationSite",
      cardinality: "many",
    });

    // WHEN
    const result = isSortableRelationship(relationship);

    // THEN
    expect(result).toBe(false);
  });
});
