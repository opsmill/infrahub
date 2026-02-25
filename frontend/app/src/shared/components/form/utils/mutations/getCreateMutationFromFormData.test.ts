import { describe, expect, it } from "vitest";

import type {
  AttributeValueFromProfile,
  DynamicFieldProps,
  FormAttributeValue,
  FormFieldValue,
  FormRelationshipValue,
} from "@/shared/components/form/type";
import {
  getCreateMutationFromFormData,
  getCreateMutationFromFormDataOnly,
} from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";

import { buildFormField } from "../../../../../../tests/fake/form";
import { generateRelationshipNode } from "../../../../../../tests/fake/node";

describe("getCreateMutationFromFormData", () => {
  it("returns empty if there is no fields in form", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [];
    const formData: Record<string, FormFieldValue> = {};

    // WHEN
    const mutationData = getCreateMutationFromFormData(fields, formData);

    // THEN
    expect(mutationData).to.deep.equal({});
  });

  it("returns empty if form data is empty", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [buildFormField()];
    const formData: Record<string, FormFieldValue> = {};

    // WHEN
    const mutationData = getCreateMutationFromFormData(fields, formData);

    // THEN
    expect(mutationData).to.deep.equal({});
  });

  it("keeps items if value is null and it's from the user", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [buildFormField({ name: "field1" })];
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
      buildFormField({
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
      buildFormField({
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
      buildFormField({
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
      relationship1: {
        source: { type: "user" },
        value: {
          id: "relationship-id",
          display_label: "Relationship 1",
          __typename: "relationship",
        },
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
      relationship1: { from_pool: { id: "pool-id" } },
    });
  });

  describe("Resource pool from-pool relationship", () => {
    it("splits pool value to from-pool relationship when fromPoolRelationshipName is set", () => {
      // GIVEN
      const fields: Array<DynamicFieldProps> = [
        buildFormField({
          name: "ip_address",
          type: "relationship",
          pool: {
            kind: "CoreIPAddressPool",
            defaultAllocatedObjectKind: "InfraIPAddress",
            fromPoolRelationshipName: "ip_address_from_resource_pool",
          },
        }),
      ];
      const formData: Record<string, FormRelationshipValue> = {
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
      const mutationData = getCreateMutationFromFormData(fields, formData);

      // THEN
      expect(mutationData).to.deep.equal({
        ip_address_from_resource_pool: { id: "pool-id" },
      });
    });

    it("only sends direct value when user selects a direct value", () => {
      // GIVEN
      const fields: Array<DynamicFieldProps> = [
        buildFormField({
          name: "ip_address",
          type: "relationship",
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
            id: "ip-id",
            display_label: "10.0.0.1",
            __typename: "InfraIPAddress",
          },
        },
      };

      // WHEN
      const mutationData = getCreateMutationFromFormData(fields, formData);

      // THEN
      expect(mutationData).to.deep.equal({
        ip_address: { id: "ip-id" },
      });
    });

    it("excludes pool value when it comes from template", () => {
      // GIVEN
      const fields: Array<DynamicFieldProps> = [
        buildFormField({
          name: "ip_address",
          type: "relationship",
          pool: {
            kind: "CoreIPAddressPool",
            defaultAllocatedObjectKind: "InfraIPAddress",
            fromPoolRelationshipName: "ip_address_from_resource_pool",
          },
        }),
      ];
      const formData: Record<string, FormRelationshipValue> = {
        ip_address: {
          source: {
            type: "pool",
            fromTemplate: true,
            label: "Loopbacks pool",
            id: "pool-id",
            kind: "CoreIPAddressPool",
          },
          value: {
            id: "pool-id",
            display_label: "Loopbacks pool",
            __typename: "CoreIPAddressPool",
          },
        },
      };

      // WHEN
      const mutationData = getCreateMutationFromFormData(fields, formData, "template-id");

      // THEN
      expect(mutationData).to.deep.equal({
        object_template: { id: "template-id" },
      });
    });

    it("includes pool value when user selects pool manually", () => {
      // GIVEN
      const fields: Array<DynamicFieldProps> = [
        buildFormField({
          name: "ip_address",
          type: "relationship",
          pool: {
            kind: "CoreIPAddressPool",
            defaultAllocatedObjectKind: "InfraIPAddress",
            fromPoolRelationshipName: "ip_address_from_resource_pool",
          },
        }),
      ];
      const formData: Record<string, FormRelationshipValue> = {
        ip_address: {
          source: {
            type: "pool",
            label: "User selected pool",
            id: "user-pool-id",
            kind: "CoreIPAddressPool",
          },
          value: { from_pool: { id: "user-pool-id" } },
        },
      };

      // WHEN
      const mutationData = getCreateMutationFromFormData(fields, formData, "template-id");

      // THEN
      expect(mutationData).to.deep.equal({
        object_template: { id: "template-id" },
        ip_address_from_resource_pool: { id: "user-pool-id" },
      });
    });

    it("only sends null on direct field when value is null", () => {
      // GIVEN
      const fields: Array<DynamicFieldProps> = [
        buildFormField({
          name: "ip_address",
          type: "relationship",
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
      const mutationData = getCreateMutationFromFormData(fields, formData);

      // THEN
      expect(mutationData).to.deep.equal({
        ip_address: { value: null },
      });
    });
  });

  it("keeps relationship with cardinality many's value if it's from user input", () => {
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
      relationship1: {
        source: { type: "user" },
        value: [
          {
            id: "relationship-id",
            display_label: "Relationship 1",
            __typename: "relationship",
          },
        ],
      },
    };

    // WHEN
    const mutationData = getCreateMutationFromFormData(fields, formData);

    // THEN
    expect(mutationData).to.deep.equal({
      relationship1: [{ id: "relationship-id" }],
    });
  });

  it("set value as null if value is an empty string", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [buildFormField({ name: "field1" })];
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
    const fields: Array<DynamicFieldProps> = [buildFormField({ name: "field1" })];
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

  it("does not include field whose source is template", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [
      buildFormField({ name: "field1" }),
      buildFormField({ name: "field2" }),
    ];
    const formData: Record<string, FormFieldValue> = {
      field1: {
        source: {
          type: "template",
          id: "template-id",
          label: "Template 1",
          kind: "Template",
        },
        value: "template-value",
      },
      field2: { source: { type: "user" }, value: 0 },
    };

    // WHEN
    const mutationData = getCreateMutationFromFormData(fields, formData, "template-id");

    // THEN
    expect(mutationData).to.deep.equal({
      object_template: { id: "template-id" },
      field2: { value: 0 },
    });
  });

  it("includes object_template in mutation data even with no template fields", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [buildFormField({ name: "field1" })];
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "user" }, value: "value1" },
    };

    // WHEN
    const mutationData = getCreateMutationFromFormData(fields, formData, "template-id");

    // THEN
    expect(mutationData).to.deep.equal({
      field1: { value: "value1" },
      object_template: { id: "template-id" },
    });
  });

  describe("Attribute of kind list", () => {
    it("set correctly attribute of kind list when value is from schema", () => {
      // GIVEN
      const fields: Array<DynamicFieldProps> = [
        buildFormField({
          name: "listField",
          type: "List",
          defaultValue: { source: { type: "schema" }, value: ["item1"] },
        }),
      ];
      const formData: Record<string, FormAttributeValue> = {
        listField: { source: { type: "schema" }, value: ["item1"] },
      };

      // WHEN
      const mutationData = getCreateMutationFromFormData(fields, formData);

      // THEN
      expect(mutationData).to.deep.equal({});
    });

    it("set correctly attribute of kind list when value is from user", () => {
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
      const mutationData = getCreateMutationFromFormData(fields, formData);

      // THEN
      expect(mutationData).to.deep.equal({
        listField: { value: ["item2", "item3"] },
      });
    });

    it("set correctly attribute field if value is from user and is an empty array", () => {
      // GIVEN
      const fields: Array<DynamicFieldProps> = [
        buildFormField({
          name: "listField",
          type: "List",
          defaultValue: { source: { type: "schema" }, value: ["item1"] },
        }),
      ];
      const formData: Record<string, FormAttributeValue> = {
        listField: { source: { type: "user" }, value: [] },
      };

      // WHEN
      const mutationData = getCreateMutationFromFormData(fields, formData);

      // THEN
      expect(mutationData).to.deep.equal({
        listField: { value: [] },
      });
    });
  });
});

describe("getCreateMutationFromFormDataOnly", () => {
  it("returns empty object if form data is empty", () => {
    // GIVEN
    const formData: Record<string, FormFieldValue> = {};

    // WHEN
    const mutationData = getCreateMutationFromFormDataOnly(formData);

    // THEN
    expect(mutationData).to.deep.equal({});
  });

  it("handles user input values correctly", () => {
    // GIVEN
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "user" }, value: "value1" },
    };

    // WHEN
    const mutationData = getCreateMutationFromFormDataOnly(formData);

    // THEN
    expect(mutationData).to.deep.equal({
      field1: { value: "value1" },
    });
  });

  it("handles empty string values as null", () => {
    // GIVEN
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "user" }, value: "" },
    };

    // WHEN
    const mutationData = getCreateMutationFromFormDataOnly(formData);

    // THEN
    expect(mutationData).to.deep.equal({
      field1: { value: null },
    });
  });

  it("handles relationship values correctly", () => {
    // GIVEN
    const formData: Record<string, FormRelationshipValue> = {
      relationship1: {
        source: { type: "user" },
        value: [
          generateRelationshipNode({ id: "rel-id-1", display_label: "Rel 1" }),
          generateRelationshipNode({ id: "rel-id-2", display_label: "Rel 2" }),
        ],
      },
    };

    // WHEN
    const mutationData = getCreateMutationFromFormDataOnly(formData);

    // THEN
    expect(mutationData).to.deep.equal({
      relationship1: [{ id: "rel-id-1" }, { id: "rel-id-2" }],
    });
  });

  it("handles pool values correctly", () => {
    // GIVEN
    const formData: Record<string, FormFieldValue> = {
      field1: {
        source: {
          type: "pool",
          label: "Pool 1",
          id: "pool-id",
          kind: "ResourcePool",
        },
        value: { from_pool: { id: "pool-id" } },
      },
    };

    // WHEN
    const mutationData = getCreateMutationFromFormDataOnly(formData);

    // THEN
    expect(mutationData).to.deep.equal({
      field1: { from_pool: { id: "pool-id" } },
    });
  });

  it("excludes pool values from template", () => {
    // GIVEN
    const formData: Record<string, FormFieldValue> = {
      field1: {
        source: {
          type: "pool",
          fromTemplate: true,
          label: "Pool 1",
          id: "pool-id",
          kind: "ResourcePool",
        },
        value: { from_pool: { id: "pool-id" } },
      },
    };

    // WHEN
    const mutationData = getCreateMutationFromFormDataOnly(formData, undefined, "template-id");

    // THEN
    expect(mutationData).to.deep.equal({
      object_template: { id: "template-id" },
    });
  });

  it("skips values that match current object values", () => {
    // GIVEN
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "user" }, value: "unchanged" },
      field2: { source: { type: "user" }, value: "changed" },
    };
    const currentObject = {
      field1: { value: "unchanged" },
      field2: { value: "old-value" },
    };

    // WHEN
    const mutationData = getCreateMutationFromFormDataOnly(formData, currentObject);

    // THEN
    expect(mutationData).to.deep.equal({
      field2: { value: "changed" },
    });
  });

  it("handles relationship value correctly", () => {
    // GIVEN
    const formData: Record<string, FormFieldValue> = {
      field1: {
        source: {
          type: "user",
        },
        value: { id: "peer-id", display_label: "peer test", __typename: "PeerKind" },
      },
    };

    // WHEN
    const mutationData = getCreateMutationFromFormDataOnly(formData);

    // THEN
    expect(mutationData).to.deep.equal({
      field1: { id: "peer-id" },
    });
  });
});
