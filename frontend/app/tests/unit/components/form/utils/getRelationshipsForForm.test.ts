import { describe, expect, it } from "vitest";
import { getRelationshipsForForm } from "@/components/form/utils/getRelationshipsForForm";
import { buildRelationshipSchema } from "./getFormFieldsFromSchema.test";

describe("getRelationshipsForForm", () => {
  it("returns an empty array if the provided relationships array is empty", () => {
    // GIVEN
    const relationships: never[] = [];

    // WHEN
    const result = getRelationshipsForForm(relationships);

    // THEN
    expect(result).toEqual([]);
  });

  it("returns a relationship if cardinality is one", () => {
    // GIVEN
    const relationships = [buildRelationshipSchema({ cardinality: "one" })];

    // WHEN
    const result = getRelationshipsForForm(relationships);

    // THEN
    expect(result).toEqual([relationships[0]]);
  });

  it("returns a relationship of cardinality many if kind is Attribute or Parent", () => {
    // GIVEN
    const relationships = [
      buildRelationshipSchema({ cardinality: "many", kind: "Attribute" }),
      buildRelationshipSchema({ cardinality: "many", kind: "Parent" }),
    ];

    // WHEN
    const result = getRelationshipsForForm(relationships);

    // THEN
    expect(result).toEqual(relationships);
  });

  it("should not return a relationship of cardinality many if kind is Generic/Component/Hierarchy", () => {
    // GIVEN
    const relationships = [
      buildRelationshipSchema({ cardinality: "many", kind: "Generic" }),
      buildRelationshipSchema({ cardinality: "many", kind: "Component" }),
      buildRelationshipSchema({ cardinality: "many", kind: "Hierarchy" }),
      buildRelationshipSchema({ cardinality: "many", kind: "Group" }),
      buildRelationshipSchema({ cardinality: "many", kind: "Profile" }),
    ];

    // WHEN
    const result = getRelationshipsForForm(relationships);

    // THEN
    expect(result).toEqual([]);
  });

  it("returns a relationship of cardinality many if it's mandatory field", () => {
    // GIVEN
    const relationships = [
      buildRelationshipSchema({ cardinality: "many", kind: "Attribute", optional: false }),
      buildRelationshipSchema({ cardinality: "many", kind: "Parent", optional: false }),
      buildRelationshipSchema({ cardinality: "many", kind: "Generic", optional: false }),
      buildRelationshipSchema({ cardinality: "many", kind: "Component", optional: false }),
      buildRelationshipSchema({ cardinality: "many", kind: "Hierarchy", optional: false }),
      buildRelationshipSchema({ cardinality: "many", kind: "Group", optional: false }),
      buildRelationshipSchema({ cardinality: "many", kind: "Profile", optional: false }),
    ];

    // WHEN
    const result = getRelationshipsForForm(relationships);

    // THEN
    expect(result).toEqual(relationships);
  });

  it("When update, returns a mandatory relationship of cardinality is many if kind is Attribute or Parent", () => {
    // GIVEN
    const relationships = [
      buildRelationshipSchema({ cardinality: "many", kind: "Attribute", optional: false }),
      buildRelationshipSchema({ cardinality: "many", kind: "Parent", optional: false }),
      buildRelationshipSchema({ cardinality: "many", kind: "Generic", optional: false }),
      buildRelationshipSchema({ cardinality: "many", kind: "Component", optional: false }),
      buildRelationshipSchema({ cardinality: "many", kind: "Hierarchy", optional: false }),
      buildRelationshipSchema({ cardinality: "many", kind: "Group", optional: false }),
      buildRelationshipSchema({ cardinality: "many", kind: "Profile", optional: false }),
    ];
    const isUpdate = true;

    // WHEN
    const result = getRelationshipsForForm(relationships, isUpdate);

    // THEN
    expect(result).toEqual([relationships[0], relationships[1]]);
  });
});
