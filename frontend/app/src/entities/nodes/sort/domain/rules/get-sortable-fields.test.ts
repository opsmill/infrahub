import { beforeEach, describe, expect, it } from "vitest";

import { store } from "@/shared/stores";

import { getSortableFields } from "@/entities/nodes/sort/domain/rules/get-sortable-fields";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../tests/fake/schema";

const NODE_METADATA_FIELDS = [
  { field: "node_metadata__created_at", label: "Created at" },
  { field: "node_metadata__updated_at", label: "Updated at" },
];

describe("getSortableFields", () => {
  beforeEach(() => {
    store.set(nodeSchemasAtom, []);
  });

  it("returns a `{attribute}__value` field per simple-valued attribute, plus node metadata fields", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({ name: "name", label: "Name", kind: "Text" }),
        generateAttributeSchema({ name: "weight", label: "Weight", kind: "Number" }),
      ],
      relationships: [],
    });

    // WHEN
    const fields = getSortableFields(schema);

    // THEN
    expect(fields).toEqual([
      { field: "name__value", label: "Name" },
      { field: "weight__value", label: "Weight" },
      ...NODE_METADATA_FIELDS,
    ]);
  });

  it("returns `{relationship}__{attribute}__value` fields for cardinality-one relationships only, ordered by peer attribute order_weight", () => {
    // GIVEN
    const site = generateNodeSchema({
      kind: "LocationSite",
      attributes: [
        generateAttributeSchema({ name: "name", label: "Name", kind: "Text", order_weight: 2000 }),
        generateAttributeSchema({
          name: "description",
          label: "Description",
          kind: "Text",
          order_weight: 1000,
        }),
        generateAttributeSchema({ name: "metadata", kind: "JSON" }),
      ],
      relationships: [],
    });
    store.set(nodeSchemasAtom, [site]);
    const schema = generateNodeSchema({
      attributes: [],
      relationships: [
        generateRelationshipSchema({
          name: "site",
          label: "Site",
          peer: "LocationSite",
          cardinality: "one",
        }),
        generateRelationshipSchema({
          name: "interfaces",
          peer: "LocationSite",
          cardinality: "many",
        }),
      ],
    });

    // WHEN
    const fields = getSortableFields(schema);

    // THEN
    expect(fields).toEqual([
      { field: "site__description__value", label: "Site › Description" },
      { field: "site__name__value", label: "Site › Name" },
      ...NODE_METADATA_FIELDS,
    ]);
  });

  it("skips relationships whose peer schema cannot be resolved", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [generateAttributeSchema({ name: "name", label: "Name", kind: "Text" })],
      relationships: [
        generateRelationshipSchema({ name: "site", peer: "UnknownKind", cardinality: "one" }),
      ],
    });

    // WHEN
    const fields = getSortableFields(schema);

    // THEN
    expect(fields).toEqual([{ field: "name__value", label: "Name" }, ...NODE_METADATA_FIELDS]);
  });
});
