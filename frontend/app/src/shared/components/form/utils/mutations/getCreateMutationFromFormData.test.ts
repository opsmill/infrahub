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
    const fields: Array<DynamicFieldProps> = [];
    const formData: Record<string, FormFieldValue> = {};

    const mutationData = getCreateMutationFromFormData(fields, formData);

    expect(mutationData).to.deep.equal({});
  });

  it("returns empty if form data is empty", () => {
    const fields: Array<DynamicFieldProps> = [buildFormField()];
    const formData: Record<string, FormFieldValue> = {};

    const mutationData = getCreateMutationFromFormData(fields, formData);

    expect(mutationData).to.deep.equal({});
  });

  it("keeps items if value is null and it's from the user", () => {
    const fields: Array<DynamicFieldProps> = [buildFormField({ name: "field1" })];
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "user" }, value: null },
    };

    const mutationData = getCreateMutationFromFormData(fields, formData);

    expect(mutationData).to.deep.equal({
      field1: { value: null },
    });
  });

  it("removes items if value is from schema's default value", () => {
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

    const mutationData = getCreateMutationFromFormData(fields, formData);

    expect(mutationData).to.deep.equal({});
  });

  it("removes items if value is from profile", () => {
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

    const mutationData = getCreateMutationFromFormData(fields, formData);

    expect(mutationData).to.deep.equal({});
  });

  it("keeps attribute value if it's from user input", () => {
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

    const mutationData = getCreateMutationFromFormData(fields, formData);

    expect(mutationData).to.deep.equal({
      field1: { value: "value2" },
    });
  });

  it("keeps relationship with cardinality one's value if it's from user input", () => {
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

    const mutationData = getCreateMutationFromFormData(fields, formData);

    expect(mutationData).to.deep.equal({
      relationship1: { id: "relationship-id" },
    });
  });

  it("keeps relationship with cardinality one's value if it's from pool", () => {
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
          kind: "CoreIPAddressPool",
        },
        value: { from_pool: { id: "pool-id" } },
      },
    };

    const mutationData = getCreateMutationFromFormData(fields, formData);

    expect(mutationData).to.deep.equal({
      relationship1: { from_pool: { id: "pool-id" } },
    });
  });

  it("includes the requested prefixlen on a direct from-pool relationship", () => {
    const fields: Array<DynamicFieldProps> = [
      buildFormField({
        name: "primary_address",
        type: "relationship",
        pool: { kind: "CoreIPAddressPool", defaultAllocatedObjectKind: "IpamIPAddress" },
      }),
    ];
    const formData: Record<string, FormRelationshipValue> = {
      primary_address: {
        source: { type: "pool", label: "Loopbacks pool", id: "pool-id", kind: "CoreIPAddressPool" },
        value: { from_pool: { id: "pool-id", prefixLength: 32 } },
      },
    };

    const mutationData = getCreateMutationFromFormData(fields, formData);

    expect(mutationData).to.deep.equal({
      primary_address: { from_pool: { id: "pool-id", prefixlen: 32 } },
    });
  });

  it("omits prefixlen on a direct from-pool relationship when not set", () => {
    const fields: Array<DynamicFieldProps> = [
      buildFormField({
        name: "primary_address",
        type: "relationship",
        pool: { kind: "CoreIPAddressPool", defaultAllocatedObjectKind: "IpamIPAddress" },
      }),
    ];
    const formData: Record<string, FormRelationshipValue> = {
      primary_address: {
        source: { type: "pool", label: "Loopbacks pool", id: "pool-id", kind: "CoreIPAddressPool" },
        value: { from_pool: { id: "pool-id" } },
      },
    };

    const mutationData = getCreateMutationFromFormData(fields, formData);

    expect(mutationData).to.deep.equal({
      primary_address: { from_pool: { id: "pool-id" } },
    });
  });

  it("includes the chosen allocated kind as address_type on a direct from-pool relationship", () => {
    const fields: Array<DynamicFieldProps> = [
      buildFormField({
        name: "primary_address",
        type: "relationship",
        pool: { kind: "CoreIPAddressPool", defaultAllocatedObjectKind: "BuiltinIPAddress" },
      }),
    ];
    const formData: Record<string, FormRelationshipValue> = {
      primary_address: {
        source: { type: "pool", label: "Loopbacks pool", id: "pool-id", kind: "CoreIPAddressPool" },
        value: { from_pool: { id: "pool-id", allocatedKind: "IpamIPAddress" } },
      },
    };

    const mutationData = getCreateMutationFromFormData(fields, formData);

    expect(mutationData).to.deep.equal({
      primary_address: { from_pool: { id: "pool-id", address_type: "IpamIPAddress" } },
    });
  });

  it("includes the chosen allocated kind as prefix_type for an IP prefix pool", () => {
    const fields: Array<DynamicFieldProps> = [
      buildFormField({
        name: "prefix",
        type: "relationship",
        pool: { kind: "CoreIPPrefixPool", defaultAllocatedObjectKind: "BuiltinIPPrefix" },
      }),
    ];
    const formData: Record<string, FormRelationshipValue> = {
      prefix: {
        source: { type: "pool", label: "Supernet pool", id: "pool-id", kind: "CoreIPPrefixPool" },
        value: { from_pool: { id: "pool-id", allocatedKind: "IpamIPPrefix", prefixLength: 26 } },
      },
    };

    const mutationData = getCreateMutationFromFormData(fields, formData);

    expect(mutationData).to.deep.equal({
      prefix: { from_pool: { id: "pool-id", size: 26, prefix_type: "IpamIPPrefix" } },
    });
  });

  it("omits the allocated kind on a direct from-pool relationship when none was chosen", () => {
    const fields: Array<DynamicFieldProps> = [
      buildFormField({
        name: "primary_address",
        type: "relationship",
        pool: { kind: "CoreIPAddressPool", defaultAllocatedObjectKind: "BuiltinIPAddress" },
      }),
    ];
    const formData: Record<string, FormRelationshipValue> = {
      primary_address: {
        source: { type: "pool", label: "Loopbacks pool", id: "pool-id", kind: "CoreIPAddressPool" },
        value: { from_pool: { id: "pool-id" } },
      },
    };

    const mutationData = getCreateMutationFromFormData(fields, formData);

    expect(mutationData).to.deep.equal({
      primary_address: { from_pool: { id: "pool-id" } },
    });
  });

  describe("Resource pool from-pool relationship", () => {
    it("sends only the pool id on the _from_resource_pool field, since its peer is the pool kind (dropping the allocated kind)", () => {
      // `<rel>_from_resource_pool` is a plain RelatedNodeInput: sending `address_type` there is rejected before any resolver runs.
      const fields: Array<DynamicFieldProps> = [
        buildFormField({
          name: "ip_address",
          type: "relationship",
          pool: {
            kind: "CoreIPAddressPool",
            defaultAllocatedObjectKind: "BuiltinIPAddress",
            fromPoolRelationshipName: "ip_address_from_resource_pool",
          },
        }),
      ];
      const formData: Record<string, FormRelationshipValue> = {
        ip_address: {
          source: { type: "pool", label: "test pool", id: "pool-id", kind: "CoreIPAddressPool" },
          value: { from_pool: { id: "pool-id", allocatedKind: "IpamIPAddress" } },
        },
      };

      const mutationData = getCreateMutationFromFormData(fields, formData);

      expect(mutationData).to.deep.equal({
        ip_address_from_resource_pool: { id: "pool-id" },
      });
    });

    it("sends only the pool id on the _from_resource_pool field, since its peer is the pool kind (dropping the prefix length)", () => {
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
          source: { type: "pool", label: "test pool", id: "pool-id", kind: "CoreIPAddressPool" },
          value: { from_pool: { id: "pool-id", prefixLength: 24 } },
        },
      };

      const mutationData = getCreateMutationFromFormData(fields, formData);

      expect(mutationData).to.deep.equal({
        ip_address_from_resource_pool: { id: "pool-id" },
      });
    });

    it("splits pool value to from-pool relationship when fromPoolRelationshipName is set", () => {
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

      const mutationData = getCreateMutationFromFormData(fields, formData);

      expect(mutationData).to.deep.equal({
        ip_address_from_resource_pool: { id: "pool-id" },
      });
    });

    it("splits number attribute pool value to from-pool relationship", () => {
      const fields: Array<DynamicFieldProps> = [
        buildFormField({
          name: "weight",
          type: "Number",
          pool: {
            kind: "CoreNumberPool",
            defaultAllocatedObjectKind: "TestTemplate",
            fromPoolRelationshipName: "weight_from_resource_pool",
          },
        }),
      ];
      const formData: Record<string, FormAttributeValue> = {
        weight: {
          source: {
            type: "pool",
            label: "My Pool",
            id: "pool-id",
            kind: "CoreNumberPool",
          },
          value: { from_pool: { id: "pool-id" } },
        } as any,
      };

      const mutationData = getCreateMutationFromFormData(fields, formData);

      expect(mutationData).to.deep.equal({
        weight_from_resource_pool: { id: "pool-id" },
      });
    });

    it("only sends direct value when user selects a direct value", () => {
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

      const mutationData = getCreateMutationFromFormData(fields, formData);

      expect(mutationData).to.deep.equal({
        ip_address: { id: "ip-id" },
      });
    });

    it("excludes pool value when it comes from template", () => {
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

      const mutationData = getCreateMutationFromFormData(fields, formData, "template-id");

      expect(mutationData).to.deep.equal({
        object_template: { id: "template-id" },
      });
    });

    it("includes pool value when user selects pool manually", () => {
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

      const mutationData = getCreateMutationFromFormData(fields, formData, "template-id");

      expect(mutationData).to.deep.equal({
        object_template: { id: "template-id" },
        ip_address_from_resource_pool: { id: "user-pool-id" },
      });
    });

    it("only sends null on direct field when value is null", () => {
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

      const mutationData = getCreateMutationFromFormData(fields, formData);

      expect(mutationData).to.deep.equal({
        ip_address: { value: null },
      });
    });
  });

  it("keeps relationship with cardinality many's value if it's from user input", () => {
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

    const mutationData = getCreateMutationFromFormData(fields, formData);

    expect(mutationData).to.deep.equal({
      relationship1: [{ id: "relationship-id" }],
    });
  });

  it("set value as null if value is an empty string", () => {
    const fields: Array<DynamicFieldProps> = [buildFormField({ name: "field1" })];
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "user" }, value: "" },
    };

    const mutationData = getCreateMutationFromFormData(fields, formData);

    expect(mutationData).to.deep.equal({
      field1: { value: null },
    });
  });

  it("keeps items if value is 0", () => {
    const fields: Array<DynamicFieldProps> = [buildFormField({ name: "field1" })];
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "user" }, value: 0 },
    };

    const mutationData = getCreateMutationFromFormData(fields, formData);

    expect(mutationData).to.deep.equal({
      field1: { value: 0 },
    });
  });

  it("does not include field whose source is template", () => {
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

    const mutationData = getCreateMutationFromFormData(fields, formData, "template-id");

    expect(mutationData).to.deep.equal({
      object_template: { id: "template-id" },
      field2: { value: 0 },
    });
  });

  it("includes object_template in mutation data even with no template fields", () => {
    const fields: Array<DynamicFieldProps> = [buildFormField({ name: "field1" })];
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "user" }, value: "value1" },
    };

    const mutationData = getCreateMutationFromFormData(fields, formData, "template-id");

    expect(mutationData).to.deep.equal({
      field1: { value: "value1" },
      object_template: { id: "template-id" },
    });
  });

  describe("Attribute of kind list", () => {
    it("set correctly attribute of kind list when value is from schema", () => {
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

      const mutationData = getCreateMutationFromFormData(fields, formData);

      expect(mutationData).to.deep.equal({});
    });

    it("set correctly attribute of kind list when value is from user", () => {
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

      const mutationData = getCreateMutationFromFormData(fields, formData);

      expect(mutationData).to.deep.equal({
        listField: { value: ["item2", "item3"] },
      });
    });

    it("set correctly attribute field if value is from user and is an empty array", () => {
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

      const mutationData = getCreateMutationFromFormData(fields, formData);

      expect(mutationData).to.deep.equal({
        listField: { value: [] },
      });
    });
  });
});

describe("getCreateMutationFromFormDataOnly", () => {
  it("returns empty object if form data is empty", () => {
    const formData: Record<string, FormFieldValue> = {};

    const mutationData = getCreateMutationFromFormDataOnly(formData);

    expect(mutationData).to.deep.equal({});
  });

  it("handles user input values correctly", () => {
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "user" }, value: "value1" },
    };

    const mutationData = getCreateMutationFromFormDataOnly(formData);

    expect(mutationData).to.deep.equal({
      field1: { value: "value1" },
    });
  });

  it("handles empty string values as null", () => {
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "user" }, value: "" },
    };

    const mutationData = getCreateMutationFromFormDataOnly(formData);

    expect(mutationData).to.deep.equal({
      field1: { value: null },
    });
  });

  it("handles relationship values correctly", () => {
    const formData: Record<string, FormRelationshipValue> = {
      relationship1: {
        source: { type: "user" },
        value: [
          generateRelationshipNode({ id: "rel-id-1", display_label: "Rel 1" }),
          generateRelationshipNode({ id: "rel-id-2", display_label: "Rel 2" }),
        ],
      },
    };

    const mutationData = getCreateMutationFromFormDataOnly(formData);

    expect(mutationData).to.deep.equal({
      relationship1: [{ id: "rel-id-1" }, { id: "rel-id-2" }],
    });
  });

  it("handles pool values correctly", () => {
    const formData: Record<string, FormFieldValue> = {
      field1: {
        source: {
          type: "pool",
          label: "Pool 1",
          id: "pool-id",
          kind: "CoreIPAddressPool",
        },
        value: { from_pool: { id: "pool-id" } },
      },
    };

    const mutationData = getCreateMutationFromFormDataOnly(formData);

    expect(mutationData).to.deep.equal({
      field1: { from_pool: { id: "pool-id" } },
    });
  });

  it("excludes pool values from template", () => {
    const formData: Record<string, FormFieldValue> = {
      field1: {
        source: {
          type: "pool",
          fromTemplate: true,
          label: "Pool 1",
          id: "pool-id",
          kind: "CoreIPAddressPool",
        },
        value: { from_pool: { id: "pool-id" } },
      },
    };

    const mutationData = getCreateMutationFromFormDataOnly(formData, undefined, "template-id");

    expect(mutationData).to.deep.equal({
      object_template: { id: "template-id" },
    });
  });

  it("skips values that match current object values", () => {
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "user" }, value: "unchanged" },
      field2: { source: { type: "user" }, value: "changed" },
    };
    const currentObject = {
      field1: { value: "unchanged" },
      field2: { value: "old-value" },
    };

    const mutationData = getCreateMutationFromFormDataOnly(formData, currentObject);

    expect(mutationData).to.deep.equal({
      field2: { value: "changed" },
    });
  });

  it("handles relationship value correctly", () => {
    const formData: Record<string, FormFieldValue> = {
      field1: {
        source: {
          type: "user",
        },
        value: { id: "peer-id", display_label: "peer test", __typename: "PeerKind" },
      },
    };

    const mutationData = getCreateMutationFromFormDataOnly(formData);

    expect(mutationData).to.deep.equal({
      field1: { id: "peer-id" },
    });
  });
});
