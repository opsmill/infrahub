import { describe, expect, it } from "vitest";

import type { RelationshipSchema } from "@/entities/schema/types";

import { generateRelationshipSchema } from "../../../../../tests/fake/schema";
import { getRelationshipsVisibleInTab } from "./get-relationships-visible-in-tab";

describe("getRelationshipsVisibleInTab", () => {
  it("should return relationships with kind Generic and cardinality many", () => {
    // GIVEN
    const relationships = [generateRelationshipSchema({ kind: "Generic", cardinality: "many" })];

    // WHEN
    const result = getRelationshipsVisibleInTab(relationships);

    // THEN
    expect(result).toEqual(relationships);
  });

  it("should return relationships with kind Component and cardinality many", () => {
    // GIVEN
    const relationships = [generateRelationshipSchema({ kind: "Component", cardinality: "many" })];

    // WHEN
    const result = getRelationshipsVisibleInTab(relationships);

    // THEN
    expect(result).toEqual(relationships);
  });

  it("should return relationships with kind Hierarchy and cardinality many", () => {
    // GIVEN
    const relationships = [generateRelationshipSchema({ kind: "Hierarchy", cardinality: "many" })];

    // WHEN
    const result = getRelationshipsVisibleInTab(relationships);

    // THEN
    expect(result).toEqual(relationships);
  });

  it("should return relationships with kind Template and cardinality many", () => {
    // GIVEN
    const relationships = [generateRelationshipSchema({ kind: "Template", cardinality: "many" })];

    // WHEN
    const result = getRelationshipsVisibleInTab(relationships);

    // THEN
    expect(result).toEqual(relationships);
  });

  it("should not return relationships with cardinality one regardless of kind", () => {
    // GIVEN
    const relationships = [
      generateRelationshipSchema({ kind: "Attribute", cardinality: "one" }),
      generateRelationshipSchema({ kind: "Generic", cardinality: "one" }),
      generateRelationshipSchema({ kind: "Component", cardinality: "one" }),
      generateRelationshipSchema({ kind: "Group", cardinality: "one" }),
      generateRelationshipSchema({ kind: "Hierarchy", cardinality: "one" }),
      generateRelationshipSchema({ kind: "Parent", cardinality: "one" }),
      generateRelationshipSchema({ kind: "Profile", cardinality: "one" }),
      generateRelationshipSchema({ kind: "Template", cardinality: "one" }),
    ];

    // WHEN
    const result = getRelationshipsVisibleInTab(relationships);

    // THEN
    expect(result).toEqual([]);
  });

  it("should not return relationships with kinds not in the visible list", () => {
    // GIVEN
    const relationships = [
      generateRelationshipSchema({ kind: "Attribute", cardinality: "many" }),
      generateRelationshipSchema({ kind: "Parent", cardinality: "many" }),
      generateRelationshipSchema({ kind: "Group", cardinality: "many" }),
      generateRelationshipSchema({ kind: "Profile", cardinality: "many" }),
    ];

    // WHEN
    const result = getRelationshipsVisibleInTab(relationships);

    // THEN
    expect(result).toEqual([]);
  });

  it("should handle mixed relationships correctly", () => {
    // GIVEN
    const visibleRelationships = [
      generateRelationshipSchema({ kind: "Generic", cardinality: "many" }),
      generateRelationshipSchema({ kind: "Component", cardinality: "many" }),
    ];
    const invisibleRelationships = [
      generateRelationshipSchema({ kind: "Generic", cardinality: "one" }),
      generateRelationshipSchema({ kind: "Attribute", cardinality: "many" }),
    ];
    const relationships = [...visibleRelationships, ...invisibleRelationships];

    // WHEN
    const result = getRelationshipsVisibleInTab(relationships);

    // THEN
    expect(result).toEqual(visibleRelationships);
  });

  it("should return empty array for empty input", () => {
    // GIVEN
    const relationships: RelationshipSchema[] = [];

    // WHEN
    const result = getRelationshipsVisibleInTab(relationships);

    // THEN
    expect(result).toEqual([]);
  });

  it("should sort relationships by order_weight", () => {
    // GIVEN
    const templateRel = generateRelationshipSchema({
      kind: "Template",
      cardinality: "many",
      order_weight: 0,
    });
    const componentRel = generateRelationshipSchema({
      kind: "Component",
      cardinality: "many",
      order_weight: 1,
    });
    const genericRel = generateRelationshipSchema({
      kind: "Generic",
      cardinality: "many",
      order_weight: 2,
    });
    const relationships = [genericRel, componentRel, templateRel];

    // WHEN
    const result = getRelationshipsVisibleInTab(relationships);

    // THEN
    expect(result).toEqual([templateRel, componentRel, genericRel]);
  });

  it("should handle undefined order_weight as 0", () => {
    // GIVEN
    const templateRel = generateRelationshipSchema({
      kind: "Template",
      cardinality: "many",
      order_weight: -1,
    });
    const componentRel = generateRelationshipSchema({
      kind: "Component",
      cardinality: "many",
      order_weight: undefined,
    });
    const genericRel = generateRelationshipSchema({
      kind: "Generic",
      cardinality: "many",
      order_weight: 1,
    });
    const relationships = [genericRel, componentRel, templateRel];

    // WHEN
    const result = getRelationshipsVisibleInTab(relationships);

    // THEN
    expect(result).toEqual([templateRel, componentRel, genericRel]);
  });
});
