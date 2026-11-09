import { describe, expect, it } from "vitest";

import {
  buildAttributeSortField,
  buildRelationshipSortField,
} from "@/entities/nodes/sort/domain/rules/sort-field";

describe("buildAttributeSortField", () => {
  it("builds the `{attribute}__value` sort field of an attribute", () => {
    // GIVEN
    const attributeName = "name";

    // WHEN
    const field = buildAttributeSortField(attributeName);

    // THEN
    expect(field).toBe("name__value");
  });
});

describe("buildRelationshipSortField", () => {
  it("prefixes an attribute sort field with the relationship name", () => {
    // GIVEN
    const attributeField = buildAttributeSortField("name");

    // WHEN
    const field = buildRelationshipSortField("site", attributeField);

    // THEN
    expect(field).toBe("site__name__value");
  });
});
