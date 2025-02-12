import { FormRelationshipValue } from "@/shared/components/form/type";
import { describe, expect, it } from "vitest";
import { generateRelationshipNode } from "../../../../../tests/fake/node";
import { isMinCount } from "./validation";

describe("isMinCount", () => {
  it("should return true when minCount is 0", () => {
    // GIVEN
    const minCount = 0;
    const fieldValue: FormRelationshipValue = {
      source: { type: "user" },
      value: [],
    };
    const validator = isMinCount(minCount);

    // WHEN
    const result = validator(fieldValue);

    // THEN
    expect(result).toBe(true);
  });

  it("should return true when array length meets minimum count", () => {
    // GIVEN
    const minCount = 2;
    const fieldValue: FormRelationshipValue = {
      source: { type: "user" },
      value: [generateRelationshipNode(), generateRelationshipNode()],
    };
    const validator = isMinCount(minCount);

    // WHEN
    const result = validator(fieldValue);

    // THEN
    expect(result).toBe(true);
  });

  it("should return error message when array length is below minimum count", () => {
    // GIVEN
    const minCount = 3;
    const fieldValue: FormRelationshipValue = {
      source: { type: "user" },
      value: [],
    };
    const validator = isMinCount(minCount);

    // WHEN
    const result = validator(fieldValue);

    // THEN
    expect(result).toBe(`Minimum ${minCount} required`);
  });

  it("should return true when value is not an array", () => {
    // GIVEN
    const minCount = 2;
    const fieldValue: FormRelationshipValue = {
      source: { type: "user" },
      value: generateRelationshipNode(),
    };
    const validator = isMinCount(minCount);

    // WHEN
    const result = validator(fieldValue);

    // THEN
    expect(result).toBe(true);
  });

  it("should return true when value is null and minCount is 0", () => {
    // GIVEN
    const minCount = 0;
    const fieldValue: FormRelationshipValue = {
      source: null,
      value: null,
    };
    const validator = isMinCount(minCount);

    // WHEN
    const result = validator(fieldValue);

    // THEN
    expect(result).toBe(true);
  });

  it("should return error message when value is null and minCount is greater than 0", () => {
    // GIVEN
    const minCount = 1;
    const fieldValue: FormRelationshipValue = {
      source: null,
      value: null,
    };
    const validator = isMinCount(minCount);

    // WHEN
    const result = validator(fieldValue);

    // THEN
    expect(result).toBe(`Minimum ${minCount} required`);
  });
});
