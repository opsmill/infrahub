import { describe, expect, it } from "vitest";

import type { AttributeSchema } from "@/entities/schema/types";

import { generateAttributeSchema } from "../../../../../tests/fake/schema";
import { getAttributesVisibleInListView } from "./get-attributes-visible-in-list-view";

describe("getAttributesVisibleInListView", () => {
  it("should return only attributes that should be visible in list view", () => {
    // GIVEN
    const attributes: AttributeSchema[] = [
      generateAttributeSchema({ name: "id", kind: "ID", label: "ID" }),
      generateAttributeSchema({ name: "text", kind: "Text", label: "Text" }),
      generateAttributeSchema({ name: "number", kind: "Number", label: "Number" }),
      generateAttributeSchema({ name: "boolean", kind: "Boolean", label: "Boolean" }),
      generateAttributeSchema({ name: "dropdown", kind: "Dropdown", label: "Dropdown" }),
      generateAttributeSchema({ name: "textarea", kind: "TextArea", label: "TextArea" }),
      generateAttributeSchema({ name: "datetime", kind: "DateTime", label: "DateTime" }),
      generateAttributeSchema({ name: "email", kind: "Email", label: "Email" }),
      generateAttributeSchema({ name: "password", kind: "Password", label: "Password" }),
      generateAttributeSchema({ name: "url", kind: "URL", label: "URL" }),
      generateAttributeSchema({ name: "file", kind: "File", label: "File" }),
      generateAttributeSchema({ name: "macaddress", kind: "MacAddress", label: "MacAddress" }),
      generateAttributeSchema({ name: "color", kind: "Color", label: "Color" }),
      generateAttributeSchema({ name: "bandwidth", kind: "Bandwidth", label: "Bandwidth" }),
      generateAttributeSchema({ name: "iphost", kind: "IPHost", label: "IPHost" }),
      generateAttributeSchema({ name: "ipnetwork", kind: "IPNetwork", label: "IPNetwork" }),
      generateAttributeSchema({ name: "checkbox", kind: "Checkbox", label: "Checkbox" }),
      generateAttributeSchema({ name: "list", kind: "List", label: "List" }),
      generateAttributeSchema({ name: "json", kind: "JSON", label: "JSON" }),
      generateAttributeSchema({ name: "any", kind: "Any", label: "Any" }),
    ];

    // WHEN
    const result = getAttributesVisibleInListView(attributes);

    // THEN
    expect(result.map((attr) => attr.kind)).toEqual([
      "Text",
      "Number",
      "Boolean",
      "Dropdown",
      "DateTime",
      "Email",
      "URL",
      "File",
      "MacAddress",
      "Color",
      "Bandwidth",
      "IPHost",
      "IPNetwork",
    ]);
  });

  it("should return empty array when no attributes are provided", () => {
    // WHEN
    const result = getAttributesVisibleInListView([]);

    // THEN
    expect(result).toEqual([]);
  });

  it("should handle attributes with missing kind", () => {
    // GIVEN
    const attributes = [
      generateAttributeSchema({ name: "text", kind: "Text", label: "Text" }),
      generateAttributeSchema({ name: "nope", kind: "Nope", label: "Nope" }) as AttributeSchema,
    ];

    // WHEN
    const result = getAttributesVisibleInListView(attributes);

    // THEN
    expect(result).toHaveLength(1);
    expect(result[0]!.kind).toBe("Text");
  });
});
