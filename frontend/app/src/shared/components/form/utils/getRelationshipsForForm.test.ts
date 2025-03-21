import { getRelationshipsForForm } from "@/shared/components/form/utils/getRelationshipsForForm";
import { describe, expect, it } from "vitest";
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

  it("returns a relationship if cardinality is one and kind is not Template", () => {
    // GIVEN
    const relationships = [
      buildRelationshipSchema({ cardinality: "one", kind: "Generic" }),
      buildRelationshipSchema({ cardinality: "one", kind: "Attribute" }),
      buildRelationshipSchema({ cardinality: "one", kind: "Parent" }),
    ];

    // WHEN
    const result = getRelationshipsForForm(relationships);

    // THEN
    expect(result).toEqual(relationships);
  });

  it("excludes relationships with cardinality one and kind Template", () => {
    // GIVEN
    const relationships = [
      buildRelationshipSchema({ cardinality: "one", kind: "Template" }),
      buildRelationshipSchema({ cardinality: "one", kind: "Generic" }),
    ];

    // WHEN
    const result = getRelationshipsForForm(relationships);

    // THEN
    expect(result).toEqual([relationships[1]]);
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

  it("When update, returns only relationships of cardinality one or with kind Attribute or Parent", () => {
    // GIVEN
    const relationships = [
      buildRelationshipSchema({ cardinality: "one", kind: "Generic" }),
      buildRelationshipSchema({ cardinality: "many", kind: "Attribute", optional: false }),
      buildRelationshipSchema({ cardinality: "many", kind: "Parent", optional: false }),
      buildRelationshipSchema({ cardinality: "many", kind: "Generic", optional: false }),
      buildRelationshipSchema({ cardinality: "many", kind: "Component", optional: false }),
    ];
    const isUpdate = true;

    // WHEN
    const result = getRelationshipsForForm(relationships, isUpdate);

    // THEN
    expect(result).toEqual([relationships[0], relationships[1], relationships[2]]);
  });

  it("When update, excludes mandatory relationships that are not of kind Attribute or Parent", () => {
    // GIVEN
    const relationships = [
      buildRelationshipSchema({ cardinality: "many", kind: "Generic", optional: false }),
      buildRelationshipSchema({ cardinality: "many", kind: "Component", optional: false }),
      buildRelationshipSchema({ cardinality: "many", kind: "Hierarchy", optional: false }),
    ];
    const isUpdate = true;

    // WHEN
    const result = getRelationshipsForForm(relationships, isUpdate);

    // THEN
    expect(result).toEqual([]);
  });

  it("When update, excludes relationships with cardinality one and kind Template", () => {
    // GIVEN
    const relationships = [
      buildRelationshipSchema({ cardinality: "one", kind: "Template" }),
      buildRelationshipSchema({ cardinality: "one", kind: "Generic" }),
    ];
    const isUpdate = true;

    // WHEN
    const result = getRelationshipsForForm(relationships, isUpdate);

    // THEN
    expect(result).toEqual([relationships[1]]);
  });
});
