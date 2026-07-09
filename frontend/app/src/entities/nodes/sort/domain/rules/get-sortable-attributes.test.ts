import { describe, expect, it } from "vitest";

import { getSortableAttributes } from "@/entities/nodes/sort/domain/rules/get-sortable-attributes";

import { generateAttributeSchema } from "../../../../../../tests/fake/schema";

describe("getSortableAttributes", () => {
  it("returns a `{attribute}__value` field per attribute, labelled with the attribute label or its name", () => {
    // GIVEN
    const attributes = [
      generateAttributeSchema({ name: "name", label: "Name", kind: "Text" }),
      generateAttributeSchema({ name: "weight", label: null, kind: "Number" }),
    ];

    // WHEN
    const fields = getSortableAttributes(attributes);

    // THEN
    expect(fields).toEqual([
      { field: "name__value", label: "Name" },
      { field: "weight__value", label: "weight" },
    ]);
  });

  it("excludes attributes with complex or unorderable kinds", () => {
    // GIVEN
    const attributes = [
      generateAttributeSchema({ name: "name", label: "Name", kind: "Text" }),
      generateAttributeSchema({ name: "config", kind: "JSON" }),
      generateAttributeSchema({ name: "tags", kind: "List" }),
      generateAttributeSchema({ name: "payload", kind: "Any" }),
      generateAttributeSchema({ name: "secret", kind: "Password" }),
      generateAttributeSchema({ name: "token", kind: "HashedPassword" }),
    ];

    // WHEN
    const fields = getSortableAttributes(attributes);

    // THEN
    expect(fields).toEqual([{ field: "name__value", label: "Name" }]);
  });
});
