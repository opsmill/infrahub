import { describe, expect, it } from "vitest";

import { resolveRelationshipData } from "@/entities/nodes/object/utils/resolve-relationship-data";
import type {
  NodeObject,
  NodeRelationshipManyWithMetadata,
  NodeRelationshipOneWithMetadata,
} from "@/entities/nodes/types";
import type { ModelSchema } from "@/entities/schema/types";

const metadata = {
  is_protected: false,
  updated_at: null,
  source: null,
  owner: null,
};

const nonTemplateSchema = { namespace: "Infra" } as ModelSchema;
const templateSchema = { namespace: "Template" } as ModelSchema;

describe("resolveRelationshipData", () => {
  it("should return the relationship data as-is for non-template schemas", () => {
    // GIVEN
    const relationshipData: NodeRelationshipOneWithMetadata = {
      node: { id: "1", hfid: null, display_label: "Device A", __typename: "InfraDevice" },
      properties: metadata,
    };
    const objectData = {
      id: "obj-1",
      __typename: "InfraDevice",
      display_label: "Device A",
      role: relationshipData,
    } as NodeObject;

    // WHEN
    const result = resolveRelationshipData({
      objectSchema: nonTemplateSchema,
      objectData,
      relationshipName: "role",
    });

    // THEN
    expect(result).toBe(relationshipData);
  });

  it("should return the relationship data as-is when the node is present on a template", () => {
    // GIVEN
    const relationshipData: NodeRelationshipOneWithMetadata = {
      node: { id: "1", hfid: null, display_label: "Device A", __typename: "InfraDevice" },
      properties: metadata,
    };
    const objectData = {
      id: "obj-1",
      __typename: "TemplateDevice",
      display_label: "Template A",
      role: relationshipData,
    } as NodeObject;

    // WHEN
    const result = resolveRelationshipData({
      objectSchema: templateSchema,
      objectData,
      relationshipName: "role",
    });

    // THEN
    expect(result).toBe(relationshipData);
  });

  it("should return pool data when template relationship-one has no node and pool data exists", () => {
    // GIVEN
    const relationshipData: NodeRelationshipOneWithMetadata = {
      node: null,
      properties: metadata,
    };
    const poolData: NodeRelationshipOneWithMetadata = {
      node: { id: "pool-1", hfid: null, display_label: "Pool A", __typename: "CoreIPAddressPool" },
      properties: metadata,
    };
    const objectData = {
      id: "obj-1",
      __typename: "TemplateDevice",
      display_label: "Template A",
      role: relationshipData,
      role_from_resource_pool: poolData,
    } as NodeObject;

    // WHEN
    const result = resolveRelationshipData({
      objectSchema: templateSchema,
      objectData,
      relationshipName: "role",
    });

    // THEN
    expect(result).toBe(poolData);
  });

  it("should return original data when template relationship-one has no node but no pool data", () => {
    // GIVEN
    const relationshipData: NodeRelationshipOneWithMetadata = {
      node: null,
      properties: metadata,
    };
    const objectData = {
      id: "obj-1",
      __typename: "TemplateDevice",
      display_label: "Template A",
      role: relationshipData,
    } as NodeObject;

    // WHEN
    const result = resolveRelationshipData({
      objectSchema: templateSchema,
      objectData,
      relationshipName: "role",
    });

    // THEN
    expect(result).toBe(relationshipData);
  });

  it("should return original data for many-relationships even on templates", () => {
    // GIVEN
    const relationshipData: NodeRelationshipManyWithMetadata = {
      edges: [
        {
          node: { id: "1", hfid: null, display_label: "Tag A", __typename: "BuiltinTag" },
          properties: metadata,
        },
      ],
    };
    const objectData = {
      id: "obj-1",
      __typename: "TemplateDevice",
      display_label: "Template A",
      tags: relationshipData,
    } as NodeObject;

    // WHEN
    const result = resolveRelationshipData({
      objectSchema: templateSchema,
      objectData,
      relationshipName: "tags",
    });

    // THEN
    expect(result).toBe(relationshipData);
  });
});
