import { describe, expect, it } from "vitest";

import { IP_ADDRESS_GENERIC, IP_PREFIX_GENERIC } from "@/entities/ipam/constants";
import { IP_ADDRESS_POOL, IP_PREFIX_POOL } from "@/entities/resource-manager/constants";
import type { ModelSchema } from "@/entities/schema/types";

import { generateGenericSchema, generateNodeSchema } from "../../../../tests/fake/schema";
import { getPoolKindFromSchema } from "./get-pool-kind-from-schema";

describe("getPoolKindFromSchema", () => {
  const baseNodeSchema = generateNodeSchema();
  const baseGenericSchema = generateGenericSchema();

  it("should return IP_ADDRESS_POOL when schema is IP_ADDRESS_GENERIC", () => {
    // GIVEN
    const schema: ModelSchema = {
      ...baseGenericSchema,
      kind: IP_ADDRESS_GENERIC,
    };

    // WHEN
    const result = getPoolKindFromSchema(schema);

    // THEN
    expect(result).toBe(IP_ADDRESS_POOL);
  });

  it("should return IP_PREFIX_POOL when schema is IP_PREFIX_GENERIC", () => {
    // GIVEN
    const schema: ModelSchema = {
      ...baseGenericSchema,
      kind: IP_PREFIX_GENERIC,
    };

    // WHEN
    const result = getPoolKindFromSchema(schema);

    // THEN
    expect(result).toBe(IP_PREFIX_POOL);
  });

  it("should return null when schema is generic but kind doesn't match any pool type", () => {
    // GIVEN
    const schema: ModelSchema = {
      ...baseGenericSchema,
      kind: "UnknownGeneric",
    };

    // WHEN
    const result = getPoolKindFromSchema(schema);

    // THEN
    expect(result).toBeNull();
  });

  it("should return pool kind when schema inherits from a prefix pool type", () => {
    // GIVEN
    const schema: ModelSchema = {
      ...baseNodeSchema,
      inherit_from: [IP_PREFIX_GENERIC, "SomeOtherType"],
    };

    // WHEN
    const result = getPoolKindFromSchema(schema);

    // THEN
    expect(result).toBe(IP_PREFIX_POOL);
  });

  it("should return pool kind when schema inherits from an address pool type", () => {
    // GIVEN
    const schema: ModelSchema = {
      ...baseNodeSchema,
      inherit_from: [IP_ADDRESS_GENERIC, "SomeOtherType"],
    };

    // WHEN
    const result = getPoolKindFromSchema(schema);

    // THEN
    expect(result).toBe(IP_ADDRESS_POOL);
  });

  it("should return null when schema has no inheritance", () => {
    // GIVEN
    const schema: ModelSchema = {
      ...baseNodeSchema,
      inherit_from: undefined,
    };

    // WHEN
    const result = getPoolKindFromSchema(schema);

    // THEN
    expect(result).toBeNull();
  });

  it("should return null when schema inherits from non-pool types", () => {
    // GIVEN
    const schema: ModelSchema = {
      ...baseNodeSchema,
      inherit_from: ["Type1", "Type2"],
    };

    // WHEN
    const result = getPoolKindFromSchema(schema);

    // THEN
    expect(result).toBeNull();
  });
});
