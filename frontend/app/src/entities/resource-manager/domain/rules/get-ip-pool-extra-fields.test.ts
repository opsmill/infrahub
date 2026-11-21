import { describe, expect, it } from "vitest";

import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../tests/fake/schema";
import { getIpPoolExtraFields } from "./get-ip-pool-extra-fields";

describe("getIpPoolExtraFields", () => {
  it("keeps the attributes and relationships the page does not already show", () => {
    // GIVEN
    const schema = generateNodeSchema({
      kind: "CoreIPPrefixPool",
      attributes: [
        generateAttributeSchema({ name: "name" }),
        generateAttributeSchema({ name: "default_prefix_length", kind: "Number" }),
        generateAttributeSchema({ name: "contact" }),
      ],
      relationships: [
        generateRelationshipSchema({ name: "ip_namespace", kind: "Generic", cardinality: "one" }),
        generateRelationshipSchema({ name: "resources", kind: "Attribute", cardinality: "many" }),
        generateRelationshipSchema({ name: "site", kind: "Attribute", cardinality: "one" }),
        generateRelationshipSchema({ name: "tags", kind: "Attribute", cardinality: "many" }),
        generateRelationshipSchema({
          name: "member_of_groups",
          kind: "Group",
          cardinality: "many",
        }),
      ],
    });

    // WHEN
    const fields = getIpPoolExtraFields(schema);

    // THEN
    expect(fields.attributes.map(({ name }) => name)).toEqual(["contact"]);
    expect(fields.relationships.map(({ name }) => name)).toEqual(["site"]);
  });

  it("returns nothing for the core pool schema", () => {
    // GIVEN
    const schema = generateNodeSchema({
      kind: "CoreIPAddressPool",
      attributes: [
        generateAttributeSchema({ name: "name" }),
        generateAttributeSchema({ name: "description" }),
        generateAttributeSchema({ name: "default_address_type" }),
        generateAttributeSchema({ name: "default_prefix_length", kind: "Number" }),
      ],
      relationships: [
        generateRelationshipSchema({ name: "ip_namespace", kind: "Generic", cardinality: "one" }),
        generateRelationshipSchema({ name: "resources", kind: "Attribute", cardinality: "many" }),
      ],
    });

    // WHEN
    const fields = getIpPoolExtraFields(schema);

    // THEN
    expect(fields).toEqual({ attributes: [], relationships: [] });
  });
});
