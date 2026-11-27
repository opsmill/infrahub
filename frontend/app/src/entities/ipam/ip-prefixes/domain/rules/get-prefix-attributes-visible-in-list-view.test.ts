import { describe, expect, it } from "vitest";

import { generateAttributeSchema } from "../../../../../../tests/fake/schema";
import { getPrefixAttributesVisibleInListView } from "./get-prefix-attributes-visible-in-list-view";

describe("getPrefixAttributesVisibleInListView", () => {
  it("should leave out the prefix fields and the List, JSON, Any and password kinds", () => {
    // GIVEN
    const attributes = [
      generateAttributeSchema({ name: "prefix", kind: "IPNetwork" }),
      generateAttributeSchema({ name: "description", kind: "TextArea" }),
      generateAttributeSchema({ name: "tags", kind: "List" }),
      generateAttributeSchema({ name: "config", kind: "JSON" }),
      generateAttributeSchema({ name: "anything", kind: "Any" }),
      generateAttributeSchema({ name: "secret", kind: "Password" }),
      generateAttributeSchema({ name: "hashed", kind: "HashedPassword" }),
    ];

    // WHEN
    const result = getPrefixAttributesVisibleInListView(attributes);

    // THEN
    expect(result.map(({ name }) => name)).toEqual(["description"]);
  });
});
