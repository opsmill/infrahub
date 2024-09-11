import { describe, expect } from "vitest";
import {
  DynamicFieldProps,
  FormAttributeValue,
  FormRelationshipValue,
  AttributeValueFromProfile,
} from "@/components/form/type";
import { getCreateMutationFromFormData } from "@/components/form/utils/mutations/getCreateMutationFromFormData";

export const buildField = (override?: Partial<DynamicFieldProps>): DynamicFieldProps => {
  return {
    name: "field1",
    label: "Field 1",
    defaultValue: null,
    disabled: false,
    type: "Text",
    rules: {
      required: true,
    },
    unique: true,
    ...override,
  } as DynamicFieldProps;
};

describe("getCreateMutationFromFormData - test", () => {
  it("returns empty if there is no fields in form", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [];
    const formData: Record<string, FormAttributeValue> = {};

    // WHEN
    const mutationData = getCreateMutationFromFormData(fields, formData);

    // THEN
    expect(mutationData).to.deep.equal({});
  });

  it("returns empty if form data if empty", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [buildField()];
    const formData: Record<string, FormAttributeValue> = {};

    // WHEN
    const mutationData = getCreateMutationFromFormData(fields, formData);

    // THEN
    expect(mutationData).to.deep.equal({});
  });

  it("keeps items if value is null and it's from the user", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [buildField({ name: "field1" })];
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "user" }, value: null },
    };

    // WHEN
    const mutationData = getCreateMutationFromFormData(fields, formData);

    // THEN
    expect(mutationData).to.deep.equal({
      field1: { value: null },
    });
  });

  it("removes items if value is from schema's default value", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [
      buildField({
        name: "field1",
        defaultValue: {
          source: { type: "schema" },
          value: "value1",
        },
      }),
    ];
    const formData: Record<string, FormAttributeValue> = {
      field1: {
        source: { type: "schema" },
        value: "value1",
      },
    };

    // WHEN
    const mutationData = getCreateMutationFromFormData(fields, formData);

    // THEN
    expect(mutationData).to.deep.equal({});
  });

  it("removes items if value is from profile", () => {
    // GIVEN
    const profileFieldValue: AttributeValueFromProfile = {
      source: {
        type: "profile",
        kind: "FakeProfileKind",
        id: "profile-id",
        label: "Profile 1",
      },
      value: "value1",
    };

    const fields: Array<DynamicFieldProps> = [
      buildField({
        name: "field1",
        type: "Text",
        defaultValue: profileFieldValue,
      }),
    ];
    const formData: Record<string, FormAttributeValue> = {
      field1: profileFieldValue,
    };

    // WHEN
    const mutationData = getCreateMutationFromFormData(fields, formData);

    // THEN
    expect(mutationData).to.deep.equal({});
  });

  it("keeps attribute value if it's from user input", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [
      buildField({
        name: "field1",
        type: "Text",
        defaultValue: {
          source: {
            type: "profile",
            kind: "FakeProfileKind",
            id: "profile-id",
            label: "Profile 1",
          },
          value: "value1",
        },
      }),
    ];
    const formData: Record<string, FormAttributeValue> = {
      field1: {
        source: { type: "user" },
        value: "value2",
      },
    };

    // WHEN
    const mutationData = getCreateMutationFromFormData(fields, formData);

    // THEN
    expect(mutationData).to.deep.equal({
      field1: { value: "value2" },
    });
  });

  it("keeps relationship with cardinality one's value if it's from user input", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [
      buildField({
        name: "relationship1",
        type: "relationship",
        defaultValue: {
          source: { type: "schema" },
          value: null,
        },
      }),
    ];
    const formData: Record<string, FormRelationshipValue> = {
      relationship1: {
        source: { type: "user" },
        value: { id: "relationship-id" },
      },
    };

    // WHEN
    const mutationData = getCreateMutationFromFormData(fields, formData);

    // THEN
    expect(mutationData).to.deep.equal({
      relationship1: { id: "relationship-id" },
    });
  });

  it("keeps relationship with cardinality one's value if it's from pool", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [
      buildField({
        name: "relationship1",
        type: "relationship",
        defaultValue: {
          source: { type: "schema" },
          value: null,
        },
      }),
    ];
    const formData: Record<string, FormRelationshipValue> = {
      relationship1: {
        source: {
          type: "pool",
          label: "test name pool",
          id: "pool-id",
          kind: "FakeResourcePool",
        },
        value: { from_pool: { id: "pool-id" } },
      },
    };

    // WHEN
    const mutationData = getCreateMutationFromFormData(fields, formData);

    // THEN
    expect(mutationData).to.deep.equal({
      relationship1: {
        from_pool: { id: "pool-id" },
      },
    });
  });

  it("keeps relationship with cardinality many's value if it's from user input", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [
      buildField({
        name: "relationship1",
        type: "relationship",
        defaultValue: {
          source: { type: "schema" },
          value: null,
        },
      }),
    ];
    const formData: Record<string, FormRelationshipValue> = {
      relationship1: {
        source: { type: "user" },
        value: [{ id: "relationship-id" }],
      },
    };

    // WHEN
    const mutationData = getCreateMutationFromFormData(fields, formData);

    // THEN
    expect(mutationData).to.deep.equal({
      relationship1: [{ id: "relationship-id" }],
    });
  });

  it("set value as null is value is an empty string", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [buildField({ name: "field1" })];
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "user" }, value: "" },
    };

    // WHEN
    const mutationData = getCreateMutationFromFormData(fields, formData);

    // THEN
    expect(mutationData).to.deep.equal({
      field1: { value: null },
    });
  });

  it("keeps items if value is 0", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [buildField({ name: "field1" })];
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "user" }, value: 0 },
    };

    // WHEN
    const mutationData = getCreateMutationFromFormData(fields, formData);

    // THEN
    expect(mutationData).to.deep.equal({
      field1: { value: 0 },
    });
  });
});
