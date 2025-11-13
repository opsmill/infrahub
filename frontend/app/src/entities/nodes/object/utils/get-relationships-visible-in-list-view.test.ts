import { describe, expect, it } from "vitest";

import type { RelationshipSchema } from "@/entities/schema/types";

import { getRelationshipsVisibleInListView } from "./get-relationships-visible-in-list-view";

describe("getRelationshipsVisibleInListView", () => {
  it("should return only relationships that should be visible in list view", () => {
    // GIVEN
    const relationships: RelationshipSchema[] = [
      { kind: "Generic", cardinality: "one" } as RelationshipSchema,
      { kind: "Generic", cardinality: "many" } as RelationshipSchema,
      { kind: "Attribute", cardinality: "one" } as RelationshipSchema,
      { kind: "Attribute", cardinality: "many" } as RelationshipSchema,
      { kind: "Component", cardinality: "one" } as RelationshipSchema,
      { kind: "Component", cardinality: "many" } as RelationshipSchema,
      { kind: "Hierarchy", cardinality: "one" } as RelationshipSchema,
      { kind: "Hierarchy", cardinality: "many" } as RelationshipSchema,
      { kind: "Parent", cardinality: "one" } as RelationshipSchema,
      { kind: "Parent", cardinality: "many" } as RelationshipSchema,
    ];

    // WHEN
    const result = getRelationshipsVisibleInListView(relationships);

    // THEN
    expect(result).toEqual([
      { kind: "Attribute", cardinality: "one" },
      { kind: "Attribute", cardinality: "many" },
      { kind: "Hierarchy", cardinality: "one" },
      { kind: "Parent", cardinality: "one" },
      { kind: "Parent", cardinality: "many" },
    ]);
  });

  it("should return empty array when no relationships are provided", () => {
    // WHEN
    const result = getRelationshipsVisibleInListView([]);

    // THEN
    expect(result).toEqual([]);
  });

  it("should handle relationships with missing kind", () => {
    // GIVEN
    const relationships = [
      { kind: "Attribute", cardinality: "one" } as RelationshipSchema,
      { kind: "Nope", cardinality: "one" } as unknown as RelationshipSchema,
    ];

    // WHEN
    const result = getRelationshipsVisibleInListView(relationships);

    // THEN
    expect(result).toHaveLength(1);
    expect(result[0]!.kind).toBe("Attribute");
  });
});
