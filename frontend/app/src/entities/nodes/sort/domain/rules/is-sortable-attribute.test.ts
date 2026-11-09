import { describe, expect, it } from "vitest";

import { isSortableAttribute } from "@/entities/nodes/sort/domain/rules/is-sortable-attribute";

import { generateAttributeSchema } from "../../../../../../tests/fake/schema";

describe("isSortableAttribute", () => {
  it("accepts simple-valued kinds", () => {
    // GIVEN
    const attribute = generateAttributeSchema({ name: "name", kind: "Text" });

    // WHEN
    const result = isSortableAttribute(attribute);

    // THEN
    expect(result).toBe(true);
  });

  it("rejects complex or unorderable kinds", () => {
    // GIVEN
    const attributes = [
      generateAttributeSchema({ name: "config", kind: "JSON" }),
      generateAttributeSchema({ name: "tags", kind: "List" }),
      generateAttributeSchema({ name: "payload", kind: "Any" }),
      generateAttributeSchema({ name: "secret", kind: "Password" }),
      generateAttributeSchema({ name: "token", kind: "HashedPassword" }),
    ];

    // WHEN
    const results = attributes.map(isSortableAttribute);

    // THEN
    expect(results).toEqual([false, false, false, false, false]);
  });
});
