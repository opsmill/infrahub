import { describe, expect, it } from "vitest";

import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { store } from "@/shared/stores";

import type { AuthContextType } from "@/entities/authentication/ui/useAuth";
import { currentBranchAtom } from "@/entities/branches/stores";
import type { AttributeType } from "@/entities/nodes/getObjectItemDisplayValue";
import type { ModelSchema } from "@/entities/schema/types";

import {
  generateAttributeSchema,
  generateRelationshipSchema,
} from "../../../../../tests/fake/schema";
import {
  FROM_RESOURCE_POOL_SUFFIX,
  RELATIONSHIP_BULK_ADD_PREFIX,
  RELATIONSHIP_BULK_REMOVE_PREFIX,
} from "../constants";

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
    const attribute = generateAttributeSchema({ kind: "Text" });

    const schema = {
      attributes: [attribute],
    } as ModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).toEqual({
      defaultValue: { source: { type: "schema" }, value: null },
      isBulkUpdate: false,
      attribute,
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
    const attribute = generateAttributeSchema({
      label: "Password",
      name: "password",
      kind: "HashedPassword",
    });

    const schema = {
      attributes: [attribute],
    } as ModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).toEqual({
      defaultValue: { source: { type: "schema" }, value: null },
      isBulkUpdate: false,
      attribute,
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
    const attribute = generateAttributeSchema({ label: "Url", name: "url", kind: "URL" });

    const schema = {
      attributes: [attribute],
    } as ModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).toEqual({
      defaultValue: { source: { type: "schema" }, value: null },
      isBulkUpdate: false,
      attribute,
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
    const attribute = generateAttributeSchema({
      label: "Parameters",
      name: "parameters",
      kind: "JSON",
    });

    const schema = {
      attributes: [attribute],
    } as ModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).toEqual({
      defaultValue: { source: { type: "schema" }, value: null },
      isBulkUpdate: false,
      attribute,
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
    const attribute = generateAttributeSchema({
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
    });

    const schema = {
      attributes: [attribute],
    } as ModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).toEqual({
      defaultValue: { source: { type: "schema" }, value: "address" },
      isBulkUpdate: false,
      attribute,
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
      schema,
      unique: false,
    });
  });

  it("should map a enum attribute correctly", () => {
    // GIVEN
    const attribute = generateAttributeSchema({
      kind: "Number",
      enum: [1, 2, 3],
      unique: false,
      optional: false,
    });

    const schema = {
      attributes: [attribute],
    } as ModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).toEqual({
      defaultValue: { source: { type: "schema" }, value: null },
      isBulkUpdate: false,
      attribute,
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
      schema,
      unique: false,
    });
  });

  it("should disable a protected field if the owner is not the current user", () => {
    // GIVEN
    const attribute = generateAttributeSchema();

    const schema = {
      attributes: [attribute],
    } as ModelSchema;

    const initialObject: { name: Partial<AttributeType> } = {
      name: {
        is_from_profile: false,
        is_protected: true,
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
      data: {
        sub: "1",
      },
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
      isBulkUpdate: false,
      attribute,
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
    const attribute = generateAttributeSchema();

    const schema = {
      attributes: [attribute],
    } as ModelSchema;

    const initialObject: { name: AttributeType } = {
      name: {
        is_from_profile: false,
        is_protected: true,
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
      data: {
        sub: "1",
      },
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
      isBulkUpdate: false,
      attribute,
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
    const attribute = generateAttributeSchema();

    const schema = {
      attributes: [attribute],
    } as ModelSchema;

    const initialObject: { name: Partial<AttributeType> } = {
      name: {
        is_from_profile: false,
        is_protected: true,
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
      isBulkUpdate: false,
      attribute,
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
    const attribute = generateAttributeSchema();

    const schema = {
      attributes: [attribute],
    } as ModelSchema;

    const initialObject: { name: Partial<AttributeType> } = {
      name: {
        is_from_profile: false,
        is_protected: true,
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
      isBulkUpdate: false,
      attribute,
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
    const attribute = generateAttributeSchema();

    const schema = {
      attributes: [attribute],
    } as ModelSchema;

    const initialObject: { name: Partial<AttributeType> } = {
      name: {
        is_from_profile: false,
        is_protected: true,
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
      status: "OPEN",
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
      isBulkUpdate: false,
      attribute,
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
    const attribute = generateAttributeSchema();

    const schema = {
      attributes: [attribute],
    } as ModelSchema;

    const initialObject: { name: Partial<AttributeType> } = {
      name: {
        is_from_profile: false,
        is_protected: true,
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
      status: "OPEN",
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
      isBulkUpdate: false,
      attribute,
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
    const attribute = generateAttributeSchema();

    const schema = {
      attributes: [attribute],
    } as ModelSchema;

    const initialObject: { name: Partial<AttributeType> } = {
      name: {
        is_from_profile: false,
        is_protected: true,
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
      status: "OPEN",
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
      isBulkUpdate: false,
      attribute,
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
    const attribute = generateAttributeSchema();

    const schema = {
      attributes: [attribute],
    } as ModelSchema;

    const initialObject: { name: Partial<AttributeType> } = {
      name: {
        is_from_profile: false,
        is_protected: true,
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
      status: "OPEN",
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
      isBulkUpdate: false,
      attribute,
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
    const uniqueAttribute = generateAttributeSchema({ name: "unique_field", unique: true });
    const notUniqueAttribute = generateAttributeSchema({ name: "non_unique_field", unique: false });

    const schema = {
      attributes: [uniqueAttribute, notUniqueAttribute],
    } as ModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema, isBulkUpdate: true });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]?.name).to.equal("non_unique_field");
  });

  it("removes required validation when isBulkUpdate is true", () => {
    // GIVEN
    const attribute = generateAttributeSchema({ name: "required_field", optional: false });
    const relationship = generateRelationshipSchema({ name: "required_rel", optional: false });

    const schema = {
      attributes: [attribute],
      relationships: [relationship],
    } as ModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema, isBulkUpdate: true });

    // THEN
    expect(fields[0]?.rules?.required).to.equal(false);
    expect(fields[1]?.rules?.required).to.equal(false);
  });

  it("should display add and remvoe fields for relationship of cardinality many in bulk edit", () => {
    const relationshipMany = generateRelationshipSchema({
      name: "cardinality_many",
      cardinality: "many",
      order_weight: 1,
    });
    const relationshipOne = generateRelationshipSchema({
      name: "cardinality_one",
      cardinality: "one",
      order_weight: 2,
    });

    const schema = {
      relationships: [relationshipMany, relationshipOne],
    } as ModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema, isBulkUpdate: true });

    // THEN
    expect(fields[0]?.name).to.equal(`${RELATIONSHIP_BULK_ADD_PREFIX}cardinality_many`);
    expect(fields[0]?.type).to.equal("relationship-add");
    expect(fields[1]?.name).to.equal(`${RELATIONSHIP_BULK_REMOVE_PREFIX}cardinality_many`);
    expect(fields[1]?.type).to.equal("relationship-remove");
    expect(fields[2]?.name).to.equal("cardinality_one");
  });

  it("should exclude relationships ending with _from_resource_pool", () => {
    // GIVEN
    const mainRelationship = generateRelationshipSchema({
      name: "ip_address",
      order_weight: 1,
    });
    const poolRelationship = generateRelationshipSchema({
      name: `ip_address${FROM_RESOURCE_POOL_SUFFIX}`,
      order_weight: 2,
    });

    const schema = {
      relationships: [mainRelationship, poolRelationship],
    } as ModelSchema;

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]?.name).to.equal("ip_address");
  });
});
