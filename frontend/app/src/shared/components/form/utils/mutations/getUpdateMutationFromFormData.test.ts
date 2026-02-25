import { describe, expect, it } from "vitest";

import type {
  DynamicFieldProps,
  FormAttributeValue,
  FormRelationshipValue,
  RelationshipValueFromPool,
} from "@/shared/components/form/type";
import { getUpdateMutationFromFormData } from "@/shared/components/form/utils/mutations/getUpdateMutationFromFormData";

import { buildFormField } from "../../../../../../tests/fake/form";

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
      buildFormField({
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

  it("correctly unset the array for multiselect", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [
      buildFormField({
        name: "field1",
        defaultValue: { source: { type: "user" }, value: ["test"] },
      }),
    ];
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "user" }, value: [] },
    };

    // WHEN
    const mutationData = getUpdateMutationFromFormData({ fields, formData });

    // THEN
    expect(mutationData).to.deep.equal({
      field1: null,
    });
  });

  it("set value to null if it's from the user and is an empty string", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [
      buildFormField({
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

  it("set attribute to null if it's from the user and value is null", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [
      buildFormField({
        name: "field1",
        defaultValue: { source: { type: "user" }, value: "old-value" },
      }),
    ];
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "user" }, value: null },
    };

    // WHEN
    const mutationData = getUpdateMutationFromFormData({ fields, formData });

    // THEN
    expect(mutationData).to.deep.equal({
      field1: { value: null },
    });
  });

  it("set relationship to null if it's from the user and value is null", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [
      buildFormField({
        name: "relationship1",
        type: "relationship",
        defaultValue: {
          source: { type: "schema" },
          value: null,
        },
      }),
    ];
    const formData: Record<string, FormRelationshipValue> = {
      relationship1: { source: { type: "user" }, value: null },
    };

    // WHEN
    const mutationData = getUpdateMutationFromFormData({ fields, formData });

    // THEN
    expect(mutationData).to.deep.equal({
      relationship1: null,
    });
  });

  it("removes field if value and source are not updated", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [
      buildFormField({
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
      buildFormField({
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

  it("keeps field if source change from user to pool", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [
      buildFormField({
        name: "field1",
        type: "relationship",
        defaultValue: {
          source: { type: "user" },
          value: { id: "value1", display_label: "value1", __typename: "FakeResource" },
        },
      }),
    ];
    const formData: Record<string, RelationshipValueFromPool> = {
      field1: {
        source: {
          type: "pool",
          label: "test name pool",
          id: "pool-id",
          kind: "FakeResourcePool",
        },
        value: {
          from_pool: { id: "pool-id" },
        },
      },
    };

    // WHEN
    const mutationData = getUpdateMutationFromFormData({ fields, formData });

    // THEN
    expect(mutationData).to.deep.equal({
      field1: {
        from_pool: { id: "pool-id" },
      },
    });
  });

  describe("Resource pool from-pool relationship", () => {
    it("splits pool value to from-pool relationship when fromPoolRelationshipName is set", () => {
      // GIVEN
      const fields: Array<DynamicFieldProps> = [
        buildFormField({
          name: "ip_address",
          type: "relationship",
          defaultValue: {
            source: { type: "user" },
            value: { id: "old-ip", display_label: "10.0.0.1", __typename: "InfraIPAddress" },
          },
          pool: {
            kind: "CoreIPAddressPool",
            defaultAllocatedObjectKind: "InfraIPAddress",
            fromPoolRelationshipName: "ip_address_from_resource_pool",
          },
        }),
      ];
      const formData: Record<string, RelationshipValueFromPool> = {
        ip_address: {
          source: {
            type: "pool",
            label: "test pool",
            id: "pool-id",
            kind: "CoreIPAddressPool",
          },
          value: { from_pool: { id: "pool-id" } },
        },
      };

      // WHEN
      const mutationData = getUpdateMutationFromFormData({ fields, formData });

      // THEN
      expect(mutationData).to.deep.equal({
        ip_address: null,
        ip_address_from_resource_pool: { id: "pool-id" },
      });
    });

    it("sets from-pool relationship to null when user selects a direct value", () => {
      // GIVEN
      const fields: Array<DynamicFieldProps> = [
        buildFormField({
          name: "ip_address",
          type: "relationship",
          defaultValue: {
            source: { type: "user" },
            value: { id: "old-ip", display_label: "10.0.0.1", __typename: "InfraIPAddress" },
          },
          pool: {
            kind: "CoreIPAddressPool",
            defaultAllocatedObjectKind: "InfraIPAddress",
            fromPoolRelationshipName: "ip_address_from_resource_pool",
          },
        }),
      ];
      const formData: Record<string, FormRelationshipValue> = {
        ip_address: {
          source: { type: "user" },
          value: {
            id: "new-ip",
            display_label: "10.0.0.2",
            __typename: "InfraIPAddress",
          },
        },
      };

      // WHEN
      const mutationData = getUpdateMutationFromFormData({ fields, formData });

      // THEN
      expect(mutationData).to.deep.equal({
        ip_address: { id: "new-ip" },
        ip_address_from_resource_pool: null,
      });
    });

    it("sets both to null when value is null", () => {
      // GIVEN
      const fields: Array<DynamicFieldProps> = [
        buildFormField({
          name: "ip_address",
          type: "relationship",
          defaultValue: {
            source: { type: "user" },
            value: { id: "old-ip", display_label: "10.0.0.1", __typename: "InfraIPAddress" },
          },
          pool: {
            kind: "CoreIPAddressPool",
            defaultAllocatedObjectKind: "InfraIPAddress",
            fromPoolRelationshipName: "ip_address_from_resource_pool",
          },
        }),
      ];
      const formData: Record<string, FormRelationshipValue> = {
        ip_address: {
          source: { type: "user" },
          value: null,
        },
      };

      // WHEN
      const mutationData = getUpdateMutationFromFormData({ fields, formData });

      // THEN
      expect(mutationData).to.deep.equal({
        ip_address: null,
        ip_address_from_resource_pool: null,
      });
    });
  });

  it("set is_default: true if field if value is from profile", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [
      buildFormField({
        name: "field1",
        defaultValue: { source: { type: "user" }, value: "value1" },
      }),
    ];
    const formData: Record<string, FormAttributeValue> = {
      field1: {
        source: {
          type: "profile",
          kind: "FakeProfileKind",
          id: "profile-id",
          label: "Profile 1",
        },
        value: "profile1",
      },
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
      buildFormField({
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

  describe("Attribute of kind list", () => {
    it("set correctly attribute of kind list when initial value is null", () => {
      // GIVEN
      const fields: Array<DynamicFieldProps> = [
        buildFormField({
          name: "listField",
          type: "List",
          defaultValue: { source: null, value: null },
        }),
      ];
      const formData: Record<string, FormAttributeValue> = {
        listField: { source: { type: "user" }, value: ["item2", "item3"] },
      };

      // WHEN
      const mutationData = getUpdateMutationFromFormData({ fields, formData });

      // THEN
      expect(mutationData).to.deep.equal({
        listField: { value: ["item2", "item3"] },
      });
    });

    it("set correctly attribute of kind list when initial has items", () => {
      // GIVEN
      const fields: Array<DynamicFieldProps> = [
        buildFormField({
          name: "listField",
          type: "List",
          defaultValue: { source: { type: "user" }, value: ["item1"] },
        }),
      ];
      const formData: Record<string, FormAttributeValue> = {
        listField: { source: { type: "user" }, value: ["item2", "item3"] },
      };

      // WHEN
      const mutationData = getUpdateMutationFromFormData({ fields, formData });

      // THEN
      expect(mutationData).to.deep.equal({
        listField: { value: ["item2", "item3"] },
      });
    });
  });
});
