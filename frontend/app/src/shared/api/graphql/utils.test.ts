import { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";
import { describe, expect, it } from "vitest";
import { generateAttributeSchema, generateRelationshipSchema } from "../../../../tests/fake/schema";
import { addAttributesToRequest, addRelationshipsToRequest } from "./utils";

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
        is_visible: true,
        source: {
          id: true,
          display_label: true,
          __typename: true,
        },
        owner: {
          id: true,
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
        is_visible: true,
        source: {
          id: true,
          display_label: true,
          __typename: true,
        },
        owner: {
          id: true,
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
          display_label: true,
        },
        properties: {
          is_visible: true,
          is_protected: true,
          updated_at: true,
          source: {
            id: true,
            display_label: true,
            __typename: true,
          },
          owner: {
            id: true,
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
          display_label: true,
        },
      },
      many: {
        edges: {
          node: {
            id: true,
            display_label: true,
          },
        },
      },
    });
  });
});
