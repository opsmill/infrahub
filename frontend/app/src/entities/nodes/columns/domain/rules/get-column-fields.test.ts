import { describe, expect, it } from "vitest";

import {
  IP_ADDRESS_COLUMN_SURFACE,
  IP_PREFIX_COLUMN_SURFACE,
  OBJECT_COLUMN_SURFACE,
  RELATIONSHIP_COLUMN_SURFACE,
} from "@/entities/nodes/columns/domain/rules/column-surfaces";
import { getColumnFields } from "@/entities/nodes/columns/domain/rules/get-column-fields";

import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../tests/fake/schema";

describe("getColumnFields", () => {
  it("lists a default-visible attribute as visible by default, falling back to its name for a label", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({ name: "name", kind: "Text", label: "Name" }),
        generateAttributeSchema({ name: "internal_note", kind: "Text", label: null }),
      ],
      relationships: [],
    });

    // WHEN
    const fields = getColumnFields(schema, OBJECT_COLUMN_SURFACE);

    // THEN
    expect(
      fields.map(({ name, label, isDefaultVisible }) => ({ name, label, isDefaultVisible }))
    ).toEqual([
      { name: "name", label: "Name", isDefaultVisible: true },
      { name: "internal_note", label: "internal_note", isDefaultVisible: true },
    ]);
  });

  it("lists an `extra` attribute as hidden by default on the object surface", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({ name: "name", kind: "Text" }),
        generateAttributeSchema({ name: "internal_note", kind: "Text", display: "extra" }),
      ],
      relationships: [],
    });

    // WHEN
    const fields = getColumnFields(schema, OBJECT_COLUMN_SURFACE);

    // THEN
    expect(fields.map(({ name, isDefaultVisible }) => ({ name, isDefaultVisible }))).toEqual([
      { name: "name", isDefaultVisible: true },
      { name: "internal_note", isDefaultVisible: false },
    ]);
  });

  it("never lists an attribute whose kind the list view cannot render, even when revealable", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({ name: "name", kind: "Text" }),
        generateAttributeSchema({ name: "config", kind: "JSON" }),
        generateAttributeSchema({ name: "secret", kind: "Password" }),
      ],
      relationships: [],
    });

    // WHEN
    const fields = getColumnFields(schema, OBJECT_COLUMN_SURFACE);

    // THEN
    expect(fields.map(({ name }) => name)).toEqual(["name"]);
  });

  it("lists a cardinality-one `Attribute` relationship", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [],
      relationships: [
        generateRelationshipSchema({
          name: "site",
          kind: "Attribute",
          cardinality: "one",
          label: "Site",
        }),
      ],
    });

    // WHEN
    const fields = getColumnFields(schema, OBJECT_COLUMN_SURFACE);

    // THEN
    expect(
      fields.map(({ name, label, isDefaultVisible }) => ({ name, label, isDefaultVisible }))
    ).toEqual([{ name: "site", label: "Site", isDefaultVisible: true }]);
  });

  it("excludes a resource-pool relationship on the object surface but keeps it on the IPAM surfaces", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [],
      relationships: [
        generateRelationshipSchema({
          name: "primary_ip_from_resource_pool",
          kind: "Generic",
          cardinality: "one",
        }),
      ],
    });

    // WHEN
    const objectFields = getColumnFields(schema, OBJECT_COLUMN_SURFACE);
    const ipAddressFields = getColumnFields(schema, IP_ADDRESS_COLUMN_SURFACE);

    // THEN
    expect({
      object: objectFields.map(({ name }) => name),
      ipAddress: ipAddressFields.map(({ name }) => name),
    }).toEqual({ object: [], ipAddress: ["primary_ip_from_resource_pool"] });
  });

  it("excludes group and profile relationships the list view never renders", () => {
    // GIVEN
    const schema = generateNodeSchema({ attributes: [] });

    // WHEN
    const fields = getColumnFields(schema, OBJECT_COLUMN_SURFACE);

    // THEN
    expect(fields.map(({ name }) => name)).toEqual([]);
  });

  it("orders the object surface fields by order weight, attributes and relationships together", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({ name: "description", kind: "Text", order_weight: 3000 }),
        generateAttributeSchema({ name: "name", kind: "Text", order_weight: 1000 }),
      ],
      relationships: [
        generateRelationshipSchema({
          name: "site",
          kind: "Attribute",
          cardinality: "one",
          order_weight: 2000,
        }),
      ],
    });

    // WHEN
    const fields = getColumnFields(schema, OBJECT_COLUMN_SURFACE);

    // THEN
    expect(fields.map(({ name }) => name)).toEqual(["name", "site", "description"]);
  });

  it("excludes the IP address attribute but keeps an `extra` attribute on the IP address surface", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({ name: "address", kind: "IPHost" }),
        generateAttributeSchema({ name: "description", kind: "Text" }),
        generateAttributeSchema({ name: "internal_note", kind: "Text", display: "extra" }),
      ],
      relationships: [],
    });

    // WHEN
    const fields = getColumnFields(schema, IP_ADDRESS_COLUMN_SURFACE);

    // THEN
    expect(fields.map(({ name }) => name)).toEqual(["description", "internal_note"]);
  });

  it("lists the ip_prefix relationship exactly once on the IP address surface", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [],
      relationships: [
        generateRelationshipSchema({ name: "ip_prefix", kind: "Attribute", cardinality: "one" }),
      ],
    });

    // WHEN
    const fields = getColumnFields(schema, IP_ADDRESS_COLUMN_SURFACE);

    // THEN
    expect(fields.map(({ name }) => name)).toEqual(["ip_prefix"]);
  });

  it("never lists the fixed column ids on any surface", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({ name: "id", kind: "Text" }),
        generateAttributeSchema({ name: "objectKind", kind: "Text" }),
        generateAttributeSchema({ name: "actions", kind: "Text" }),
        generateAttributeSchema({ name: "description", kind: "Text" }),
      ],
      relationships: [],
    });

    // WHEN
    const fieldsBySurface = [
      OBJECT_COLUMN_SURFACE,
      RELATIONSHIP_COLUMN_SURFACE,
      IP_ADDRESS_COLUMN_SURFACE,
      IP_PREFIX_COLUMN_SURFACE,
    ].map((surface) => getColumnFields(schema, surface).map(({ name }) => name));

    // THEN
    expect(fieldsBySurface).toEqual([
      ["description"],
      ["description"],
      ["description"],
      ["description"],
    ]);
  });

  it("returns only default-visible fields on the surfaces that cannot reveal", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({ name: "description", kind: "Text" }),
        generateAttributeSchema({ name: "internal_note", kind: "Text", display: "extra" }),
      ],
      relationships: [],
    });

    // WHEN
    const fieldsBySurface = [
      RELATIONSHIP_COLUMN_SURFACE,
      IP_ADDRESS_COLUMN_SURFACE,
      IP_PREFIX_COLUMN_SURFACE,
    ].map((surface) => getColumnFields(schema, surface));

    // THEN
    expect(
      fieldsBySurface.every((fields) => fields.every(({ isDefaultVisible }) => isDefaultVisible))
    ).toBe(true);
  });
});
