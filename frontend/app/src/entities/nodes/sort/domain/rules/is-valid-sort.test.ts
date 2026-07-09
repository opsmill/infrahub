import { beforeEach, describe, expect, it } from "vitest";

import { store } from "@/shared/stores";

import { isValidSort } from "@/entities/nodes/sort/domain/rules/is-valid-sort";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../tests/fake/schema";

describe("isValidSort", () => {
  beforeEach(() => {
    store.set(nodeSchemasAtom, []);
  });

  it("accepts sortable attribute, relationship and node metadata fields", () => {
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

    // WHEN
    const attributeSort = isValidSort({ field: "name__value", direction: "ASC" }, schema);
    const relationshipSort = isValidSort({ field: "site__name__value", direction: "ASC" }, schema);
    const metadataSort = isValidSort(
      { field: "node_metadata__created_at", direction: "ASC" },
      schema
    );

    // THEN
    expect(attributeSort).toBe(true);
    expect(relationshipSort).toBe(true);
    expect(metadataSort).toBe(true);
  });

  it("rejects fields that are not sortable on the schema", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({ name: "name", kind: "Text" }),
        generateAttributeSchema({ name: "config", kind: "JSON" }),
      ],
      relationships: [],
    });

    // WHEN
    const unknownAttribute = isValidSort({ field: "owner__value", direction: "ASC" }, schema);
    const unsortableKind = isValidSort({ field: "config__value", direction: "ASC" }, schema);
    const hostileToken = isValidSort(
      { field: "name__value: ASC}) {password", direction: "ASC" },
      schema
    );

    // THEN
    expect(unknownAttribute).toBe(false);
    expect(unsortableKind).toBe(false);
    expect(hostileToken).toBe(false);
  });
});
