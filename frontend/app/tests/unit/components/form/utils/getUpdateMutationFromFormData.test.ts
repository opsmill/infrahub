import { describe, expect } from "vitest";
import { DynamicFieldProps, FormAttributeValue } from "@/components/form/type";
import { getUpdateMutationFromFormData } from "@/components/form/utils/mutations/getUpdateMutationFromFormData";
import { buildField } from "./getCreateMutationFromFormData.test";

describe("getUpdateMutationFromFormData - test", () => {
  it("returns empty if there is no fields in form", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [];
    const formData: Record<string, FormAttributeValue> = {};

    // WHEN
    const mutationData = getUpdateMutationFromFormData({ fields, formData });

    // THEN
    expect(mutationData).to.deep.equal({});
  });

  it("keeps value if it's from the user", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [
      buildField({
        name: "field1",
        defaultValue: { source: { type: "user" }, value: "old-value" },
      }),
    ];
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "user" }, value: "test-value" },
    };

    // WHEN
    const mutationData = getUpdateMutationFromFormData({ fields, formData });

    // THEN
    expect(mutationData).to.deep.equal({
      field1: { value: "test-value" },
    });
  });

  it("set value to null if it's from the user and is an empty string", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [
      buildField({
        name: "field1",
        defaultValue: { source: { type: "user" }, value: "old-value" },
      }),
    ];
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "user" }, value: "" },
    };

    // WHEN
    const mutationData = getUpdateMutationFromFormData({ fields, formData });

    // THEN
    expect(mutationData).to.deep.equal({
      field1: { value: null },
    });
  });

  it("removes field if value and source are not updated", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [
      buildField({
        name: "field1",
        defaultValue: { source: { type: "user" }, value: "old-value" },
      }),
    ];
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "user" }, value: "old-value" },
    };

    // WHEN
    const mutationData = getUpdateMutationFromFormData({ fields, formData });

    // THEN
    expect(mutationData).to.deep.equal({});
  });

  it("keeps field if source is updated", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [
      buildField({
        name: "field1",
        defaultValue: { source: { type: "schema" }, value: "value1" },
      }),
    ];
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "user" }, value: "value1" },
    };

    // WHEN
    const mutationData = getUpdateMutationFromFormData({ fields, formData });

    // THEN
    expect(mutationData).to.deep.equal({
      field1: { value: "value1" },
    });
  });

  it("set is_default: true if field if value is from profile", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [
      buildField({
        name: "field1",
        defaultValue: { source: { type: "user" }, value: "value1" },
      }),
    ];
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "profile" }, value: "profile1" },
    };

    // WHEN
    const mutationData = getUpdateMutationFromFormData({ fields, formData });

    // THEN
    expect(mutationData).to.deep.equal({
      field1: { is_default: true },
    });
  });

  it("set is_default: true if field if value is from schema", () => {
    const fields: Array<DynamicFieldProps> = [
      buildField({
        name: "field1",
        defaultValue: { source: { type: "user" }, value: "value1" },
      }),
    ];
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "schema" }, value: "value2" },
    };

    // WHEN
    const mutationData = getUpdateMutationFromFormData({ fields, formData });

    // THEN
    expect(mutationData).to.deep.equal({
      field1: { is_default: true },
    });
  });
});
