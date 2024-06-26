import { describe, expect, it } from "vitest";
import { GetObjectDefaultValue, getObjectDefaultValue } from "@/components/form/utils";

describe("getObjectDefaultValue", () => {
  it("returns null when no default value are found", () => {
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
      default_value: null,
      inherited: false,
      allow_override: "any",
    } satisfies GetObjectDefaultValue["fieldSchema"];

    // WHEN
    const defaultValue = getObjectDefaultValue({ fieldSchema });

    // THEN
    expect(defaultValue).to.equal(null);
  });

  it("returns null if field is an relationship and no object field value is provided", () => {
    // GIVEN
    const fieldSchema = {
      id: "17d9d595-b1f1-52f5-3c03-c51e6c12d685",
      state: "present",
      name: "tag",
      peer: "BuiltinTag",
      kind: "Attribute",
      label: "Tag",
      description: "relationship many for testing and development",
      identifier: "builtintag__testallinone",
      cardinality: "many",
      min_count: 0,
      max_count: 0,
      order_weight: 25000,
      optional: true,
      branch: "aware",
      inherited: false,
      direction: "bidirectional",
      hierarchical: null,
      filters: [],
      on_delete: "no-action",
      allow_override: "any",
      read_only: false,
    } satisfies GetObjectDefaultValue["fieldSchema"];

    // WHEN
    const defaultValue = getObjectDefaultValue({ fieldSchema });

    // THEN
    expect(defaultValue).to.equal(null);
  });

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
    } satisfies GetObjectDefaultValue["fieldSchema"];

    // WHEN
    const defaultValue = getObjectDefaultValue({ fieldSchema });

    // THEN
    expect(defaultValue).to.equal("test-value-form-schema");
  });

  it("returns schema's default value when it exists, and profile default value is null and current object field value is not provided", () => {
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
    } satisfies GetObjectDefaultValue["fieldSchema"];

    const profile = {
      name: {
        value: null,
      },
    };

    // WHEN
    const defaultValue = getObjectDefaultValue({ fieldSchema, profile });

    // THEN
    expect(defaultValue).to.equal("test-value-form-schema");
  });

  it("returns schema's default value when it exists, and profile default value is null and current object field value is null", () => {
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
    } satisfies GetObjectDefaultValue["fieldSchema"];

    const profile = {
      name: {
        value: null,
      },
    };

    const initialObject = {
      name: {
        value: null,
      },
    };

    // WHEN
    const defaultValue = getObjectDefaultValue({ fieldSchema, initialObject, profile });

    // THEN
    expect(defaultValue).to.equal("test-value-form-schema");
  });

  it("returns profile's default value when it exists, schema's default value is null and current object field value is null", () => {
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
      default_value: null,
      inherited: false,
      allow_override: "any",
    } satisfies GetObjectDefaultValue["fieldSchema"];

    const profile = {
      name: {
        value: "test-value-form-profile",
      },
    };

    const initialObject = {
      name: {
        value: null,
      },
    };

    // WHEN
    const defaultValue = getObjectDefaultValue({ fieldSchema, initialObject, profile });

    // THEN
    expect(defaultValue).to.equal("test-value-form-profile");
  });

  it("returns profile's default value when it exists, schema's default value exists and current object field value is null", () => {
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
    } satisfies GetObjectDefaultValue["fieldSchema"];

    const profile = {
      name: {
        value: "test-value-form-profile",
      },
    };

    const initialObject = {
      name: {
        value: null,
      },
    };

    // WHEN
    const defaultValue = getObjectDefaultValue({ fieldSchema, initialObject, profile });

    // THEN
    expect(defaultValue).to.equal("test-value-form-profile");
  });

  it("returns current object field's value when it exists", () => {
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
      default_value: null,
      inherited: false,
      allow_override: "any",
    } satisfies GetObjectDefaultValue["fieldSchema"];

    const profile = {
      name: {
        value: "test-value-form-profile",
      },
    };

    const initialObject = {
      name: {
        value: "data-from-current-object",
      },
    };

    // WHEN
    const defaultValue = getObjectDefaultValue({ fieldSchema, initialObject, profile });

    // THEN
    expect(defaultValue).to.equal("data-from-current-object");
  });
});
