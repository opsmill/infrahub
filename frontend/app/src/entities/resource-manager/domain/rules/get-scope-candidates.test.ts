import { describe, expect, it } from "vitest";

import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/domain/model/schema";

import { generateGenericSchema, generateNodeSchema } from "../../../../../tests/fake/schema";
import { getScopeCandidates } from "./get-scope-candidates";

const baseAttribute = generateNodeSchema().attributes![0]!;
const baseRelationship = generateNodeSchema().relationships![0]!;

const attribute = (overrides: Partial<AttributeSchema>): AttributeSchema =>
  ({ ...baseAttribute, ...overrides }) as AttributeSchema;

const relationship = (overrides: Partial<RelationshipSchema>): RelationshipSchema => ({
  ...baseRelationship,
  kind: "Generic",
  ...overrides,
});

describe("getScopeCandidates", () => {
  const schema = generateNodeSchema({
    attributes: [
      attribute({ name: "role", label: "Role", kind: "Dropdown", optional: false }),
      attribute({ name: "description", label: "Description", kind: "Text", optional: true }),
      attribute({ name: "tags_list", label: "Tag names", kind: "List", optional: false }),
      attribute({ name: "data", label: "Data", kind: "JSON", optional: false }),
      attribute({ name: "vlan_id", label: "VLAN ID", kind: "Number", optional: false }),
    ],
    relationships: [
      relationship({
        name: "site",
        label: "Site",
        peer: "LocationSite",
        cardinality: "one",
        optional: false,
      }),
      relationship({
        name: "rack",
        label: "Rack",
        peer: "LocationRack",
        cardinality: "one",
        optional: true,
      }),
      relationship({
        name: "interfaces",
        label: "Interfaces",
        peer: "InfraInterface",
        cardinality: "many",
        optional: false,
      }),
    ],
  });

  it("lists every attribute and relationship of the kind with the reason it cannot be chosen", () => {
    // GIVEN
    const nodeAttribute = "vlan_id";

    // WHEN
    const candidates = getScopeCandidates(schema, nodeAttribute);

    // THEN
    expect(candidates).toEqual([
      { name: "role", label: "Role", type: "attribute", detail: "Dropdown" },
      {
        name: "description",
        label: "Description",
        type: "attribute",
        detail: "Text",
        unavailableReason: "Optional",
      },
      { name: "tags_list", label: "Tag names", type: "attribute", detail: "List" },
      { name: "data", label: "Data", type: "attribute", detail: "JSON" },
      {
        name: "vlan_id",
        label: "VLAN ID",
        type: "attribute",
        detail: "Number",
        unavailableReason: "This is the attribute the pool allocates",
      },
      { name: "site", label: "Site", type: "relationship", detail: "LocationSite" },
      {
        name: "rack",
        label: "Rack",
        type: "relationship",
        detail: "LocationRack",
        unavailableReason: "Optional",
      },
      {
        name: "interfaces",
        label: "Interfaces",
        type: "relationship",
        detail: "InfraInterface",
        unavailableReason: "Relationships of cardinality many can't be used",
      },
    ]);
  });

  it("refuses an optional List or JSON attribute as optional", () => {
    // GIVEN
    const optionalStructured = generateNodeSchema({
      attributes: [
        attribute({ name: "tags_list", label: "Tag names", kind: "List", optional: true }),
        attribute({ name: "data", label: "Data", kind: "JSON", optional: true }),
      ],
      relationships: [],
    });

    // WHEN
    const candidates = getScopeCandidates(optionalStructured, "number");

    // THEN
    expect(candidates.map(({ unavailableReason }) => unavailableReason)).toEqual([
      "Optional",
      "Optional",
    ]);
  });

  it("uses the field name when the field has no label", () => {
    // GIVEN
    const unlabelled = generateNodeSchema({
      attributes: [attribute({ name: "serial", label: null, kind: "Text", optional: false })],
      relationships: [],
    });

    // WHEN
    const candidates = getScopeCandidates(unlabelled, "number");

    // THEN
    expect(candidates).toEqual([
      { name: "serial", label: "serial", type: "attribute", detail: "Text" },
    ]);
  });

  it("lists the fields of a generic schema", () => {
    // GIVEN
    const generic = generateGenericSchema({
      attributes: [attribute({ name: "name", label: "Name", kind: "Text", optional: false })],
      relationships: [
        relationship({
          name: "device",
          label: "Device",
          peer: "InfraDevice",
          cardinality: "one",
          optional: false,
        }),
      ],
    });

    // WHEN
    const candidates = getScopeCandidates(generic, "number");

    // THEN
    expect(candidates).toEqual([
      { name: "name", label: "Name", type: "attribute", detail: "Text" },
      { name: "device", label: "Device", type: "relationship", detail: "InfraDevice" },
    ]);
  });

  it("returns only bare field names, with no path into a related node", () => {
    // GIVEN
    const nodeAttribute = "vlan_id";

    // WHEN
    const candidates = getScopeCandidates(schema, nodeAttribute);

    // THEN
    expect(candidates.every((candidate) => !candidate.name.includes("__"))).toBe(true);
  });

  it("leaves out the group, profile and template relationships that every kind has", () => {
    // GIVEN
    const withSystemRelationships = generateNodeSchema({
      attributes: [],
      relationships: [
        relationship({ name: "member_of_groups", kind: "Group", cardinality: "many" }),
        relationship({ name: "subscriber_of_groups", kind: "Group", cardinality: "many" }),
        relationship({ name: "profiles", kind: "Profile", cardinality: "many" }),
        relationship({ name: "object_template", kind: "Template", cardinality: "one" }),
        relationship({
          name: "parent",
          label: "Parent",
          peer: "LocationRegion",
          kind: "Hierarchy",
          cardinality: "one",
          optional: false,
        }),
        relationship({
          name: "device",
          label: "Device",
          peer: "InfraDevice",
          kind: "Parent",
          cardinality: "one",
          optional: false,
        }),
      ],
    });

    // WHEN
    const candidates = getScopeCandidates(withSystemRelationships, "number");

    // THEN
    expect(candidates).toEqual([
      { name: "parent", label: "Parent", type: "relationship", detail: "LocationRegion" },
      { name: "device", label: "Device", type: "relationship", detail: "InfraDevice" },
    ]);
  });

  it("returns no candidates for a kind without fields", () => {
    // GIVEN
    const empty = generateNodeSchema({ attributes: undefined, relationships: undefined });

    // WHEN
    const candidates = getScopeCandidates(empty, "number");

    // THEN
    expect(candidates).toEqual([]);
  });
});
