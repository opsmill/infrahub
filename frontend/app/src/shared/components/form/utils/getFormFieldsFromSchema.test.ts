import { AuthContextType } from "@/entities/authentication/ui/useAuth";
import { currentBranchAtom } from "@/entities/branches/stores";
import { AttributeType } from "@/entities/nodes/getObjectItemDisplayValue";
import { ModelSchema } from "@/entities/schema/types";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { store } from "@/shared/stores";
import { describe, expect, it } from "vitest";
import {
  generateAttributeSchema,
  generateRelationshipSchema,
} from "../../../../../tests/fake/schema";

describe("getFormFieldsFromSchema", () => {
  it("returns no fields if schema has no attributes nor relationships", () => {
    // GIVEN
    const schema = {} as ModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(0);
  });

  it("returns no fields that are read only", () => {
    // GIVEN
    const schema = {
      attributes: [generateAttributeSchema({ read_only: true })],
      relationships: [generateRelationshipSchema({ read_only: true })],
    } as ModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(0);
  });

  it("returns fields ordered by order_weight", () => {
    // GIVEN
    const schema = {
      attributes: [
        generateAttributeSchema({ name: "third", order_weight: 3 }),
        generateAttributeSchema({ name: "first", order_weight: 1 }),
      ],
      relationships: [generateRelationshipSchema({ name: "second", order_weight: 2 })],
    } as ModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(3);
    expect(fields[0]!.name).to.equal("first");
    expect(fields[1]!.name).to.equal("second");
    expect(fields[2]!.name).to.equal("third");
  });

  it("should map a text attribute correctly", () => {
    // GIVEN
    const schema = {
      attributes: [generateAttributeSchema({ kind: "Text" })],
    } as ModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).toEqual({
      defaultValue: { source: { type: "schema" }, value: null },
      description: "description",
      disabled: false,
      name: "name",
      label: "Name",
      type: "Text",
      unique: false,
      rules: {
        required: false,
        validate: expect.any(Function),
      },
    });
  });

  it("should map a HashedPassword attribute correctly", () => {
    // GIVEN
    const schema = {
      attributes: [
        generateAttributeSchema({ label: "Password", name: "password", kind: "HashedPassword" }),
      ],
    } as ModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).toEqual({
      defaultValue: { source: { type: "schema" }, value: null },
      description: "description",
      disabled: false,
      name: "password",
      label: "Password",
      type: "HashedPassword",
      unique: false,
      rules: {
        required: false,
        validate: expect.any(Function),
      },
    });
  });

  it("should map a URL attribute correctly", () => {
    // GIVEN
    const schema = {
      attributes: [generateAttributeSchema({ label: "Url", name: "url", kind: "URL" })],
    } as ModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).toEqual({
      defaultValue: { source: { type: "schema" }, value: null },
      description: "description",
      disabled: false,
      name: "url",
      label: "Url",
      type: "URL",
      unique: false,
      rules: {
        required: false,
        validate: expect.any(Function),
      },
    });
  });

  it("should map a JSON attribute correctly", () => {
    // GIVEN
    const schema = {
      attributes: [
        generateAttributeSchema({ label: "Parameters", name: "parameters", kind: "JSON" }),
      ],
    } as ModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).toEqual({
      defaultValue: { source: { type: "schema" }, value: null },
      description: "description",
      disabled: false,
      name: "parameters",
      label: "Parameters",
      type: "JSON",
      unique: false,
      rules: {
        required: false,
        validate: expect.any(Function),
      },
    });
  });

  it("should map a Dropdown attribute correctly", () => {
    // GIVEN
    const schema = {
      attributes: [
        generateAttributeSchema({
          default_value: "address",
          label: "Member Type",
          name: "member_type",
          kind: "Dropdown",
          choices: [
            {
              id: null,
              state: "present",
              name: "prefix",
              description: "Prefix serves as container for other prefixes",
              color: "#ed6a5a",
              label: "Prefix",
            },
            {
              id: null,
              state: "present",
              name: "address",
              description: "Prefix serves as subnet for IP addresses",
              color: "#f4f1bb",
              label: "Address",
            },
          ],
        }),
      ],
    } as ModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).toEqual({
      defaultValue: { source: { type: "schema" }, value: "address" },
      description: "description",
      disabled: false,
      name: "member_type",
      label: "Member Type",
      type: "Dropdown",
      rules: {
        required: false,
        validate: expect.any(Function),
      },
      items: [
        {
          value: "prefix",
          label: "Prefix",
          description: "Prefix serves as container for other prefixes",
          color: "#ed6a5a",
        },
        {
          value: "address",
          label: "Address",
          description: "Prefix serves as subnet for IP addresses",
          color: "#f4f1bb",
        },
      ],
      field: schema.attributes?.[0],
      schema,
      unique: false,
    });
  });

  it("should map a enum attribute correctly", () => {
    // GIVEN
    const schema = {
      attributes: [
        generateAttributeSchema({
          kind: "Number",
          enum: [1, 2, 3],
          unique: false,
          optional: false,
        }),
      ],
    } as ModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).toEqual({
      defaultValue: { source: { type: "schema" }, value: null },
      description: "description",
      disabled: false,
      name: "name",
      label: "Name",
      type: "enum",
      rules: {
        required: true,
        validate: expect.any(Function),
      },
      items: [1, 2, 3],
      field: schema.attributes?.[0],
      schema,
      unique: false,
    });
  });

  it("should disable a protected field if the owner is not the current user", () => {
    // GIVEN
    const schema = {
      attributes: [generateAttributeSchema()],
    } as ModelSchema;

    const initialObject: { name: Partial<AttributeType> } = {
      name: {
        is_from_profile: false,
        is_protected: true,
        is_visible: true,
        owner: {
          id: "17dd42a7-d547-60af-3111-c51b4b2fc72e",
          display_label: "Architecture Team",
        },
        source: null,
        updated_at: "2024-07-15T09:32:01.363787+00:00",
        value: "test-value",
        __typename: "TextAttribute",
      },
    };

    const auth: AuthContextType = {
      accessToken: "abc",
      isAuthenticated: true,
      isLoading: false,
      data: {
        sub: "1",
      },
      login: async () => {},
      signOut: () => {},
      setToken: () => {},
      user: {
        id: "1",
      },
    };

    // WHEN
    const fields = getFormFieldsFromSchema({ schema, initialObject, auth });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).toEqual({
      defaultValue: { source: { type: "user" }, value: "test-value" },
      description: "description",
      disabled: true,
      name: "name",
      label: "Name",
      type: "Text",
      unique: false,
      rules: {
        required: false,
        validate: expect.any(Function),
      },
    });
  });

  it("should enable a protected field if the owner is the current user", () => {
    // GIVEN
    const schema = {
      attributes: [generateAttributeSchema()],
    } as ModelSchema;

    const initialObject: { name: AttributeType } = {
      name: {
        is_from_profile: false,
        is_protected: true,
        is_visible: true,
        owner: {
          id: "1",
          display_label: "Architecture Team",
        },
        source: null,
        updated_at: "2024-07-15T09:32:01.363787+00:00",
        value: "test-value",
        __typename: "TextAttribute",
      },
    };

    const auth: AuthContextType = {
      accessToken: "abc",
      isAuthenticated: true,
      isLoading: false,
      data: {
        sub: "1",
      },
      login: async () => {},
      signOut: () => {},
      setToken: () => {},
      user: {
        id: "1",
      },
    };

    // WHEN
    const fields = getFormFieldsFromSchema({ schema, initialObject, auth });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).toEqual({
      defaultValue: { source: { type: "user" }, value: "test-value" },
      description: "description",
      disabled: false,
      name: "name",
      label: "Name",
      type: "Text",
      unique: false,
      rules: {
        required: false,
        validate: expect.any(Function),
      },
    });
  });

  it("should disable a field if permission is DENY", () => {
    // GIVEN
    const schema = {
      attributes: [generateAttributeSchema()],
    } as ModelSchema;

    const initialObject: { name: Partial<AttributeType> } = {
      name: {
        is_from_profile: false,
        is_protected: true,
        is_visible: true,
        owner: {
          id: "17dd42a7-d547-60af-3111-c51b4b2fc72e",
          display_label: "Architecture Team",
        },
        permissions: {
          update_value: "DENY",
        },
        source: null,
        updated_at: "2024-07-15T09:32:01.363787+00:00",
        value: "test-value",
        __typename: "TextAttribute",
      },
    };

    // WHEN
    const fields = getFormFieldsFromSchema({ schema, initialObject });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).toEqual({
      defaultValue: { source: { type: "user" }, value: "test-value" },
      description: "description",
      disabled: true,
      name: "name",
      label: "Name",
      type: "Text",
      unique: false,
      rules: {
        required: false,
        validate: expect.any(Function),
      },
    });
  });

  it("should enable a field if permission is ALLOW_ALL", () => {
    // GIVEN
    const schema = {
      attributes: [generateAttributeSchema()],
    } as ModelSchema;

    const initialObject: { name: Partial<AttributeType> } = {
      name: {
        is_from_profile: false,
        is_protected: true,
        is_visible: true,
        owner: {
          id: "17dd42a7-d547-60af-3111-c51b4b2fc72e",
          display_label: "Architecture Team",
        },
        permissions: {
          update_value: "ALLOW",
        },
        source: null,
        updated_at: "2024-07-15T09:32:01.363787+00:00",
        value: "test-value",
        __typename: "TextAttribute",
      },
    };

    // WHEN
    const fields = getFormFieldsFromSchema({ schema, initialObject });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).toEqual({
      defaultValue: { source: { type: "user" }, value: "test-value" },
      description: "description",
      disabled: false,
      name: "name",
      label: "Name",
      type: "Text",
      unique: false,
      rules: {
        required: false,
        validate: expect.any(Function),
      },
    });
  });

  it("should enable a field if permission is ALLOW_DEFAULT and current branch is default", () => {
    // GIVEN
    const schema = {
      attributes: [generateAttributeSchema()],
    } as ModelSchema;

    const initialObject: { name: Partial<AttributeType> } = {
      name: {
        is_from_profile: false,
        is_protected: true,
        is_visible: true,
        owner: {
          id: "17dd42a7-d547-60af-3111-c51b4b2fc72e",
          display_label: "Architecture Team",
        },
        permissions: {
          update_value: "ALLOW_DEFAULT",
        },
        source: null,
        updated_at: "2024-07-15T09:32:01.363787+00:00",
        value: "test-value",
        __typename: "TextAttribute",
      },
    };

    store.set(currentBranchAtom, {
      id: "18007869-b812-f080-2d60-c51d9e906226",
      name: "mainnn",
      description: "Default Branch",
      origin_branch: "main",
      branched_from: "2024-10-21T12:44:12.365354Z",
      created_at: "2024-10-21T12:44:12.365371Z",
      sync_with_git: true,
      is_default: true,
      has_schema_changes: false,
      __typename: "Branch",
    });

    // WHEN
    const fields = getFormFieldsFromSchema({ schema, initialObject });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).toEqual({
      defaultValue: { source: { type: "user" }, value: "test-value" },
      description: "description",
      disabled: false,
      name: "name",
      label: "Name",
      type: "Text",
      unique: false,
      rules: {
        required: false,
        validate: expect.any(Function),
      },
    });
  });

  it("should disable a field if permission is ALLOW_DEFAULT and current branch is not default", () => {
    // GIVEN
    const schema = {
      attributes: [generateAttributeSchema()],
    } as ModelSchema;

    const initialObject: { name: Partial<AttributeType> } = {
      name: {
        is_from_profile: false,
        is_protected: true,
        is_visible: true,
        owner: {
          id: "17dd42a7-d547-60af-3111-c51b4b2fc72e",
          display_label: "Architecture Team",
        },
        permissions: {
          update_value: "ALLOW_DEFAULT",
        },
        source: null,
        updated_at: "2024-07-15T09:32:01.363787+00:00",
        value: "test-value",
        __typename: "TextAttribute",
      },
    };

    store.set(currentBranchAtom, {
      id: "18007869-b812-f080-2d60-c51d9e906226",
      name: "other",
      description: "other Branch",
      origin_branch: "main",
      branched_from: "2024-10-21T12:44:12.365354Z",
      created_at: "2024-10-21T12:44:12.365371Z",
      sync_with_git: true,
      is_default: false,
      has_schema_changes: false,
      __typename: "Branch",
    });

    // WHEN
    const fields = getFormFieldsFromSchema({ schema, initialObject });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).toEqual({
      defaultValue: { source: { type: "user" }, value: "test-value" },
      description: "description",
      disabled: true,
      name: "name",
      label: "Name",
      type: "Text",
      unique: false,
      rules: {
        required: false,
        validate: expect.any(Function),
      },
    });
  });

  it("should disable a field if permission is ALLOW_OTHER and current branch is default", () => {
    // GIVEN
    const schema = {
      attributes: [generateAttributeSchema()],
    } as ModelSchema;

    const initialObject: { name: Partial<AttributeType> } = {
      name: {
        is_from_profile: false,
        is_protected: true,
        is_visible: true,
        owner: {
          id: "17dd42a7-d547-60af-3111-c51b4b2fc72e",
          display_label: "Architecture Team",
        },
        permissions: {
          update_value: "ALLOW_OTHER",
        },
        source: null,
        updated_at: "2024-07-15T09:32:01.363787+00:00",
        value: "test-value",
        __typename: "TextAttribute",
      },
    };

    store.set(currentBranchAtom, {
      id: "18007869-b812-f080-2d60-c51d9e906226",
      name: "main",
      description: "Default Branch",
      origin_branch: "main",
      branched_from: "2024-10-21T12:44:12.365354Z",
      created_at: "2024-10-21T12:44:12.365371Z",
      sync_with_git: true,
      is_default: true,
      has_schema_changes: false,
      __typename: "Branch",
    });

    // WHEN
    const fields = getFormFieldsFromSchema({ schema, initialObject });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).toEqual({
      defaultValue: { source: { type: "user" }, value: "test-value" },
      description: "description",
      disabled: true,
      name: "name",
      label: "Name",
      type: "Text",
      unique: false,
      rules: {
        required: false,
        validate: expect.any(Function),
      },
    });
  });

  it("should disable a field if permission is ALLOW_OTHER and current branch is not default", () => {
    // GIVEN
    const schema = {
      attributes: [generateAttributeSchema()],
    } as ModelSchema;

    const initialObject: { name: Partial<AttributeType> } = {
      name: {
        is_from_profile: false,
        is_protected: true,
        is_visible: true,
        owner: {
          id: "17dd42a7-d547-60af-3111-c51b4b2fc72e",
          display_label: "Architecture Team",
        },
        permissions: {
          update_value: "ALLOW_OTHER",
        },
        source: null,
        updated_at: "2024-07-15T09:32:01.363787+00:00",
        value: "test-value",
        __typename: "TextAttribute",
      },
    };

    store.set(currentBranchAtom, {
      id: "18007869-b812-f080-2d60-c51d9e906226",
      name: "other",
      description: "other Branch",
      origin_branch: "main",
      branched_from: "2024-10-21T12:44:12.365354Z",
      created_at: "2024-10-21T12:44:12.365371Z",
      sync_with_git: true,
      is_default: false,
      has_schema_changes: false,
      __typename: "Branch",
    });

    // WHEN
    const fields = getFormFieldsFromSchema({ schema, initialObject });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).toEqual({
      defaultValue: { source: { type: "user" }, value: "test-value" },
      description: "description",
      disabled: false,
      name: "name",
      label: "Name",
      type: "Text",
      unique: false,
      rules: {
        required: false,
        validate: expect.any(Function),
      },
    });
  });

  it("removes unique fields when isBulkUpdate is true", () => {
    // GIVEN
    const schema = {
      attributes: [
        generateAttributeSchema({ name: "unique_field", unique: true }),
        generateAttributeSchema({ name: "non_unique_field", unique: false }),
      ],
    } as ModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema, isBulkUpdate: true });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]?.name).to.equal("non_unique_field");
  });

  it("removes required validation when isBulkUpdate is true", () => {
    // GIVEN
    const schema = {
      attributes: [generateAttributeSchema({ name: "required_field", optional: false })],
      relationships: [generateRelationshipSchema({ name: "required_rel", optional: false })],
    } as ModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema, isBulkUpdate: true });

    // THEN
    expect(fields[0]?.rules?.required).to.equal(false);
    expect(fields[1]?.rules?.required).to.equal(false);
  });
});
