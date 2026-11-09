import { describe, expect, it } from "vitest";

import { generateRelationshipSchema } from "../../../../../../tests/fake/schema";
import { isRelationshipVisibleInSummary } from "./is-relationship-visible-in-summary";

describe("isRelationshipVisibleInSummary", () => {
  it("should show an Attribute relationship", () => {
    // GIVEN
    const relationship = generateRelationshipSchema({ name: "resources", kind: "Attribute" });

    // WHEN
    const result = isRelationshipVisibleInSummary(relationship);

    // THEN
    expect(result).toBe(true);
  });

  it("should hide member_of_groups", () => {
    // GIVEN
    const relationship = generateRelationshipSchema({ name: "member_of_groups", kind: "Group" });

    // WHEN
    const result = isRelationshipVisibleInSummary(relationship);

    // THEN
    expect(result).toBe(false);
  });

  it("should hide subscriber_of_groups", () => {
    // GIVEN
    const relationship = generateRelationshipSchema({
      name: "subscriber_of_groups",
      kind: "Group",
    });

    // WHEN
    const result = isRelationshipVisibleInSummary(relationship);

    // THEN
    expect(result).toBe(false);
  });

  it("should hide profiles", () => {
    // GIVEN
    const relationship = generateRelationshipSchema({ name: "profiles", kind: "Profile" });

    // WHEN
    const result = isRelationshipVisibleInSummary(relationship);

    // THEN
    expect(result).toBe(false);
  });

  it("should hide a from-resource-pool relationship", () => {
    // GIVEN
    const relationship = generateRelationshipSchema({
      name: "address_from_resource_pool",
      kind: "Attribute",
    });

    // WHEN
    const result = isRelationshipVisibleInSummary(relationship);

    // THEN
    expect(result).toBe(false);
  });

  it("should hide a cardinality-many Generic relationship", () => {
    // GIVEN
    const relationship = generateRelationshipSchema({
      name: "children",
      kind: "Generic",
      cardinality: "many",
    });

    // WHEN
    const result = isRelationshipVisibleInSummary(relationship);

    // THEN
    expect(result).toBe(false);
  });
});
