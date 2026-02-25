import { beforeEach, describe, expect, it } from "vitest";

import type { ProfileData } from "@/shared/components/form/object-form";
import {
  type GetFieldDefaultValue,
  getFieldDefaultValue,
} from "@/shared/components/form/utils/getFieldDefaultValue";
import { store } from "@/shared/stores";

import type { AttributeType } from "@/entities/nodes/getObjectItemDisplayValue";
import type { NodeObject, NodeObjectWithMetadata } from "@/entities/nodes/types";
import {
  genericSchemasAtom,
  nodeSchemasAtom,
  profileSchemasAtom,
  templateSchemasAtom,
} from "@/entities/schema/stores/schema.atom";

import {
  generateAttributeSchema,
  generateGenericSchema,
  generateNodeSchema,
  generateProfileSchema,
  generateRelationshipSchema,
  generateTemplateSchema,
} from "../../../../../tests/fake/schema";

describe("getFieldDefaultValue", () => {
  beforeEach(() => {
    // Initialize schema store with necessary schemas for type checking
    const nodeSchema = generateNodeSchema({ kind: "Node" });
    const genericSchema = generateGenericSchema({ kind: "Generic" });
    const profileSchema = generateProfileSchema({ kind: "Profile" });
    const templateSchema = generateTemplateSchema({ kind: "Template" });
    const fakeProfileSchema = generateProfileSchema({ kind: "FakeProfileKind" });
    const poolSchema = generateGenericSchema({ kind: "FakePool" });
    const fakeTemplateSchema = generateTemplateSchema({ kind: "FakeTemplateKind" });

    store.set(nodeSchemasAtom, [nodeSchema]);
    store.set(genericSchemasAtom, [genericSchema, poolSchema]);
    store.set(profileSchemasAtom, [profileSchema, fakeProfileSchema]);
    store.set(templateSchemasAtom, [templateSchema, fakeTemplateSchema]);
  });

  describe("when source is the user", () => {
    it("returns current object field's value when value is not from profile", () => {
      // GIVEN
      const fieldSchema = generateRelationshipSchema({ name: "field1" });

      const profiles: Array<ProfileData> = [
        {
          id: "profile1",
          display_label: "Profile 1",
          __typename: "FakeProfileKind",
          field1: {
            value: "test-value-form-profile",
          },
        },
      ];

      const initialObject: Record<string, AttributeType> = {
        field1: {
          value: "test-value-from-user",
          is_default: false,
          is_from_profile: false,
        },
      };

      // WHEN
      const defaultValue = getFieldDefaultValue({ fieldSchema, initialObject, profiles });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          type: "user",
        },
        value: "test-value-from-user",
      });
    });

    it("returns current object field's value when value is not from profile and is null", () => {
      // GIVEN
      const fieldSchema = generateAttributeSchema({ name: "field1" });

      const profiles: Array<ProfileData> = [
        {
          id: "profile1",
          display_label: "Profile 1",
          __typename: "FakeProfileKind",
          field1: {
            value: "test-value-form-profile",
          },
        },
      ];

      const initialObject: Record<string, AttributeType> = {
        field1: {
          value: null,
          is_default: false,
          is_from_profile: false,
        },
      };

      // WHEN
      const defaultValue = getFieldDefaultValue({ fieldSchema, initialObject, profiles });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          type: "user",
        },
        value: null,
      });
    });

    it("returns current object field's value when value is not from profile and is 0", () => {
      // GIVEN
      const fieldSchema = generateAttributeSchema({ name: "field1" });

      const profiles: Array<ProfileData> = [
        {
          id: "profile1",
          display_label: "Profile 1",
          __typename: "FakeProfileKind",
          field1: {
            value: "test-value-form-profile",
          },
        },
      ];

      const initialObject: Record<string, AttributeType> = {
        field1: {
          value: 0,
          is_default: false,
          is_from_profile: false,
        },
      };

      // WHEN
      const defaultValue = getFieldDefaultValue({ fieldSchema, initialObject, profiles });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          type: "user",
        },
        value: 0,
      });
    });
  });

  describe("when source is profile", () => {
    it("returns profile's value when it exists, current object value is not found", () => {
      // GIVEN
      const fieldSchema = generateAttributeSchema({ name: "field1" });

      const profiles: Array<ProfileData> = [
        {
          id: "profile1",
          display_label: "Profile 1",
          __typename: "FakeProfileKind",
          field1: {
            value: "test-value-form-profile",
          },
        },
      ];

      const initialObject = {};

      // WHEN
      const defaultValue = getFieldDefaultValue({ fieldSchema, initialObject, profiles });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          label: "Profile 1",
          type: "profile",
          id: "profile1",
          kind: "FakeProfileKind",
        },
        value: "test-value-form-profile",
      });
    });

    it("returns profile's value when it exists, current object field is found and is from profile", () => {
      // GIVEN
      const fieldSchema = generateAttributeSchema({ name: "field1" });

      const profiles: Array<ProfileData> = [
        {
          id: "profile1",
          display_label: "Profile 1",
          __typename: "FakeProfileKind",
          field1: {
            value: "test-value-form-profile",
          },
        },
      ];

      const initialObject: Record<string, AttributeType> = {
        field1: {
          value: "test-value-form-profile",
          is_from_profile: true,
          is_default: false,
        },
      };

      // WHEN
      const defaultValue = getFieldDefaultValue({ fieldSchema, initialObject, profiles });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          label: "Profile 1",
          type: "profile",
          id: "profile1",
          kind: "FakeProfileKind",
        },
        value: "test-value-form-profile",
      });
    });

    it("returns schema's value when profile value is null", () => {
      // GIVEN
      const fieldSchema = generateAttributeSchema({ name: "field1" });

      const profiles: Array<ProfileData> = [
        {
          id: "profile1",
          display_label: "Profile 1",
          __typename: "FakeProfileKind",
          field1: {
            value: null,
          },
        },
      ];

      // WHEN
      const defaultValue = getFieldDefaultValue({ fieldSchema, profiles });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          type: "schema",
        },
        value: null,
      });
    });

    it("returns profile's value when it exists and value is 0", () => {
      // GIVEN
      const fieldSchema = generateAttributeSchema({ name: "field1" });

      const profiles: Array<ProfileData> = [
        {
          id: "profile1",
          display_label: "Profile 1",
          __typename: "FakeProfileKind",
          field1: {
            value: 0,
          },
        },
      ];

      // WHEN
      const defaultValue = getFieldDefaultValue({ fieldSchema, profiles });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          label: "Profile 1",
          type: "profile",
          id: "profile1",
          kind: "FakeProfileKind",
        },
        value: 0,
      });
    });

    it("returns profile's value with the highest priority + order by id ASC", () => {
      // GIVEN
      const fieldSchema: GetFieldDefaultValue["fieldSchema"] = {
        id: "17d67b92-f0b9-cf97-3001-c51824a9c7dc",
        state: "present",
        name: "name",
        kind: "Text",
        enum: null,
        choices: null,
        regex: null,
        max_length: null,
        min_length: null,
        label: "Name",
        description: null,
        read_only: false,
        unique: true,
        optional: false,
        branch: "aware",
        order_weight: 1000,
        default_value: "test-value-form-schema",
        inherited: false,
        allow_override: "any",
      };

      const profiles: Array<ProfileData> = [
        {
          id: "profile3",
          display_label: "Profile 3",
          __typename: "FakeProfileKind",
          name: {
            value: "third",
          },
          profile_priority: {
            value: 1,
          },
        },
        {
          id: "profile1",
          display_label: "Profile 1",
          __typename: "FakeProfileKind",
          name: {
            value: "first",
          },
          profile_priority: {
            value: 2,
          },
        },
        {
          id: "profile2",
          display_label: "Profile 2",
          __typename: "FakeProfileKind",
          name: {
            value: "second",
          },
          profile_priority: {
            value: 1,
          },
        },
      ];

      // WHEN
      const defaultValue = getFieldDefaultValue({ fieldSchema, profiles });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          label: "Profile 2",
          type: "profile",
          id: "profile2",
          kind: "FakeProfileKind",
        },
        value: "second",
      });
    });

    it("returns the 1st profile that contains any not null value", () => {
      // GIVEN
      const fieldSchema: GetFieldDefaultValue["fieldSchema"] = {
        id: "17d67b92-f0b9-cf97-3001-c51824a9c7dc",
        state: "present",
        name: "name",
        kind: "Text",
        enum: null,
        choices: null,
        regex: null,
        max_length: null,
        min_length: null,
        label: "Name",
        description: null,
        read_only: false,
        unique: true,
        optional: false,
        branch: "aware",
        order_weight: 1000,
        default_value: "test-value-form-schema",
        inherited: false,
        allow_override: "any",
      };

      const profiles: Array<ProfileData> = [
        {
          id: "profile1",
          display_label: "Profile 1",
          __typename: "FakeProfileKind",
          name: {
            value: "first",
          },
          profile_priority: {
            value: 2,
          },
        },
        {
          id: "profile2",
          display_label: "Profile 2",
          __typename: "FakeProfileKind",
          name: {
            value: null,
          },
          profile_priority: {
            value: 1,
          },
        },
      ];

      // WHEN
      const defaultValue = getFieldDefaultValue({ fieldSchema, profiles });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          label: "Profile 1",
          type: "profile",
          id: "profile1",
          kind: "FakeProfileKind",
        },
        value: "first",
      });
    });
  });

  describe("when source is schema", () => {
    it("returns schema's default value when it exists, and no profile nor current object field value are provided", () => {
      // GIVEN
      const fieldSchema: GetFieldDefaultValue["fieldSchema"] = {
        id: "17d67b92-f0b9-cf97-3001-c51824a9c7dc",
        state: "present",
        name: "name",
        kind: "Text",
        enum: null,
        choices: null,
        regex: null,
        max_length: null,
        min_length: null,
        label: "Name",
        description: null,
        read_only: false,
        unique: true,
        optional: false,
        branch: "aware",
        order_weight: 1000,
        default_value: "test-value-form-schema",
        inherited: false,
        allow_override: "any",
      };

      // WHEN
      const defaultValue = getFieldDefaultValue({ fieldSchema });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          type: "schema",
        },
        value: "test-value-form-schema",
      });
    });

    it("returns schema's default value when it exists if the value is null", () => {
      // GIVEN
      const fieldSchema = generateAttributeSchema();

      // WHEN
      const defaultValue = getFieldDefaultValue({ fieldSchema });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          type: "schema",
        },
        value: null,
      });
    });

    it("returns schema's default value when current value has is_default: true", () => {
      // GIVEN
      const fieldSchema = generateAttributeSchema({ default_value: "my-default-value" });

      const initialObject: Record<string, AttributeType> = {
        field1: {
          value: "my-default-value",
          is_default: true,
          is_from_profile: false,
        },
      };

      // WHEN
      const defaultValue = getFieldDefaultValue({ fieldSchema, initialObject });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          type: "schema",
        },
        value: "my-default-value",
      });
    });
  });

  it("returns null if field is an relationship and no object field value is provided", () => {
    // GIVEN
    const fieldSchema = generateRelationshipSchema();

    // WHEN
    const defaultValue = getFieldDefaultValue({ fieldSchema });

    // THEN
    expect(defaultValue).to.deep.equal({ source: null, value: null });
  });

  describe("when source is template", () => {
    it("returns template value when provided", () => {
      // GIVEN
      const fieldSchema = generateAttributeSchema({ name: "field1" });
      const objectTemplate: NodeObject = {
        id: "template-id",
        __typename: "FakeTemplate",
        field1: {
          value: "template-value",
        },
      };

      // WHEN
      const defaultValue = getFieldDefaultValue({ fieldSchema, objectTemplate });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          type: "template",
          id: "template-id",
          label: "template-id",
          kind: "FakeTemplate",
        },
        value: "template-value",
      });
    });

    it("returns pool value from template when field value is null and source is a pool", () => {
      // GIVEN
      store.set(nodeSchemasAtom, [
        generateNodeSchema({
          kind: "CoreNumberPool",
          inherit_from: ["CoreResourcePool"],
        }),
      ]);

      const fieldSchema = generateAttributeSchema({ name: "field1" });
      const objectTemplate: NodeObjectWithMetadata = {
        id: "template-id",
        __typename: "FakeTemplate",
        field1: {
          value: null,
          is_default: false,
          is_from_profile: false,
          is_protected: false,
          is_visible: true,
          owner: null,
          updated_at: new Date().toISOString(),
          source: {
            id: "pool-id",
            display_label: "My Number Pool",
            __typename: "CoreNumberPool",
          },
        },
      };

      // WHEN
      const defaultValue = getFieldDefaultValue({ fieldSchema, objectTemplate });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          type: "pool",
          id: "pool-id",
          label: "My Number Pool",
          kind: "CoreNumberPool",
        },
        value: { from_pool: { id: "pool-id" } },
      });
    });

    it("returns null when template field value is null and source is not a pool", () => {
      // GIVEN
      const fieldSchema = generateAttributeSchema({ name: "field1" });
      const objectTemplate: NodeObjectWithMetadata = {
        id: "template-id",
        __typename: "FakeTemplate",
        field1: {
          value: null,
          is_default: false,
          is_from_profile: false,
          is_protected: false,
          is_visible: true,
          owner: null,
          updated_at: new Date().toISOString(),
          source: {
            id: "pool-id",
            display_label: "My Number Pool",
            __typename: "CoreNumberPool",
          },
        },
      };

      // WHEN
      const defaultValue = getFieldDefaultValue({ fieldSchema, objectTemplate });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          type: "schema",
        },
        value: null,
      });
    });

    it("returns null value when template field value is null", () => {
      // GIVEN
      const fieldSchema = generateAttributeSchema({ name: "field1" });
      const objectTemplate: NodeObject = {
        id: "template-id",
        __typename: "FakeTemplate",
        field1: {
          value: null,
        },
      };

      // WHEN
      const defaultValue = getFieldDefaultValue({ fieldSchema, objectTemplate });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          type: "schema",
        },
        value: null,
      });
    });

    it("returns template when source is template", () => {
      // GIVEN
      const fieldSchema = generateAttributeSchema({
        name: "field1",
        default_value: "my-default-value",
      });

      const initialObject: Record<string, AttributeType> = {
        field1: {
          value: "my-value",
          source: {
            id: "template-id",
            display_label: "Template",
            __typename: "FakeTemplateKind",
          },
        },
      };

      // WHEN
      const defaultValue = getFieldDefaultValue({ fieldSchema, initialObject });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          id: "template-id",
          kind: "FakeTemplateKind",
          label: "Template",
          type: "template",
        },
        value: "my-value",
      });
    });
  });

  describe("when source is pool", () => {
    it("returns object value when assigned from a pool", () => {
      // GIVEN
      const fieldSchema = generateAttributeSchema({
        name: "field1",
        default_value: "my-default-value",
      });

      const initialObject: Record<string, AttributeType> = {
        field1: {
          value: "my-default-value",
          source: {
            id: "pool-id",
            display_label: "Fake pool",
            __typename: "FakePool",
          },
        },
      };

      // WHEN
      const defaultValue = getFieldDefaultValue({ fieldSchema, initialObject });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          type: "pool",
          id: "pool-id",
          label: "Fake pool",
          kind: "FakePool",
        },
        value: "my-default-value",
      });
    });
  });
});
