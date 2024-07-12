import { describe, expect, it } from "vitest";
import {
  GetFieldDefaultValue,
  getFieldDefaultValue,
} from "@/components/form/utils/getFieldDefaultValue";
import { ProfileData } from "@/components/form/object-form";
import { buildAttributeSchema, buildRelationshipSchema } from "./getFormFieldsFromSchema.test";
import { AttributeType } from "@/utils/getObjectItemDisplayValue";

describe("getFieldDefaultValue", () => {
  describe("when source is the user", () => {
    it("returns current object field's value when value is not from profile", () => {
      // GIVEN
      const fieldSchema = buildAttributeSchema({ name: "field1" });

      const profiles = [
        {
          id: "profile1",
          display_label: "Profile 1",
          field1: {
            value: "test-value-form-profile",
          },
        },
      ] as Array<ProfileData>;

      const initialObject: Record<string, AttributeType> = {
        field1: {
          value: "test-value-from-user",
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
      const fieldSchema = buildAttributeSchema({ name: "field1" });

      const profiles = [
        {
          id: "profile1",
          display_label: "Profile 1",
          field1: {
            value: "test-value-form-profile",
          },
        },
      ] as Array<ProfileData>;

      const initialObject: Record<string, AttributeType> = {
        field1: {
          value: null,
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
      const fieldSchema = buildAttributeSchema({ name: "field1" });

      const profiles = [
        {
          id: "profile1",
          display_label: "Profile 1",
          field1: {
            value: "test-value-form-profile",
          },
        },
      ] as Array<ProfileData>;

      const initialObject: Record<string, AttributeType> = {
        field1: {
          value: 0,
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
      const fieldSchema = buildAttributeSchema({ name: "field1" });

      const profiles = [
        {
          id: "profile1",
          display_label: "Profile 1",
          field1: {
            value: "test-value-form-profile",
          },
        },
      ] as Array<ProfileData>;

      const initialObject = {};

      // WHEN
      const defaultValue = getFieldDefaultValue({ fieldSchema, initialObject, profiles });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          label: "Profile 1",
          type: "profile",
        },
        value: "test-value-form-profile",
      });
    });

    it("returns profile's value when it exists, current object field is found and is from profile", () => {
      // GIVEN
      const fieldSchema = buildAttributeSchema({ name: "field1" });

      const profiles = [
        {
          id: "profile1",
          display_label: "Profile 1",
          field1: {
            value: "test-value-form-profile",
          },
        },
      ] as Array<ProfileData>;

      const initialObject: Record<string, AttributeType> = {
        field1: {
          value: "test-value-form-profile",
          is_from_profile: true,
        },
      };

      // WHEN
      const defaultValue = getFieldDefaultValue({ fieldSchema, initialObject, profiles });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          label: "Profile 1",
          type: "profile",
        },
        value: "test-value-form-profile",
      });
    });

    it("returns profile's value when it exists and value is null", () => {
      // GIVEN
      const fieldSchema = buildAttributeSchema({ name: "field1" });

      const profiles = [
        {
          id: "profile1",
          display_label: "Profile 1",
          field1: {
            value: null,
          },
        },
      ] as Array<ProfileData>;

      // WHEN
      const defaultValue = getFieldDefaultValue({ fieldSchema, profiles });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          label: "Profile 1",
          type: "profile",
        },
        value: null,
      });
    });

    it("returns profile's value when it exists and value is 0", () => {
      // GIVEN
      const fieldSchema = buildAttributeSchema({ name: "field1" });

      const profiles = [
        {
          id: "profile1",
          display_label: "Profile 1",
          field1: {
            value: 0,
          },
        },
      ] as Array<ProfileData>;

      // WHEN
      const defaultValue = getFieldDefaultValue({ fieldSchema, profiles });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          label: "Profile 1",
          type: "profile",
        },
        value: 0,
      });
    });

    it("returns profile's value with the highest priority + order by id ASC", () => {
      // GIVEN
      const fieldSchema = {
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
      } satisfies GetFieldDefaultValue["fieldSchema"];

      const profiles = [
        {
          id: "profile3",
          display_label: "Profile 3",
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
          name: {
            value: "second",
          },
          profile_priority: {
            value: 1,
          },
        },
      ] as Array<ProfileData>;

      // WHEN
      const defaultValue = getFieldDefaultValue({ fieldSchema, profiles });

      // THEN
      expect(defaultValue).to.deep.equal({
        source: {
          label: "Profile 2",
          type: "profile",
        },
        value: "second",
      });
    });
  });

  describe("when source is schema", () => {
    it("returns schema's default value when it exists, and no profile nor current object field value are provided", () => {
      // GIVEN
      const fieldSchema = {
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
      } satisfies GetFieldDefaultValue["fieldSchema"];

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
      const fieldSchema = buildAttributeSchema();

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
  });

  it("returns null if field is an relationship and no object field value is provided", () => {
    // GIVEN
    const fieldSchema = buildRelationshipSchema();

    // WHEN
    const defaultValue = getFieldDefaultValue({ fieldSchema });

    // THEN
    expect(defaultValue).to.deep.equal({ source: null, value: null });
  });
});