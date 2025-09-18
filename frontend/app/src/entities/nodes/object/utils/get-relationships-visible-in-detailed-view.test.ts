import { describe, expect, it } from "vitest";

import type { RelationshipSchema } from "@/entities/schema/types";

import { generateRelationshipSchema } from "../../../../../tests/fake/schema";
import { getRelationshipsVisibleInDetailedView } from "./get-relationships-visible-in-detailed-view";

describe("getRelationshipsVisibleInDetailedView", () => {
  it("should return Attribute relationships", () => {
    // GIVEN
    const relationships = [generateRelationshipSchema({ kind: "Attribute", cardinality: "many" })];

    // WHEN
    const result = getRelationshipsVisibleInDetailedView(relationships);

    // THEN
    expect(result).toEqual(relationships);
  });

  it("should return Parent relationships", () => {
    // GIVEN
    const relationships = [generateRelationshipSchema({ kind: "Parent", cardinality: "one" })];

    // WHEN
    const result = getRelationshipsVisibleInDetailedView(relationships);

    // THEN
    expect(result).toEqual(relationships);
  });

  it("should return only Generic relationships with cardinality 'one'", () => {
    // GIVEN
    const relationships = [
      generateRelationshipSchema({ kind: "Generic", cardinality: "one" }),
      generateRelationshipSchema({ kind: "Generic", cardinality: "many" }),
    ];

    // WHEN
    const result = getRelationshipsVisibleInDetailedView(relationships);

    // THEN
    expect(result).toEqual([generateRelationshipSchema({ kind: "Generic", cardinality: "one" })]);
  });

  it("should return only Component relationships with cardinality 'one'", () => {
    // GIVEN
    const relationships = [
      generateRelationshipSchema({ kind: "Component", cardinality: "one" }),
      generateRelationshipSchema({ kind: "Component", cardinality: "many" }),
    ];

    // WHEN
    const result = getRelationshipsVisibleInDetailedView(relationships);

    // THEN
    expect(result).toEqual([generateRelationshipSchema({ kind: "Component", cardinality: "one" })]);
  });

  it("should return only Hierarchy relationships with cardinality 'one'", () => {
    // GIVEN
    const relationships = [
      generateRelationshipSchema({ kind: "Hierarchy", cardinality: "one" }),
      generateRelationshipSchema({ kind: "Hierarchy", cardinality: "many" }),
    ];

    // WHEN
    const result = getRelationshipsVisibleInDetailedView(relationships);

    // THEN
    expect(result).toEqual([generateRelationshipSchema({ kind: "Hierarchy", cardinality: "one" })]);
  });

  it("should not return Group relationship types", () => {
    // GIVEN
    const relationships = [
      generateRelationshipSchema({ kind: "Group", cardinality: "one" }),
      generateRelationshipSchema({ kind: "Group", cardinality: "many" }),
    ];

    // WHEN
    const result = getRelationshipsVisibleInDetailedView(relationships);

    // THEN
    expect(result).toEqual([]);
  });

  it("should handle mixed relationship types correctly", () => {
    // GIVEN
    const relationships = [
      generateRelationshipSchema({ kind: "Attribute", cardinality: "many" }),
      generateRelationshipSchema({ kind: "Parent", cardinality: "one" }),
      generateRelationshipSchema({ kind: "Generic", cardinality: "one" }),
      generateRelationshipSchema({ kind: "Generic", cardinality: "many" }),
      generateRelationshipSchema({ kind: "Component", cardinality: "one" }),
      generateRelationshipSchema({ kind: "Component", cardinality: "many" }),
      generateRelationshipSchema({ kind: "Hierarchy", cardinality: "one" }),
      generateRelationshipSchema({ kind: "Hierarchy", cardinality: "many" }),
      generateRelationshipSchema({ kind: "Group", cardinality: "many" }),
    ];

    // WHEN
    const result = getRelationshipsVisibleInDetailedView(relationships);

    // THEN
    expect(result).toEqual([
      generateRelationshipSchema({ kind: "Attribute", cardinality: "many" }),
      generateRelationshipSchema({ kind: "Parent", cardinality: "one" }),
      generateRelationshipSchema({ kind: "Generic", cardinality: "one" }),
      generateRelationshipSchema({ kind: "Component", cardinality: "one" }),
      generateRelationshipSchema({ kind: "Hierarchy", cardinality: "one" }),
    ]);
  });

  it("should handle empty relationships array", () => {
    // GIVEN
    const relationships: RelationshipSchema[] = [];

    // WHEN
    const result = getRelationshipsVisibleInDetailedView(relationships);

    // THEN
    expect(result).toEqual([]);
  });
});
