import { describe, expect, it } from "vitest";

import { getRelationshipsForForm } from "@/shared/components/form/utils/getRelationshipsForForm";

import { generateRelationshipSchema } from "../../../../../tests/fake/schema";

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
      generateRelationshipSchema({ cardinality: "one", kind: "Generic" }),
      generateRelationshipSchema({ cardinality: "one", kind: "Attribute" }),
      generateRelationshipSchema({ cardinality: "one", kind: "Parent" }),
    ];

    // WHEN
    const result = getRelationshipsForForm(relationships);

    // THEN
    expect(result).toEqual(relationships);
  });

  it("excludes relationships with cardinality one and kind Template", () => {
    // GIVEN
    const relationships = [
      generateRelationshipSchema({ cardinality: "one", kind: "Template" }),
      generateRelationshipSchema({ cardinality: "one", kind: "Generic" }),
    ];

    // WHEN
    const result = getRelationshipsForForm(relationships);

    // THEN
    expect(result).toEqual([relationships[1]]);
  });

  it("returns a relationship of cardinality many if kind is Attribute or Parent", () => {
    // GIVEN
    const relationships = [
      generateRelationshipSchema({ cardinality: "many", kind: "Attribute" }),
      generateRelationshipSchema({ cardinality: "many", kind: "Parent" }),
    ];

    // WHEN
    const result = getRelationshipsForForm(relationships);

    // THEN
    expect(result).toEqual(relationships);
  });

  it("should not return a relationship of cardinality many if kind is Generic/Component/Hierarchy", () => {
    // GIVEN
    const relationships = [
      generateRelationshipSchema({ cardinality: "many", kind: "Generic" }),
      generateRelationshipSchema({ cardinality: "many", kind: "Component" }),
      generateRelationshipSchema({ cardinality: "many", kind: "Hierarchy" }),
      generateRelationshipSchema({ cardinality: "many", kind: "Group" }),
      generateRelationshipSchema({ cardinality: "many", kind: "Profile" }),
    ];

    // WHEN
    const result = getRelationshipsForForm(relationships);

    // THEN
    expect(result).toEqual([]);
  });

  it("returns a relationship of cardinality many if it's mandatory field", () => {
    // GIVEN
    const relationships = [
      generateRelationshipSchema({ cardinality: "many", kind: "Attribute", optional: false }),
      generateRelationshipSchema({ cardinality: "many", kind: "Parent", optional: false }),
      generateRelationshipSchema({ cardinality: "many", kind: "Generic", optional: false }),
      generateRelationshipSchema({ cardinality: "many", kind: "Component", optional: false }),
      generateRelationshipSchema({ cardinality: "many", kind: "Hierarchy", optional: false }),
      generateRelationshipSchema({ cardinality: "many", kind: "Group", optional: false }),
      generateRelationshipSchema({ cardinality: "many", kind: "Profile", optional: false }),
    ];

    // WHEN
    const result = getRelationshipsForForm(relationships);

    // THEN
    expect(result).toEqual(relationships);
  });

  it("When update, returns only relationships of cardinality one or with kind Attribute or Parent", () => {
    // GIVEN
    const relationships = [
      generateRelationshipSchema({ cardinality: "one", kind: "Generic" }),
      generateRelationshipSchema({ cardinality: "many", kind: "Attribute", optional: false }),
      generateRelationshipSchema({ cardinality: "many", kind: "Parent", optional: false }),
      generateRelationshipSchema({ cardinality: "many", kind: "Generic", optional: false }),
      generateRelationshipSchema({ cardinality: "many", kind: "Component", optional: false }),
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
      generateRelationshipSchema({ cardinality: "many", kind: "Generic", optional: false }),
      generateRelationshipSchema({ cardinality: "many", kind: "Component", optional: false }),
      generateRelationshipSchema({ cardinality: "many", kind: "Hierarchy", optional: false }),
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
      generateRelationshipSchema({ cardinality: "one", kind: "Template" }),
      generateRelationshipSchema({ cardinality: "one", kind: "Generic" }),
    ];
    const isUpdate = true;

    // WHEN
    const result = getRelationshipsForForm(relationships, isUpdate);

    // THEN
    expect(result).toEqual([relationships[1]]);
  });
});
