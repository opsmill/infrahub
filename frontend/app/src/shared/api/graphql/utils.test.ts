import { describe, expect, it } from "vitest";

import type { Filter } from "@/shared/hooks/useFilters";

import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

import { generateAttributeSchema, generateRelationshipSchema } from "../../../../tests/fake/schema";
import { addAttributesToRequest, addFiltersToRequest, addRelationshipsToRequest } from "./utils";

describe("addAttributesToRequest", () => {
  it("should return base fragment for simple attribute", () => {
    // GIVEN
    const attributes: Array<AttributeSchema> = [
      generateAttributeSchema({ name: "test", kind: "Text" }),
    ];

    // WHEN
    const result = addAttributesToRequest(attributes);

    // THEN
    expect(result).toEqual({
      test: {
        id: true,
        value: true,
      },
    });
  });

  it("should add dropdown specific fields for dropdown attributes", () => {
    // GIVEN
    const attributes: Array<AttributeSchema> = [
      generateAttributeSchema({ name: "test", kind: "Dropdown" }),
    ];

    // WHEN
    const result = addAttributesToRequest(attributes);

    // THEN
    expect(result).toEqual({
      test: {
        id: true,
        value: true,
        color: true,
        description: true,
        label: true,
      },
    });
  });

  it("should add metadata fields when withMetadata is true", () => {
    // GIVEN
    const attributes: Array<AttributeSchema> = [
      generateAttributeSchema({ name: "test", kind: "Text" }),
    ];

    // WHEN
    const result = addAttributesToRequest(attributes, { withMetadata: true });

    // THEN
    expect(result).toEqual({
      test: {
        id: true,
        value: true,
        updated_at: true,
        is_default: true,
        is_from_profile: true,
        is_protected: true,
        source: {
          id: true,
          hfid: true,
          display_label: true,
          __typename: true,
        },
        owner: {
          id: true,
          hfid: true,
          display_label: true,
          __typename: true,
        },
      },
    });
  });

  it("should add permissions fields when withPermissions is true", () => {
    // GIVEN
    const attributes: Array<AttributeSchema> = [
      generateAttributeSchema({ name: "test", kind: "Text" }),
    ];

    // WHEN
    const result = addAttributesToRequest(attributes, { withPermissions: true });

    // THEN
    expect(result).toEqual({
      test: {
        id: true,
        value: true,
        permissions: {
          update_value: true,
        },
      },
    });
  });

  it("should add both metadata and permissions fields when both flags are true", () => {
    // GIVEN
    const attributes: Array<AttributeSchema> = [
      generateAttributeSchema({ name: "test", kind: "Text" }),
    ];

    // WHEN
    const result = addAttributesToRequest(attributes, {
      withMetadata: true,
      withPermissions: true,
    });

    // THEN
    expect(result).toEqual({
      test: {
        id: true,
        value: true,
        updated_at: true,
        is_default: true,
        is_from_profile: true,
        is_protected: true,
        source: {
          id: true,
          hfid: true,
          display_label: true,
          __typename: true,
        },
        owner: {
          id: true,
          hfid: true,
          display_label: true,
          __typename: true,
        },
        permissions: {
          update_value: true,
        },
      },
    });
  });
});

describe("addRelationshipsToRequest", () => {
  it("should return base fragment for one-to-one relationship", () => {
    // GIVEN
    const relationships: Array<RelationshipSchema> = [
      generateRelationshipSchema({ name: "test", cardinality: "one" }),
    ];

    // WHEN
    const result = addRelationshipsToRequest(relationships);

    // THEN
    expect(result).toEqual({
      test: {
        node: {
          id: true,
          hfid: true,
          display_label: true,
        },
      },
    });
  });

  it("should return edges fragment for one-to-many relationship", () => {
    // GIVEN
    const relationships: Array<RelationshipSchema> = [
      generateRelationshipSchema({ name: "test", cardinality: "many" }),
    ];

    // WHEN
    const result = addRelationshipsToRequest(relationships);

    // THEN
    expect(result).toEqual({
      test: {
        edges: {
          node: {
            id: true,
            hfid: true,
            display_label: true,
          },
        },
      },
    });
  });

  it("should add metadata when withMetadata is true", () => {
    // GIVEN
    const relationships: Array<RelationshipSchema> = [
      generateRelationshipSchema({ name: "test", cardinality: "one" }),
    ];

    // WHEN
    const result = addRelationshipsToRequest(relationships, { withMetadata: true });

    // THEN
    expect(result).toEqual({
      test: {
        node: {
          id: true,
          hfid: true,
          display_label: true,
        },
        properties: {
          is_protected: true,
          updated_at: true,
          source: {
            id: true,
            hfid: true,
            display_label: true,
            __typename: true,
          },
          owner: {
            id: true,
            hfid: true,
            display_label: true,
            __typename: true,
          },
        },
      },
    });
  });

  it("should handle multiple relationships", () => {
    // GIVEN
    const relationships: Array<RelationshipSchema> = [
      generateRelationshipSchema({ name: "one", cardinality: "one" }),
      generateRelationshipSchema({ name: "many", cardinality: "many" }),
    ];

    // WHEN
    const result = addRelationshipsToRequest(relationships);

    // THEN
    expect(result).toEqual({
      one: {
        node: {
          id: true,
          hfid: true,
          display_label: true,
        },
      },
      many: {
        edges: {
          node: {
            id: true,
            hfid: true,
            display_label: true,
          },
        },
      },
    });
  });
});

describe("addFiltersToRequest", () => {
  it("should add partial_match flag and value for text-based value filters", () => {
    // GIVEN
    const filters: Filter[] = [{ name: "name__value", value: "test" }];

    // WHEN
    const result = addFiltersToRequest(filters);

    // THEN
    expect(result).toEqual({
      partial_match: true,
      name__value: "test",
    });
  });

  it("should add partial_match flag and array value for text-based values filters", () => {
    // GIVEN
    const filters: Filter[] = [{ name: "tags__values", value: ["tag1", "tag2"] }];

    // WHEN
    const result = addFiltersToRequest(filters);

    // THEN
    expect(result).toEqual({
      partial_match: true,
      tags__values: ["tag1", "tag2"],
    });
  });

  it("should include isnull filter value without partial_match flag", () => {
    // GIVEN
    const filters: Filter[] = [{ name: "field__isnull", value: true }];

    // WHEN
    const result = addFiltersToRequest(filters);

    // THEN
    expect(result).toEqual({
      field__isnull: true,
    });
  });

  it("should extract IDs from array of objects for ids filters", () => {
    // GIVEN
    const filters: Filter[] = [{ name: "related__ids", value: [{ id: "1" }, { id: "2" }] }];

    // WHEN
    const result = addFiltersToRequest(filters);

    // THEN
    expect(result).toEqual({
      related__ids: ["1", "2"],
    });
  });

  it("should correctly combine multiple filters of different types", () => {
    // GIVEN
    const filters: Filter[] = [
      { name: "name__value", value: "test" },
      { name: "field__isnull", value: true },
      { name: "related__ids", value: [{ id: "1" }] },
    ];

    // WHEN
    const result = addFiltersToRequest(filters);

    // THEN
    expect(result).toEqual({
      partial_match: true,
      name__value: "test",
      field__isnull: true,
      related__ids: ["1"],
    });
  });

  it("should return empty object for filters with invalid field name format", () => {
    // GIVEN
    const filters: Filter[] = [
      { name: "invalid", value: "test" } as any,
      { name: "also__invalid", value: "test" },
    ];

    // WHEN
    const result = addFiltersToRequest(filters);

    // THEN
    expect(result).toEqual({});
  });
});
