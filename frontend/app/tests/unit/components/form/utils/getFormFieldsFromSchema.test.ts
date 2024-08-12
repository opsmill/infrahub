import { describe, expect, it } from "vitest";
import { getFormFieldsFromSchema } from "@/components/form/utils/getFormFieldsFromSchema";
import { IModelSchema } from "@/state/atoms/schema.atom";
import { AuthContextType } from "@/hooks/useAuth";
import { AttributeType } from "@/utils/getObjectItemDisplayValue";
import { components } from "@/infraops";

export const buildAttributeSchema = (
  override?: Partial<components["schemas"]["AttributeSchema-Output"]>
): components["schemas"]["AttributeSchema-Output"] => ({
  id: "17d67b92-f0b9-cf97-3001-c51824a9c7dc",
  state: "present",
  name: "field1",
  kind: "Text",
  enum: null,
  choices: null,
  regex: null,
  max_length: null,
  min_length: null,
  label: "Field 1",
  description: null,
  read_only: false,
  unique: false,
  optional: true,
  branch: "aware",
  order_weight: 1000,
  default_value: null,
  inherited: false,
  allow_override: "any",
  ...override,
});

export const buildRelationshipSchema = (
  override?: Partial<components["schemas"]["RelationshipSchema-Output"]>
): components["schemas"]["RelationshipSchema-Output"] => ({
  id: "17e2718c-73ed-3ffe-3402-c515757ff94f",
  state: "present",
  name: "tagone",
  peer: "BuiltinTag",
  kind: "Attribute",
  label: "Tagone",
  description: "relationship many input for testing and development",
  identifier: "builtintag__testallinone",
  cardinality: "many",
  min_count: 0,
  max_count: 0,
  order_weight: 24000,
  optional: true,
  branch: "aware",
  inherited: false,
  direction: "bidirectional",
  hierarchical: null,
  on_delete: "no-action",
  allow_override: "any",
  read_only: false,
  ...override,
});

describe("getFormFieldsFromSchema", () => {
  it("returns no fields if schema has no attributes nor relationships", () => {
    // GIVEN
    const schema = {} as IModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(0);
  });

  it("returns no fields that are read only", () => {
    // GIVEN
    const schema = {
      attributes: [buildAttributeSchema({ read_only: true })],
      relationships: [buildRelationshipSchema({ read_only: true })],
    } as IModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(0);
  });

  it("returns fields ordered by order_weight", () => {
    // GIVEN
    const schema = {
      attributes: [
        buildAttributeSchema({ name: "third", order_weight: 3 }),
        buildAttributeSchema({ name: "first", order_weight: 1 }),
      ],
      relationships: [buildRelationshipSchema({ name: "second", order_weight: 2 })],
    } as IModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(3);
    expect(fields[0].name).to.equal("first");
    expect(fields[1].name).to.equal("second");
    expect(fields[2].name).to.equal("third");
  });

  it("should map a text attribute correctly", () => {
    // GIVEN
    const schema = {
      attributes: [buildAttributeSchema({ kind: "Text" })],
    } as IModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).toEqual({
      defaultValue: { source: { type: "schema" }, value: null },
      description: undefined,
      disabled: false,
      name: "field1",
      label: "Field 1",
      type: "Text",
      unique: false,
      rules: {
        required: false,
        validate: {
          required: expect.any(Function),
        },
      },
    });
  });

  it("should map a HashedPassword attribute correctly", () => {
    // GIVEN
    const schema = {
      attributes: [
        buildAttributeSchema({ label: "Password", name: "password", kind: "HashedPassword" }),
      ],
    } as IModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).toEqual({
      defaultValue: { source: { type: "schema" }, value: null },
      description: undefined,
      disabled: false,
      name: "password",
      label: "Password",
      type: "HashedPassword",
      unique: false,
      rules: {
        required: false,
        validate: {
          required: expect.any(Function),
        },
      },
    });
  });

  it("should map a URL attribute correctly", () => {
    // GIVEN
    const schema = {
      attributes: [buildAttributeSchema({ label: "Url", name: "url", kind: "URL" })],
    } as IModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).toEqual({
      defaultValue: { source: { type: "schema" }, value: null },
      description: undefined,
      disabled: false,
      name: "url",
      label: "Url",
      type: "URL",
      unique: false,
      rules: {
        required: false,
        validate: {
          required: expect.any(Function),
        },
      },
    });
  });

  it("should map a JSON attribute correctly", () => {
    // GIVEN
    const schema = {
      attributes: [buildAttributeSchema({ label: "Parameters", name: "parameters", kind: "JSON" })],
    } as IModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).toEqual({
      defaultValue: { source: { type: "schema" }, value: null },
      description: undefined,
      disabled: false,
      name: "parameters",
      label: "Parameters",
      type: "JSON",
      unique: false,
      rules: {
        required: false,
        validate: {
          required: expect.any(Function),
        },
      },
    });
  });

  it("should map a Dropdown attribute correctly", () => {
    // GIVEN
    const schema = {
      attributes: [
        buildAttributeSchema({
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
    } as IModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).toEqual({
      defaultValue: { source: { type: "schema" }, value: "address" },
      description: undefined,
      disabled: false,
      name: "member_type",
      label: "Member Type",
      type: "Dropdown",
      rules: {
        required: false,
        validate: {
          required: expect.any(Function),
        },
      },
      items: [
        {
          id: "prefix",
          description: "Prefix serves as container for other prefixes",
          color: "#ed6a5a",
          name: "Prefix",
        },
        {
          id: "address",
          description: "Prefix serves as subnet for IP addresses",
          color: "#f4f1bb",
          name: "Address",
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
        buildAttributeSchema({
          kind: "Number",
          enum: [1, 2, 3],
          unique: false,
          optional: false,
        }),
      ],
    } as IModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).toEqual({
      defaultValue: { source: { type: "schema" }, value: null },
      description: undefined,
      disabled: false,
      name: "field1",
      label: "Field 1",
      type: "enum",
      rules: {
        required: true,
        validate: {
          required: expect.any(Function),
        },
      },
      items: [
        { id: 1, name: 1 },
        { id: 2, name: 2 },
        { id: 3, name: 3 },
      ],
      field: schema.attributes?.[0],
      schema,
      unique: false,
    });
  });

  it("should disable a protected field if the owner is not the current user", () => {
    // GIVEN
    const schema = {
      attributes: [buildAttributeSchema()],
    } as IModelSchema;

    const initialObject: { field1: Partial<AttributeType> } = {
      field1: {
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
      signIn: async () => {},
      signOut: () => {},
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
      description: undefined,
      disabled: true,
      name: "field1",
      label: "Field 1",
      type: "Text",
      unique: false,
      rules: {
        required: false,
        validate: {
          required: expect.any(Function),
        },
      },
    });
  });

  it("should enable a protected field if the owner is the current user", () => {
    // GIVEN
    const schema = {
      attributes: [buildAttributeSchema()],
    } as IModelSchema;

    const initialObject: { field1: AttributeType } = {
      field1: {
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
      signIn: async () => {},
      signOut: () => {},
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
      description: undefined,
      disabled: false,
      name: "field1",
      label: "Field 1",
      type: "Text",
      unique: false,
      rules: {
        required: false,
        validate: {
          required: expect.any(Function),
        },
      },
    });
  });
});
