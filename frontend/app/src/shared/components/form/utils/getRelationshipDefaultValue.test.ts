import * as R from "remeda";
import { describe, expect, it } from "vitest";

import type { ProfileData } from "@/shared/components/form/object-form";
import {
  getRelationshipDefaultValue,
  getRelationshipDefaultValueFromProfiles,
} from "@/shared/components/form/utils/getRelationshipDefaultValue";
import { store } from "@/shared/stores";

import type {
  NodeObject,
  NodeRelationshipManyWithMetadata,
  NodeRelationshipOneWithMetadata,
} from "@/entities/nodes/types";
import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/constants";
import { nodeSchemasAtom, profileSchemasAtom } from "@/entities/schema/stores/schema.atom";
import type { NodeSchema, ProfileSchema } from "@/entities/schema/types";

import { generateNodeSchema, generateRelationshipSchema } from "../../../../../tests/fake/schema";

type DeepPartial<T> = T extends object
  ? {
      [P in keyof T]?: DeepPartial<T[P]>;
    }
  : T;

const buildRelationshipOneData = (
  override?: DeepPartial<NodeRelationshipOneWithMetadata>
): NodeRelationshipOneWithMetadata => {
  const base: NodeRelationshipOneWithMetadata = {
    node: {
      id: "relationship-one-id",
      display_label: "Relationship One",
      __typename: "RelationshipOne",
    },
    properties: {
      updated_at: "2024-07-17T17:59:05.309135+00:00",
      is_protected: false,
      source: null,
      owner: null,
    },
  };

  if (!override) return base;

  return R.mergeDeep(base, override) as NodeRelationshipOneWithMetadata;
};

describe("getRelationshipDefaultValue", () => {
  describe("when cardinality one", () => {
    it("returns null if there is no relationship", () => {
      // GIVEN
      const objectData = null;
      const objectTemplate = null;

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        objectData,
        objectTemplate,
        relationshipName: "testRelationship",
      });

      // THEN
      expect(defaultValue).to.deep.equal({ source: null, value: null });
    });

    it("returns user defined relationship", () => {
      // GIVEN
      const relationshipName = "testRelationship";
      const relationshipData = buildRelationshipOneData();
      const objectTemplate = null;

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        objectData: { [relationshipName]: relationshipData },
        objectTemplate,
        relationshipName,
      });

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

      const relationshipName = "testRelationship";
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
      const defaultValue = getRelationshipDefaultValue({
        objectData: { [relationshipName]: relationshipData },
        objectTemplate,
        relationshipName,
      });

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

    it("returns relationship from profile when editing existing object with profile source", () => {
      // GIVEN
      store.set(profileSchemasAtom, [
        { kind: "ProfileTestDevice", namespace: "Profile" } as ProfileSchema,
      ]);

      const relationshipName = "testRelationship";
      // When relationship data comes from a profile source, we skip it and let profiles provide the value
      const relationshipData = buildRelationshipOneData({
        properties: {
          source: {
            id: "profile-source-id",
            display_label: "Test Profile Source",
            __typename: "ProfileTestDevice",
          },
        },
      });
      const objectTemplate = null;
      const profiles: ProfileData[] = [
        {
          id: "profile-source-id",
          display_label: "Test Profile Source",
          __typename: "ProfileTestDevice",
          profile_priority: { value: 1000 },
          testRelationship: {
            node: {
              id: "relationship-one-id",
              display_label: "Relationship One",
              __typename: "RelationshipOne",
            },
            properties: {
              is_protected: null,
              owner: null,
              source: null,
              updated_at: null,
            },
          },
        },
      ];

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        objectData: { [relationshipName]: relationshipData },
        objectTemplate,
        profiles,
        relationshipName,
      });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          type: "profile",
          id: "profile-source-id",
          label: "Test Profile Source",
          kind: "ProfileTestDevice",
        },
        value: {
          id: "relationship-one-id",
          display_label: "Relationship One",
          __typename: "RelationshipOne",
        },
      });
    });

    it("returns empty value when profile source was removed from node", () => {
      // GIVEN
      store.set(profileSchemasAtom, [
        { kind: "ProfileTestDevice", namespace: "Profile" } as ProfileSchema,
      ]);

      const relationshipName = "testRelationship";
      // Relationship data has a profile source, but the profile is no longer assigned to the node
      const relationshipData = buildRelationshipOneData({
        properties: {
          source: {
            id: "removed-profile-id",
            display_label: "Removed Profile",
            __typename: "ProfileTestDevice",
          },
        },
      });
      const objectTemplate = null;
      const profiles: ProfileData[] = []; // Profile was removed

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        objectData: { [relationshipName]: relationshipData },
        objectTemplate,
        profiles,
        relationshipName,
      });

      // THEN - should be empty since the profile was removed
      expect(defaultValue).to.deep.equal({ source: null, value: null });
    });

    it("returns relationship from template when no relationship data is provided", () => {
      // GIVEN
      store.set(nodeSchemasAtom, [
        generateNodeSchema({ kind: "TemplateType", display_labels: ["label"] }),
        generateNodeSchema({ kind: "TemplateRelationship", display_labels: ["label"] }),
      ]);

      const relationshipName = "testRelationship";
      const objectTemplate: NodeObject = {
        id: "template-id",
        display_label: "Template Object",
        __typename: "TemplateType",
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

    it("returns pool value from template when template relationship node is null and _from_resource_pool exists", () => {
      // GIVEN
      store.set(nodeSchemasAtom, [
        generateNodeSchema({ kind: "TemplateType", display_labels: ["label"] }),
        generateNodeSchema({
          kind: "CoreIPAddressPool",
          display_labels: ["name__value"],
        }),
      ]);

      const relationshipName = "ip_address";
      const objectTemplate: NodeObject = {
        id: "template-id",
        display_label: "Template Object",
        __typename: "TemplateType",
        ip_address: {
          node: null,
        },
        ip_address_from_resource_pool: {
          node: {
            id: "pool-id",
            display_label: "My IP Pool",
            __typename: "CoreIPAddressPool",
          },
        },
      };

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        objectTemplate,
        relationshipName,
      });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          type: "pool",
          fromTemplate: true,
          label: "My IP Pool",
          id: "pool-id",
          kind: "CoreIPAddressPool",
        },
        value: {
          id: "pool-id",
          display_label: "My IP Pool",
          __typename: "CoreIPAddressPool",
        },
      });
    });

    it("returns null from template when template relationship node is null and _from_resource_pool node is also null", () => {
      // GIVEN
      store.set(nodeSchemasAtom, [
        generateNodeSchema({ kind: "TemplateType", display_labels: ["label"] }),
      ]);

      const relationshipName = "ip_address";
      const objectTemplate: NodeObject = {
        id: "template-id",
        display_label: "Template Object",
        __typename: "TemplateType",
        ip_address: {
          node: null,
        },
        ip_address_from_resource_pool: {
          node: null,
        },
      };

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        objectTemplate,
        relationshipName,
      });

      // THEN
      expect(defaultValue).to.deep.equal({ source: null, value: null });
    });

    it("returns default form field value when template exists but relationship name is not found", () => {
      // GIVEN
      const relationshipName = "nonExistentRelationship";
      const objectTemplate: NodeObject = {
        id: "template-id",
        display_label: "Template Object",
        __typename: "TemplateType",
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
        objectTemplate,
        relationshipName,
      });

      // THEN
      expect(defaultValue).to.deep.equal({ source: null, value: null });
    });

    it("returns pool value from _from_resource_pool relationship when main node is null", () => {
      // GIVEN
      store.set(nodeSchemasAtom, [
        generateNodeSchema({
          kind: "CoreIPAddressPool",
          display_labels: ["name__value"],
        }),
      ]);

      const relationshipName = "ip_address";
      const objectData = {
        ip_address: {
          node: null,
          properties: {
            is_protected: null,
            owner: null,
            source: null,
            updated_at: null,
          },
        } as NodeRelationshipOneWithMetadata,
        ip_address_from_resource_pool: {
          node: {
            id: "pool-id",
            display_label: "My IP Pool",
            __typename: "CoreIPAddressPool",
            name: { value: "My IP Pool" },
          },
          properties: {
            is_protected: null,
            owner: null,
            source: null,
            updated_at: null,
          },
        } as NodeRelationshipOneWithMetadata,
      };

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        objectData,
        objectTemplate: null,
        relationshipName,
      });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          type: "pool",
          label: "My IP Pool",
          id: "pool-id",
          kind: "CoreIPAddressPool",
        },
        value: {
          id: "pool-id",
          display_label: "My IP Pool",
          __typename: "CoreIPAddressPool",
          name: { value: "My IP Pool" },
        },
      });
    });

    it("returns null when main node is null and _from_resource_pool node is also null", () => {
      // GIVEN
      const relationshipName = "ip_address";
      const objectData = {
        ip_address: {
          node: null,
          properties: {
            is_protected: null,
            owner: null,
            source: null,
            updated_at: null,
          },
        } as NodeRelationshipOneWithMetadata,
        ip_address_from_resource_pool: {
          node: null,
          properties: {
            is_protected: null,
            owner: null,
            source: null,
            updated_at: null,
          },
        } as NodeRelationshipOneWithMetadata,
      };

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        objectData,
        objectTemplate: null,
        relationshipName,
      });

      // THEN
      expect(defaultValue).to.deep.equal({ source: null, value: null });
    });

    it("does not consult _from_resource_pool when main relationship has a node", () => {
      // GIVEN
      const relationshipName = "ip_address";
      const objectData = {
        ip_address: buildRelationshipOneData(),
        ip_address_from_resource_pool: {
          node: {
            id: "pool-id",
            display_label: "My IP Pool",
            __typename: "CoreIPAddressPool",
          },
          properties: {
            is_protected: null,
            owner: null,
            source: null,
            updated_at: null,
          },
        } as NodeRelationshipOneWithMetadata,
      };

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        objectData,
        objectTemplate: null,
        relationshipName,
      });

      // THEN - returns user value from main relationship, not pool
      expect(defaultValue).to.deep.equal({
        source: { type: "user" },
        value: {
          id: "relationship-one-id",
          display_label: "Relationship One",
          __typename: "RelationshipOne",
        },
      });
    });

    it("returns profile value when relationship node is null and profile is provided", () => {
      // GIVEN
      const relationshipName = "my_relationship";
      const relationshipData: NodeRelationshipOneWithMetadata = {
        node: null,
        properties: {
          is_protected: null,
          owner: null,
          source: null,
          updated_at: null,
        },
      };
      const objectTemplate = null;
      const profiles: Array<ProfileData> = [
        {
          id: "profile-1",
          display_label: "Test Profile",
          __typename: "TestProfile",
          profile_priority: { value: 1 },
          my_relationship: {
            node: {
              id: "profile-rel-1",
              display_label: "Profile Relationship",
              __typename: "RelatedNode",
            },
          },
        },
      ];

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        objectData: { [relationshipName]: relationshipData },
        objectTemplate,
        profiles,
        relationshipName,
      });

      // THEN - profile provides the relationship value
      expect(defaultValue).to.deep.equal({
        source: {
          type: "profile",
          id: "profile-1",
          label: "Test Profile",
          kind: "TestProfile",
        },
        value: {
          id: "profile-rel-1",
          display_label: "Profile Relationship",
          __typename: "RelatedNode",
        },
      });
    });
  });

  describe("when cardinality many", () => {
    it("returns default value if relationships are empty (allowing profile fallback)", () => {
      // GIVEN
      const relationshipName = "testRelationship";
      const relationshipData: NodeRelationshipManyWithMetadata = { edges: [] };
      const objectTemplate = null;

      // WHEN - no profiles provided, so falls back to default
      const defaultValue = getRelationshipDefaultValue({
        objectData: { [relationshipName]: relationshipData },
        objectTemplate,
        relationshipName,
      });

      // THEN - empty data should not block profile fallback
      expect(defaultValue).to.deep.equal({ source: null, value: null });
    });

    it("returns profile value when relationships are empty and profile is provided", () => {
      // GIVEN
      const relationshipName = "my_relationship";
      const relationshipData: NodeRelationshipManyWithMetadata = { edges: [] };
      const objectTemplate = null;
      const profiles: Array<ProfileData> = [
        {
          id: "profile-1",
          display_label: "Test Profile",
          __typename: "TestProfile",
          profile_priority: { value: 1 },
          my_relationship: {
            edges: [
              {
                node: {
                  id: "profile-rel-1",
                  display_label: "Profile Relationship",
                  __typename: "RelatedNode",
                },
              },
            ],
          },
        },
      ];

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        objectData: { [relationshipName]: relationshipData },
        objectTemplate,
        profiles,
        relationshipName,
      });

      // THEN - profile provides the relationship value
      expect(defaultValue).to.deep.equal({
        source: {
          type: "profile",
          id: "profile-1",
          label: "Test Profile",
          kind: "TestProfile",
        },
        value: [
          {
            id: "profile-rel-1",
            display_label: "Profile Relationship",
            __typename: "RelatedNode",
          },
        ],
      });
    });

    it("returns user defined relationship", () => {
      // GIVEN
      const relationshipName = "testRelationship";
      const relationshipData: NodeRelationshipManyWithMetadata = {
        edges: [buildRelationshipOneData({ properties: { source: null } })],
      };
      const objectTemplate = null;

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        objectData: { [relationshipName]: relationshipData },
        objectTemplate,
        relationshipName,
      });

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

    it("returns relationship from profile when editing existing object with cardinality many and profile source", () => {
      // GIVEN
      store.set(profileSchemasAtom, [
        { kind: "ProfileTestDevice", namespace: "Profile" } as ProfileSchema,
      ]);

      const relationshipName = "manyRelationship";
      // When relationship data comes from a profile source, we skip it and let profiles provide the value
      const relationshipData: NodeRelationshipManyWithMetadata = {
        edges: [
          buildRelationshipOneData({
            properties: {
              source: {
                id: "profile-source-id",
                display_label: "Test Profile Source",
                __typename: "ProfileTestDevice",
              },
            },
          }),
          buildRelationshipOneData({
            node: {
              id: "relationship-two-id",
              display_label: "Relationship Two",
              __typename: "RelationshipTwo",
            },
            properties: {
              source: {
                id: "profile-source-id",
                display_label: "Test Profile Source",
                __typename: "ProfileTestDevice",
              },
            },
          }),
        ],
      };
      const objectTemplate = null;
      const profiles: Array<ProfileData> = [
        {
          id: "profile-source-id",
          display_label: "Test Profile Source",
          __typename: "ProfileTestDevice",
          profile_priority: { value: 1000 },
          manyRelationship: {
            edges: [
              {
                node: {
                  id: "relationship-one-id",
                  display_label: "Relationship One",
                  __typename: "RelationshipOne",
                },
              },
              {
                node: {
                  id: "relationship-two-id",
                  display_label: "Relationship Two",
                  __typename: "RelationshipTwo",
                },
              },
            ],
          },
        },
      ];

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        objectData: { [relationshipName]: relationshipData },
        objectTemplate,
        profiles,
        relationshipName,
      });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          type: "profile",
          id: "profile-source-id",
          label: "Test Profile Source",
          kind: "ProfileTestDevice",
        },
        value: [
          {
            id: "relationship-one-id",
            display_label: "Relationship One",
            __typename: "RelationshipOne",
          },
          {
            id: "relationship-two-id",
            display_label: "Relationship Two",
            __typename: "RelationshipTwo",
          },
        ],
      });
    });

    it("returns empty value when profile source was removed from node with cardinality many", () => {
      // GIVEN
      store.set(profileSchemasAtom, [
        { kind: "ProfileTestDevice", namespace: "Profile" } as ProfileSchema,
      ]);

      const relationshipName = "manyRelationship";
      // Relationship data has a profile source, but the profile is no longer assigned to the node
      const relationshipData: NodeRelationshipManyWithMetadata = {
        edges: [
          buildRelationshipOneData({
            properties: {
              source: {
                id: "removed-profile-id",
                display_label: "Removed Profile",
                __typename: "ProfileTestDevice",
              },
            },
          }),
          buildRelationshipOneData({
            node: {
              id: "relationship-two-id",
              display_label: "Relationship Two",
              __typename: "RelationshipTwo",
            },
            properties: {
              source: {
                id: "removed-profile-id",
                display_label: "Removed Profile",
                __typename: "ProfileTestDevice",
              },
            },
          }),
        ],
      };
      const objectTemplate = null;
      const profiles: ProfileData[] = []; // Profile was removed

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        objectData: { [relationshipName]: relationshipData },
        objectTemplate,
        profiles,
        relationshipName,
      });

      // THEN - should be empty since the profile was removed
      expect(defaultValue).to.deep.equal({ source: null, value: null });
    });

    it("returns relationships from template with cardinality many", () => {
      // GIVEN
      store.set(nodeSchemasAtom, [
        generateNodeSchema({ kind: "TemplateType", display_labels: ["label"] }),
        generateNodeSchema({ kind: "TemplateRelationship", display_labels: ["label"] }),
      ]);

      const relationshipName = "manyRelationship";
      const objectTemplate: NodeObject = {
        id: "template-id",
        display_label: "Template Object",
        __typename: "TemplateType",
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
      const relationshipName = "emptyRelationship";
      const objectTemplate: NodeObject = {
        id: "template-id",
        display_label: "Template Object",
        __typename: "TemplateType",
        emptyRelationship: {
          edges: [],
        },
      };

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
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
      const relationshipName = "testRelationship";
      const relationshipData = buildRelationshipOneData({ properties: { source: null } });
      const objectTemplate = {
        id: "template-id",
        display_label: "Template Object",
        __typename: "TemplateType",
      } as NodeObject;
      const isFilterForm = true;

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        objectData: { [relationshipName]: relationshipData },
        objectTemplate,
        isFilterForm,
        relationshipName,
      });

      // THEN
      expect(defaultValue).to.deep.equal({ source: null, value: null });
    });
  });

  describe("when parent schema is provided", () => {
    it("returns relationship from parent schema", () => {
      // GIVEN
      const objectTemplate = null;
      const parentSchema = generateNodeSchema({
        kind: "TestParent",
        display_labels: ["name__value"],
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
        display_label: "Parent Object",
        __typename: "TestParent",
      };

      // Register the parent schema so getNodeLabel can resolve the display_label
      store.set(nodeSchemasAtom, [parentSchema]);

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
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
        value: {
          id: parentData.id,
          display_label: parentData.display_label,
          __typename: parentData.__typename,
        },
      });
    });
  });

  describe("when profiles are provided", () => {
    const buildProfileData = (override: Partial<ProfileData> = {}): ProfileData => ({
      id: "profile-id",
      display_label: "Test Profile",
      __typename: "ProfileTestDevice",
      profile_priority: { value: 1000 },
      ...override,
    });

    it("returns relationship from profile when no other data is provided", () => {
      // GIVEN
      const relationshipName = "testRelationship";
      const objectTemplate = null;
      const profiles = [
        buildProfileData({
          testRelationship: {
            node: {
              id: "profile-rel-id",
              display_label: "Profile Relationship",
              __typename: "ProfileRelationshipType",
            },
          },
        }),
      ];

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        objectTemplate,
        profiles,
        relationshipName,
      });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          type: "profile",
          id: "profile-id",
          label: "Test Profile",
          kind: "ProfileTestDevice",
        },
        value: {
          id: "profile-rel-id",
          display_label: "Profile Relationship",
          __typename: "ProfileRelationshipType",
        },
      });
    });

    it("returns null when profile relationship has null node", () => {
      // GIVEN
      const relationshipName = "testRelationship";
      const objectTemplate = null;
      const profiles = [
        buildProfileData({
          testRelationship: {
            node: null,
          },
        }),
      ];

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        objectTemplate,
        profiles,
        relationshipName,
      });

      // THEN
      expect(defaultValue).to.deep.equal({ source: null, value: null });
    });

    it("returns null when profile does not have the relationship", () => {
      // GIVEN
      const relationshipName = "nonExistentRelationship";
      const objectTemplate = null;
      const profiles = [buildProfileData({})];

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        objectTemplate,
        profiles,
        relationshipName,
      });

      // THEN
      expect(defaultValue).to.deep.equal({ source: null, value: null });
    });

    it("prioritizes template over profile", () => {
      // GIVEN
      store.set(nodeSchemasAtom, [
        generateNodeSchema({ kind: "TemplateType", display_labels: ["label"] }),
        generateNodeSchema({ kind: "TemplateRelationship", display_labels: ["label"] }),
      ]);

      const relationshipName = "testRelationship";
      const objectTemplate: NodeObject = {
        id: "template-id",
        display_label: "Template Object",
        __typename: "TemplateType",
        testRelationship: {
          node: {
            id: "template-rel-id",
            display_label: "Template Relationship",
            __typename: "TemplateRelationship",
          },
        },
      };
      const profiles = [
        buildProfileData({
          testRelationship: {
            node: {
              id: "profile-rel-id",
              display_label: "Profile Relationship",
              __typename: "ProfileRelationshipType",
            },
          },
        }),
      ];

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        objectTemplate,
        profiles,
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

    it("selects relationship from profile with highest priority", () => {
      // GIVEN
      const relationshipName = "testRelationship";
      const objectTemplate = null;
      const profiles = [
        buildProfileData({
          id: "low-priority-profile",
          display_label: "Low Priority Profile",
          profile_priority: { value: 2000 },
          testRelationship: {
            node: {
              id: "low-priority-rel-id",
              display_label: "Low Priority Relationship",
              __typename: "LowPriorityType",
            },
          },
        }),
        buildProfileData({
          id: "high-priority-profile",
          display_label: "High Priority Profile",
          profile_priority: { value: 1000 },
          testRelationship: {
            node: {
              id: "high-priority-rel-id",
              display_label: "High Priority Relationship",
              __typename: "HighPriorityType",
            },
          },
        }),
      ];

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        objectTemplate,
        profiles,
        relationshipName,
      });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          type: "profile",
          id: "high-priority-profile",
          label: "High Priority Profile",
          kind: "ProfileTestDevice",
        },
        value: {
          id: "high-priority-rel-id",
          display_label: "High Priority Relationship",
          __typename: "HighPriorityType",
        },
      });
    });

    it("returns cardinality many relationships from profile", () => {
      // GIVEN
      const relationshipName = "manyRelationship";
      const objectTemplate = null;
      const profiles: Array<ProfileData> = [
        {
          id: "profile-id",
          display_label: "Test Profile",
          __typename: "ProfileTestDevice",
          profile_priority: { value: 1000 },
          manyRelationship: {
            edges: [
              {
                node: {
                  id: "profile-rel-id-1",
                  display_label: "Profile Relationship 1",
                  __typename: "ProfileRelationshipType",
                },
              },
              {
                node: {
                  id: "profile-rel-id-2",
                  display_label: "Profile Relationship 2",
                  __typename: "ProfileRelationshipType",
                },
              },
            ],
          },
        },
      ];

      // WHEN
      const defaultValue = getRelationshipDefaultValue({
        objectTemplate,
        profiles,
        relationshipName,
      });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          type: "profile",
          id: "profile-id",
          label: "Test Profile",
          kind: "ProfileTestDevice",
        },
        value: [
          {
            id: "profile-rel-id-1",
            display_label: "Profile Relationship 1",
            __typename: "ProfileRelationshipType",
          },
          {
            id: "profile-rel-id-2",
            display_label: "Profile Relationship 2",
            __typename: "ProfileRelationshipType",
          },
        ],
      });
    });
  });
});

describe("getRelationshipDefaultValueFromProfiles", () => {
  const buildProfileData = (override: Partial<ProfileData> = {}): ProfileData => ({
    id: "profile-id",
    display_label: "Test Profile",
    __typename: "ProfileTestDevice",
    profile_priority: { value: 1000 },
    ...override,
  });

  it("returns null when relationshipName is undefined", () => {
    // GIVEN
    const profiles = [buildProfileData({})];

    // WHEN
    const result = getRelationshipDefaultValueFromProfiles(undefined, profiles);

    // THEN
    expect(result).toBeNull();
  });

  it("returns null when profiles array is empty", () => {
    // GIVEN
    const profiles: ProfileData[] = [];

    // WHEN
    const result = getRelationshipDefaultValueFromProfiles("testRelationship", profiles);

    // THEN
    expect(result).toBeNull();
  });

  it("returns relationship from profile", () => {
    // GIVEN
    const profiles = [
      buildProfileData({
        testRelationship: {
          node: {
            id: "profile-rel-id",
            display_label: "Profile Relationship",
            __typename: "ProfileRelationshipType",
          },
        },
      }),
    ];

    // WHEN
    const result = getRelationshipDefaultValueFromProfiles("testRelationship", profiles);

    // THEN
    expect(result).to.deep.equal({
      source: {
        type: "profile",
        id: "profile-id",
        label: "Test Profile",
        kind: "ProfileTestDevice",
      },
      value: {
        id: "profile-rel-id",
        display_label: "Profile Relationship",
        __typename: "ProfileRelationshipType",
      },
    });
  });

  describe("cardinality many", () => {
    it("returns relationships from profile with cardinality many", () => {
      // GIVEN
      const profiles = [
        buildProfileData({
          testRelationship: {
            edges: [
              {
                node: {
                  id: "profile-rel-id-1",
                  display_label: "Profile Relationship 1",
                  __typename: "ProfileRelationshipType",
                },
              },
              {
                node: {
                  id: "profile-rel-id-2",
                  display_label: "Profile Relationship 2",
                  __typename: "ProfileRelationshipType",
                },
              },
            ],
          },
        }),
      ];

      // WHEN
      const result = getRelationshipDefaultValueFromProfiles("testRelationship", profiles);

      // THEN
      expect(result).to.deep.equal({
        source: {
          type: "profile",
          id: "profile-id",
          label: "Test Profile",
          kind: "ProfileTestDevice",
        },
        value: [
          {
            id: "profile-rel-id-1",
            display_label: "Profile Relationship 1",
            __typename: "ProfileRelationshipType",
          },
          {
            id: "profile-rel-id-2",
            display_label: "Profile Relationship 2",
            __typename: "ProfileRelationshipType",
          },
        ],
      });
    });

    it("returns null when profile has empty edges array", () => {
      // GIVEN
      const profiles = [
        buildProfileData({
          testRelationship: {
            edges: [],
          },
        }),
      ];

      // WHEN
      const result = getRelationshipDefaultValueFromProfiles("testRelationship", profiles);

      // THEN
      expect(result).toBeNull();
    });

    it("filters out null nodes from edges", () => {
      // GIVEN
      const profiles = [
        buildProfileData({
          testRelationship: {
            edges: [
              {
                node: {
                  id: "profile-rel-id-1",
                  display_label: "Profile Relationship 1",
                  __typename: "ProfileRelationshipType",
                },
              },
              { node: null },
              {
                node: {
                  id: "profile-rel-id-2",
                  display_label: "Profile Relationship 2",
                  __typename: "ProfileRelationshipType",
                },
              },
            ],
          },
        }),
      ];

      // WHEN
      const result = getRelationshipDefaultValueFromProfiles("testRelationship", profiles);

      // THEN
      expect(result).to.deep.equal({
        source: {
          type: "profile",
          id: "profile-id",
          label: "Test Profile",
          kind: "ProfileTestDevice",
        },
        value: [
          {
            id: "profile-rel-id-1",
            display_label: "Profile Relationship 1",
            __typename: "ProfileRelationshipType",
          },
          {
            id: "profile-rel-id-2",
            display_label: "Profile Relationship 2",
            __typename: "ProfileRelationshipType",
          },
        ],
      });
    });

    it("selects relationship from profile with highest priority for cardinality many", () => {
      // GIVEN
      const profiles = [
        buildProfileData({
          id: "low-priority-profile",
          display_label: "Low Priority Profile",
          profile_priority: { value: 2000 },
          testRelationship: {
            edges: [
              {
                node: {
                  id: "low-priority-rel-id",
                  display_label: "Low Priority Relationship",
                  __typename: "LowPriorityType",
                },
              },
            ],
          },
        }),
        buildProfileData({
          id: "high-priority-profile",
          display_label: "High Priority Profile",
          profile_priority: { value: 1000 },
          testRelationship: {
            edges: [
              {
                node: {
                  id: "high-priority-rel-id",
                  display_label: "High Priority Relationship",
                  __typename: "HighPriorityType",
                },
              },
            ],
          },
        }),
      ];

      // WHEN
      const result = getRelationshipDefaultValueFromProfiles("testRelationship", profiles);

      // THEN
      expect(result).to.deep.equal({
        source: {
          type: "profile",
          id: "high-priority-profile",
          label: "High Priority Profile",
          kind: "ProfileTestDevice",
        },
        value: [
          {
            id: "high-priority-rel-id",
            display_label: "High Priority Relationship",
            __typename: "HighPriorityType",
          },
        ],
      });
    });
  });
});
