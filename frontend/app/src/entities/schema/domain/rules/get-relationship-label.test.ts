import { describe, expect, it } from "vitest";

import { getRelationshipLabel } from "@/entities/schema/domain/rules/get-relationship-label";

import {
  generateGenericSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../tests/fake/schema";

describe("getRelationshipLabel", () => {
  it("returns the peer label when the relationship is hierarchical and the peer has a label (C1)", () => {
    // GIVEN
    const relationshipSchema = generateRelationshipSchema({
      name: "parent",
      label: "Parent",
      cardinality: "one",
      hierarchical: "LocationGeneric",
    });
    const peerSchema = generateNodeSchema({ kind: "Site", label: "Site" });

    // WHEN
    const result = getRelationshipLabel(relationshipSchema, peerSchema);

    // THEN
    expect(result).toBe("Site");
  });

  it("falls back to label when hierarchical but the peer schema is missing (C2)", () => {
    // GIVEN
    const relationshipSchema = generateRelationshipSchema({
      name: "parent",
      label: "Parent",
      cardinality: "one",
      hierarchical: "LocationGeneric",
    });

    // WHEN
    const result = getRelationshipLabel(relationshipSchema);

    // THEN
    expect(result).toBe("Parent");
  });

  it("falls back to name when hierarchical but neither the peer label nor the relationship label is present (C2)", () => {
    // GIVEN
    const relationshipSchema = generateRelationshipSchema({
      name: "parent",
      label: null,
      cardinality: "one",
      hierarchical: "LocationGeneric",
    });
    const peerSchema = generateNodeSchema({ kind: "Site", label: null });

    // WHEN
    const result = getRelationshipLabel(relationshipSchema, peerSchema);

    // THEN
    expect(result).toBe("parent");
  });

  it("leaves a non-hierarchical relationship named parent unchanged (C3)", () => {
    // GIVEN
    const relationshipSchema = generateRelationshipSchema({
      name: "parent",
      label: "Parent",
      cardinality: "one",
      hierarchical: null,
    });
    const peerSchema = generateNodeSchema({ kind: "Site", label: "Site" });

    // WHEN
    const result = getRelationshipLabel(relationshipSchema, peerSchema);

    // THEN
    expect(result).toBe("Parent");
  });

  it("returns the peer label verbatim for a hierarchical children relationship without pluralization (C4)", () => {
    // GIVEN
    const relationshipSchema = generateRelationshipSchema({
      name: "children",
      label: "Children",
      cardinality: "many",
      hierarchical: "LocationGeneric",
    });
    const peerSchema = generateNodeSchema({ kind: "Site", label: "Site" });

    // WHEN
    const result = getRelationshipLabel(relationshipSchema, peerSchema);

    // THEN
    expect(result).toBe("Site");
  });

  it("keeps the generic Parent/Children label when the hierarchical peer resolves to a generic (C5)", () => {
    // GIVEN
    const relationshipSchema = generateRelationshipSchema({
      name: "parent",
      label: "Parent",
      cardinality: "one",
      hierarchical: "LocationGeneric",
    });
    const peerSchema = generateGenericSchema({ kind: "LocationGeneric", label: "Location" });

    // WHEN
    const result = getRelationshipLabel(relationshipSchema, peerSchema);

    // THEN
    expect(result).toBe("Parent");
  });
});
