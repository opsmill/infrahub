import { describe, expect, it } from "vitest";

import { generateAttributeSchema } from "../../../../../../tests/fake/schema";
import { getIpAddressAttributesVisibleInListView } from "./get-ip-address-attributes-visible-in-list-view";

describe("getIpAddressAttributesVisibleInListView", () => {
  it("should leave out the address field and the List, JSON, Any and password kinds", () => {
    // GIVEN
    const attributes = [
      generateAttributeSchema({ name: "address", kind: "IPHost" }),
      generateAttributeSchema({ name: "description", kind: "TextArea" }),
      generateAttributeSchema({ name: "tags", kind: "List" }),
      generateAttributeSchema({ name: "config", kind: "JSON" }),
      generateAttributeSchema({ name: "anything", kind: "Any" }),
      generateAttributeSchema({ name: "secret", kind: "Password" }),
      generateAttributeSchema({ name: "hashed", kind: "HashedPassword" }),
    ];

    // WHEN
    const result = getIpAddressAttributesVisibleInListView(attributes);

    // THEN
    expect(result.map(({ name }) => name)).toEqual(["description"]);
  });
});
