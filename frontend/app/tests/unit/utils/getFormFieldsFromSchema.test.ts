import { describe, expect, it } from "vitest";
import { getFormFieldsFromSchema } from "../../../src/components/form/utils";
import { IModelSchema } from "../../../src/state/atoms/schema.atom";

describe("getFormFieldsFromSchema", () => {
  it("returns no fields if schema has no attributes nor relationships", () => {
    // GIVEN
    const schema = {};

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(0);
  });

  it("should map a text attribute correctly", () => {
    // GIVEN
    const schema: Pick<IModelSchema, "attributes" | "relationships"> = {
      attributes: [
        {
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
          default_value: null,
          inherited: false,
          allow_override: "any",
        },
      ],
    };

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).to.deep.equal({
      defaultValue: null,
      description: undefined,
      disabled: false,
      name: "name",
      label: "Name",
      type: "Text",
      unique: true,
      rules: {
        required: true,
      },
    });
  });

  it("should map a HashedPassword attribute correctly", () => {
    // GIVEN
    const schema: Pick<IModelSchema, "attributes" | "relationships"> = {
      attributes: [
        {
          id: "17d67b92-f48c-d385-300d-c518c0f3f7f2",
          state: "present",
          name: "password",
          kind: "HashedPassword",
          enum: null,
          choices: null,
          regex: null,
          max_length: null,
          min_length: null,
          label: "Password",
          description: null,
          read_only: false,
          unique: false,
          optional: false,
          branch: "agnostic",
          order_weight: 2000,
          default_value: null,
          inherited: false,
          allow_override: "any",
        },
      ],
    };

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).to.deep.equal({
      defaultValue: null,
      description: undefined,
      disabled: false,
      name: "password",
      label: "Password",
      type: "HashedPassword",
      unique: false,
      rules: {
        required: true,
      },
    });
  });

  it("should map a URL attribute correctly", () => {
    // GIVEN
    const schema: Pick<IModelSchema, "attributes" | "relationships"> = {
      attributes: [
        {
          id: "17d67b93-db48-7360-3002-c514e72d4910",
          state: "present",
          name: "url",
          kind: "URL",
          enum: null,
          choices: null,
          regex: null,
          max_length: null,
          min_length: null,
          label: "Url",
          description: null,
          read_only: false,
          unique: false,
          optional: true,
          branch: "agnostic",
          order_weight: 3000,
          default_value: null,
          inherited: true,
          allow_override: "any",
        },
      ],
    };

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).to.deep.equal({
      defaultValue: null,
      description: undefined,
      disabled: false,
      name: "url",
      label: "Url",
      type: "URL",
      unique: false,
      rules: {
        required: false,
      },
    });
  });

  it("should map a JSON attribute correctly", () => {
    // GIVEN
    const schema: Pick<IModelSchema, "attributes" | "relationships"> = {
      attributes: [
        {
          id: "17d67b93-cdfa-3f6b-3000-c510e05c9186",
          state: "present",
          name: "parameters",
          kind: "JSON",
          enum: null,
          choices: null,
          regex: null,
          max_length: null,
          min_length: null,
          label: "Parameters",
          description: null,
          read_only: false,
          unique: false,
          optional: false,
          branch: "aware",
          order_weight: 3000,
          default_value: null,
          inherited: false,
          allow_override: "any",
        },
      ],
    };

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).to.deep.equal({
      defaultValue: null,
      description: undefined,
      disabled: false,
      name: "parameters",
      label: "Parameters",
      type: "JSON",
      unique: false,
      rules: {
        required: true,
      },
    });
  });

  it("should map a Dropdown attribute correctly", () => {
    // GIVEN
    const schema: Pick<IModelSchema, "attributes" | "relationships"> = {
      attributes: [
        {
          id: "17d67be6-24a2-4da6-3003-c5130e3a579e",
          state: "present",
          name: "member_type",
          kind: "Dropdown",
          enum: null,
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
          regex: null,
          max_length: null,
          min_length: null,
          label: "Member Type",
          description: null,
          read_only: false,
          unique: false,
          optional: true,
          branch: "aware",
          order_weight: 3000,
          default_value: "address",
          inherited: true,
          allow_override: "any",
        },
      ],
    };

    // WHEN
    const fields = getFormFieldsFromSchema({ schema });

    // THEN
    expect(fields.length).to.equal(1);
    expect(fields[0]).to.deep.equal({
      defaultValue: "address",
      description: undefined,
      disabled: false,
      name: "member_type",
      label: "Member Type",
      type: "Dropdown",
      rules: {
        required: false,
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
      unique: false,
    });
  });
});
