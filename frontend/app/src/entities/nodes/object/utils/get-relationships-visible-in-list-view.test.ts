import { describe, expect, it } from "vitest";

import { generateRelationshipSchema } from "../../../../../tests/fake/schema";
import { getRelationshipsVisibleInListView } from "./get-relationships-visible-in-list-view";

describe("getRelationshipsVisibleInListView", () => {
  it("should return only relationships that should be visible in list view", () => {
    // GIVEN
    const genericOne = generateRelationshipSchema({ kind: "Generic", cardinality: "one" });
    const genericMany = generateRelationshipSchema({ kind: "Generic", cardinality: "many" });
    const attributeOne = generateRelationshipSchema({ kind: "Attribute", cardinality: "one" });
    const attributeMany = generateRelationshipSchema({ kind: "Attribute", cardinality: "many" });
    const componentOne = generateRelationshipSchema({ kind: "Component", cardinality: "one" });
    const componentMany = generateRelationshipSchema({ kind: "Component", cardinality: "many" });
    const hierarchyOne = generateRelationshipSchema({ kind: "Hierarchy", cardinality: "one" });
    const hierarchyMany = generateRelationshipSchema({ kind: "Hierarchy", cardinality: "many" });
    const parentOne = generateRelationshipSchema({ kind: "Parent", cardinality: "one" });
    const parentMany = generateRelationshipSchema({ kind: "Parent", cardinality: "many" });

    const relationships = [
      genericOne,
      genericMany,
      attributeOne,
      attributeMany,
      componentOne,
      componentMany,
      hierarchyOne,
      hierarchyMany,
      parentOne,
      parentMany,
    ];

    // WHEN
    const result = getRelationshipsVisibleInListView(relationships);

    // THEN
    expect(result).toEqual([attributeOne, attributeMany, hierarchyOne, parentOne, parentMany]);
  });

  it("should return empty array when no relationships are provided", () => {
    // WHEN
    const result = getRelationshipsVisibleInListView([]);

    // THEN
    expect(result).toEqual([]);
  });

  it("should handle relationships with unknown kind", () => {
    // GIVEN
    const attribute = generateRelationshipSchema({ kind: "Attribute", cardinality: "one" });
    const unknown = generateRelationshipSchema({
      kind: "Nope" as never,
      cardinality: "one",
    });

    // WHEN
    const result = getRelationshipsVisibleInListView([attribute, unknown]);

    // THEN
    expect(result).toHaveLength(1);
    expect(result[0]!.kind).toBe("Attribute");
  });
});
