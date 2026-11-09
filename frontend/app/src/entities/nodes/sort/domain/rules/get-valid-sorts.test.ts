import { beforeEach, describe, expect, it } from "vitest";

import { store } from "@/shared/stores";

import { getValidSorts } from "@/entities/nodes/sort/domain/rules/get-valid-sorts";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../tests/fake/schema";

describe("getValidSorts", () => {
  beforeEach(() => {
    store.set(nodeSchemasAtom, []);
  });

  it("keeps sortable attribute, relationship and node metadata fields", () => {
    // GIVEN
    const site = generateNodeSchema({
      kind: "LocationSite",
      attributes: [generateAttributeSchema({ name: "name", kind: "Text" })],
      relationships: [],
    });
    store.set(nodeSchemasAtom, [site]);
    const schema = generateNodeSchema({
      attributes: [generateAttributeSchema({ name: "name", kind: "Text" })],
      relationships: [
        generateRelationshipSchema({ name: "site", peer: "LocationSite", cardinality: "one" }),
      ],
    });
    const sorts = [
      { field: "name__value", direction: "ASC" },
      { field: "site__name__value", direction: "DESC" },
      { field: "node_metadata__created_at", direction: "ASC" },
      { field: "node_metadata__updated_at", direction: "DESC" },
    ] as const;

    // WHEN
    const validSorts = getValidSorts([...sorts], schema);

    // THEN
    expect(validSorts).toEqual([...sorts]);
  });

  it("drops fields that are not sortable on the schema", () => {
    // GIVEN
    const site = generateNodeSchema({
      kind: "LocationSite",
      attributes: [generateAttributeSchema({ name: "name", kind: "Text" })],
      relationships: [],
    });
    store.set(nodeSchemasAtom, [site]);
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({ name: "name", kind: "Text" }),
        generateAttributeSchema({ name: "config", kind: "JSON" }),
      ],
      relationships: [
        generateRelationshipSchema({
          name: "interfaces",
          peer: "LocationSite",
          cardinality: "many",
        }),
        generateRelationshipSchema({ name: "device", peer: "UnknownKind", cardinality: "one" }),
      ],
    });

    // WHEN
    const validSorts = getValidSorts(
      [
        { field: "name__value", direction: "ASC" },
        { field: "owner__value", direction: "ASC" },
        { field: "config__value", direction: "ASC" },
        { field: "interfaces__name__value", direction: "ASC" },
        { field: "device__name__value", direction: "ASC" },
        { field: "name__value: ASC}) {password", direction: "ASC" },
      ],
      schema
    );

    // THEN
    expect(validSorts).toEqual([{ field: "name__value", direction: "ASC" }]);
  });

  it("keeps a custom sort on a schema default-order sub-property field", () => {
    // GIVEN
    const schema = generateNodeSchema({
      order_by: ["prefix__version", "prefix__binary_address"],
      attributes: [generateAttributeSchema({ name: "prefix", kind: "IPNetwork" })],
      relationships: [],
    });
    const sorts = [{ field: "prefix__version", direction: "DESC" }] as const;

    // WHEN
    const validSorts = getValidSorts([...sorts], schema);

    // THEN
    expect(validSorts).toEqual([...sorts]);
  });

  it("keeps only the first occurrence of a duplicated field", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [generateAttributeSchema({ name: "name", kind: "Text" })],
      relationships: [],
    });

    // WHEN
    const validSorts = getValidSorts(
      [
        { field: "name__value", direction: "ASC" },
        { field: "name__value", direction: "DESC" },
      ],
      schema
    );

    // THEN
    expect(validSorts).toEqual([{ field: "name__value", direction: "ASC" }]);
  });

  it("returns an empty list untouched without deriving anything", () => {
    // GIVEN
    const schema = generateNodeSchema({ attributes: [], relationships: [] });

    // WHEN
    const validSorts = getValidSorts([], schema);

    // THEN
    expect(validSorts).toEqual([]);
  });
});
