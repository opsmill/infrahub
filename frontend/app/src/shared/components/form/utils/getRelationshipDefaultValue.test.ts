import { describe, expect, it, vi } from "vitest";

import { getRelationshipDefaultValue } from "@/shared/components/form/utils/getRelationshipDefaultValue";
import { store } from "@/shared/stores";

import type {
  RelationshipManyType,
  RelationshipOneType,
} from "@/entities/nodes/getObjectItemDisplayValue";
import type { NodeObject } from "@/entities/nodes/types";
import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/constants";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import type { NodeSchema } from "@/entities/schema/types";

import { generateNodeSchema, generateRelationshipSchema } from "../../../../../tests/fake/schema";

const buildRelationshipOneData = (override: Partial<RelationshipOneType>): RelationshipOneType => ({
  node: {
    id: "relationship-one-id",
    display_label: "Relationship One",
    __typename: "RelationshipOne",
  },
  properties: {
    updated_at: "2024-07-17T17:59:05.309135+00:00",
    is_protected: null,
    is_visible: true,
    source: null,
    owner: null,
    __typename: "RelationshipProperty",
  },
  ...override,
});

vi.mock("@/entities/schema/domain/get-schema", () => ({
  getSchema: vi.fn(() => ({
    schema: generateNodeSchema(),
    isGeneric: false,
    isNode: true,
    isProfile: false,
  })),
}));

describe("getRelationshipDefaultValue", () => {
  describe("when cardinality one", () => {
    it("returns null if there is no relationship", () => {
      // GIVEN
      const relationshipData = undefined;
      const objectTemplate = null;

      // WHEN
      const defaultValue = getRelationshipDefaultValue({ relationshipData, objectTemplate });

      // THEN
      expect(defaultValue).to.deep.equal({ source: null, value: null });
    });

    it("returns user defined relationship", () => {
      // GIVEN
      const relationshipData = buildRelationshipOneData({ properties: { source: null } });
      const objectTemplate = null;

      // WHEN
      const defaultValue = getRelationshipDefaultValue({ relationshipData, objectTemplate });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: { type: "user" },
        value: {
          id: "relationship-one-id",
          display_label: "Relationship One",
          __typename: "RelationshipOne",
        },
      });
    });

    it("returns relationship from pool", () => {
      // GIVEN
      store.set(nodeSchemasAtom, [
        { kind: "FakeResourcePool", inherit_from: [RESOURCE_GENERIC_KIND] } as NodeSchema,
      ]);

      const relationshipData = buildRelationshipOneData({
        properties: {
          source: {
            id: "pool-random-id",
            display_label: "test name pool",
            __typename: "FakeResourcePool",
          },
        },
      });
      const objectTemplate = null;

      // WHEN
      const defaultValue = getRelationshipDefaultValue({ relationshipData, objectTemplate });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          type: "pool",
          label: "test name pool",
          id: "pool-random-id",
          kind: "FakeResourcePool",
        },
        value: {
          id: "relationship-one-id",
          display_label: "Relationship One",
          __typename: "RelationshipOne",
        },
      });
    });

    it("returns relationship from template when no relationship data is provided", () => {
      // GIVEN
      const relationshipData = undefined;
      const relationshipName = "testRelationship";
      const objectTemplate: NodeObject = {
        id: "template-id" as any,
        display_label: "Template Object" as any,
        __typename: "TemplateType" as any,
        testRelationship: {
          node: {
            id: "template-rel-id",
            display_label: "Template Relationship",
            __typename: "TemplateRelationship",
          },
        },
      };

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        relationshipData,
        objectTemplate,
        relationshipName,
      });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          type: "template",
          label: "Template Object",
          kind: "TemplateType",
          id: "template-id",
        },
        value: {
          id: "template-rel-id",
          display_label: "Template Relationship",
          __typename: "TemplateRelationship",
        },
      });
    });

    it("returns default form field value when template exists but relationship name is not found", () => {
      // GIVEN
      const relationshipData = undefined;
      const relationshipName = "nonExistentRelationship";
      const objectTemplate: NodeObject = {
        id: "template-id" as any,
        display_label: "Template Object" as any,
        __typename: "TemplateType" as any,
        testRelationship: {
          node: {
            id: "template-rel-id",
            display_label: "Template Relationship",
            __typename: "TemplateRelationship",
          },
        },
      };

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        relationshipData,
        objectTemplate,
        relationshipName,
      });

      // THEN
      expect(defaultValue).to.deep.equal({ source: null, value: null });
    });
  });

  describe("when cardinality many", () => {
    it("returns empty array if there are no relationships", () => {
      // GIVEN
      const relationshipData: RelationshipManyType = { edges: [] };
      const objectTemplate = null;

      // WHEN
      const defaultValue = getRelationshipDefaultValue({ relationshipData, objectTemplate });

      // THEN
      expect(defaultValue).to.deep.equal({ source: { type: "user" }, value: [] });
    });

    it("returns user defined relationship", () => {
      // GIVEN
      const relationshipData: RelationshipManyType = {
        edges: [buildRelationshipOneData({ properties: { source: null } })],
      };
      const objectTemplate = null;

      // WHEN
      const defaultValue = getRelationshipDefaultValue({ relationshipData, objectTemplate });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: { type: "user" },
        value: [
          {
            id: "relationship-one-id",
            display_label: "Relationship One",
            __typename: "RelationshipOne",
          },
        ],
      });
    });

    it("returns relationships from template with cardinality many", () => {
      // GIVEN
      const relationshipData = undefined;
      const relationshipName = "manyRelationship";
      const objectTemplate: NodeObject = {
        id: "template-id" as any,
        display_label: "Template Object" as any,
        __typename: "TemplateType" as any,
        manyRelationship: {
          edges: [
            {
              node: {
                id: "template-rel-id-1",
                display_label: "Template Relationship 1",
                __typename: "TemplateRelationship",
              },
            },
            {
              node: {
                id: "template-rel-id-2",
                display_label: "Template Relationship 2",
                __typename: "TemplateRelationship",
              },
            },
          ],
        },
      };

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        relationshipData,
        objectTemplate,
        relationshipName,
      });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          type: "template",
          label: "Template Object",
          kind: "TemplateType",
          id: "template-id",
        },
        value: [
          {
            id: "template-rel-id-1",
            display_label: "Template Relationship 1",
            __typename: "TemplateRelationship",
          },
          {
            id: "template-rel-id-2",
            display_label: "Template Relationship 2",
            __typename: "TemplateRelationship",
          },
        ],
      });
    });

    it("returns default form field value when template relationship has empty edges", () => {
      // GIVEN
      const relationshipData = undefined;
      const relationshipName = "emptyRelationship";
      const objectTemplate: NodeObject = {
        id: "template-id" as any,
        display_label: "Template Object" as any,
        __typename: "TemplateType" as any,
        emptyRelationship: {
          edges: [],
        },
      };

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        relationshipData,
        objectTemplate,
        relationshipName,
      });

      // THEN
      expect(defaultValue).to.deep.equal({ source: null, value: null });
    });
  });

  describe("filter form", () => {
    it("returns null values when isFilterForm is true", () => {
      // GIVEN
      const relationshipData = buildRelationshipOneData({ properties: { source: null } });
      const objectTemplate = {
        id: "template-id",
        display_label: "Template Object",
        __typename: "TemplateType",
      } as NodeObject;
      const isFilterForm = true;

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        relationshipData,
        objectTemplate,
        isFilterForm,
      });

      // THEN
      expect(defaultValue).to.deep.equal({ source: null, value: null });
    });
  });

  describe("when parent schema is provided", () => {
    it("returns relationship from parent schema", () => {
      // GIVEN
      const relationshipData = undefined;
      const objectTemplate = null;
      const parentSchema = generateNodeSchema({
        kind: "TestParent",
        relationships: [
          {
            ...generateRelationshipSchema(),
            kind: "Component",
            name: "relationship-to-component",
            peer: "TestComponent",
          },
        ],
      });
      const componentSchema = generateNodeSchema({
        kind: "TestComponent",
        relationships: [
          {
            ...generateRelationshipSchema(),
            kind: "Parent",
            name: "relationship-to-parent",
            peer: "TestParent",
          },
        ],
      });
      const parentData: NodeObject = {
        id: "parent-id",
        kind: "TestParent",
        display_label: "Parent Object",
        __typename: "TestParent",
      };

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        relationshipData,
        objectTemplate,
        relationshipName: "relationship-to-parent",
        schema: componentSchema,
        parentSchema,
        parentData,
      });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          type: "user",
        },
        value: parentData,
      });
    });
  });
});
