import { describe, expect, it } from "vitest";

import { ACCOUNT_ROLE_OBJECT, OBJECT_PERMISSION_OBJECT } from "@/shared/config/constants";

import { getFilterDefinitionName } from "@/entities/nodes/object/domain/filter-definition";

import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../tests/fake/schema";
import { getFilterDefinitions } from "./get-filter-definitions";

describe("getFilterDefinitions", () => {
  it("appends metadata filters after table-specific fields", () => {
    // GIVEN
    const schema = generateNodeSchema({
      kind: OBJECT_PERMISSION_OBJECT,
      attributes: [
        generateAttributeSchema({ name: "name" }),
        generateAttributeSchema({ name: "action" }),
        generateAttributeSchema({ name: "decision", kind: "Dropdown" }),
        generateAttributeSchema({ name: "description" }),
      ],
      relationships: [
        generateRelationshipSchema({ name: "roles" }),
        generateRelationshipSchema({ name: "groups" }),
      ],
    });

    // WHEN
    const result = getFilterDefinitions(schema).map((definition) =>
      getFilterDefinitionName(definition)
    );

    // THEN
    expect(result).toEqual([
      "action",
      "decision",
      "roles",
      "node_metadata__created_at",
      "node_metadata__updated_at",
      "node_metadata__created_by",
      "node_metadata__updated_by",
    ]);
  });

  it("excludes schema fields not visible in the object table for default schemas", () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({ name: "hidden_extra", display: "extra" }),
        generateAttributeSchema({ name: "notes", kind: "TextArea" }),
        generateAttributeSchema({ name: "name", kind: "Text" }),
      ],
      relationships: [
        generateRelationshipSchema({
          name: "hidden_relationship",
          kind: "Attribute",
          cardinality: "one",
          display: "extra",
        }),
        generateRelationshipSchema({
          name: "address_from_resource_pool",
          kind: "Generic",
          cardinality: "one",
        }),
        generateRelationshipSchema({
          name: "children",
          kind: "Hierarchy",
          cardinality: "many",
        }),
        generateRelationshipSchema({
          name: "parent",
          kind: "Parent",
          cardinality: "one",
        }),
      ],
    });

    // WHEN
    const result = getFilterDefinitions(schema).map((definition) =>
      getFilterDefinitionName(definition)
    );

    // THEN
    expect(result).toEqual([
      "name",
      "parent",
      "node_metadata__created_at",
      "node_metadata__updated_at",
      "node_metadata__created_by",
      "node_metadata__updated_by",
    ]);
  });

  it("uses the role table columns for account role schemas", () => {
    // GIVEN
    const schema = generateNodeSchema({
      kind: ACCOUNT_ROLE_OBJECT,
      attributes: [
        generateAttributeSchema({ name: "name", kind: "Text" }),
        generateAttributeSchema({ name: "description", kind: "Text" }),
        generateAttributeSchema({ name: "label", kind: "Text" }),
      ],
      relationships: [
        generateRelationshipSchema({
          name: "groups",
          kind: "Attribute",
          cardinality: "many",
        }),
        generateRelationshipSchema({
          name: "permissions",
          kind: "Attribute",
          cardinality: "many",
        }),
        generateRelationshipSchema({
          name: "members",
          kind: "Attribute",
          cardinality: "many",
        }),
      ],
    });

    // WHEN
    const result = getFilterDefinitions(schema).map((definition) =>
      getFilterDefinitionName(definition)
    );

    // THEN
    expect(result).toEqual([
      "name",
      "description",
      "groups",
      "permissions",
      "node_metadata__created_at",
      "node_metadata__updated_at",
      "node_metadata__created_by",
      "node_metadata__updated_by",
    ]);
  });
});
