import { FormRelationshipValue } from "@/shared/components/form/type";
import { describe, expect, it } from "vitest";
import { generateRelationshipNode } from "../../../../../tests/fake/node";
import { isMaxCount, isMinCount } from "./validation";

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

describe("isMaxCount", () => {
  it("should return true when value is null", () => {
    // GIVEN
    const maxCount = 2;
    const fieldValue: FormRelationshipValue = {
      source: null,
      value: null,
    };
    const validator = isMaxCount(maxCount);

    // WHEN
    const result = validator(fieldValue);

    // THEN
    expect(result).toBe(true);
  });

  it("should return true when value is not an array", () => {
    // GIVEN
    const maxCount = 2;
    const fieldValue: FormRelationshipValue = {
      source: { type: "user" },
      value: generateRelationshipNode(),
    };
    const validator = isMaxCount(maxCount);

    // WHEN
    const result = validator(fieldValue);

    // THEN
    expect(result).toBe(true);
  });

  it("should return true when array length is less than maxCount", () => {
    // GIVEN
    const maxCount = 2;
    const fieldValue: FormRelationshipValue = {
      source: { type: "user" },
      value: [generateRelationshipNode()],
    };
    const validator = isMaxCount(maxCount);

    // WHEN
    const result = validator(fieldValue);

    // THEN
    expect(result).toBe(true);
  });

  it("should return true when array length equals maxCount", () => {
    // GIVEN
    const maxCount = 2;
    const fieldValue: FormRelationshipValue = {
      source: { type: "user" },
      value: [generateRelationshipNode(), generateRelationshipNode()],
    };
    const validator = isMaxCount(maxCount);

    // WHEN
    const result = validator(fieldValue);

    // THEN
    expect(result).toBe(true);
  });

  it("should return error message when array length exceeds maxCount", () => {
    // GIVEN
    const maxCount = 2;
    const fieldValue: FormRelationshipValue = {
      source: { type: "user" },
      value: [generateRelationshipNode(), generateRelationshipNode(), generateRelationshipNode()],
    };
    const validator = isMaxCount(maxCount);

    // WHEN
    const result = validator(fieldValue);

    // THEN
    expect(result).toBe(`Maximum ${maxCount} allowed`);
  });

  it("should return true when maxCount is 0 (infinity)", () => {
    // GIVEN
    const maxCount = 0;
    const fieldValue: FormRelationshipValue = {
      source: { type: "user" },
      value: [
        generateRelationshipNode(),
        generateRelationshipNode(),
        generateRelationshipNode(),
        generateRelationshipNode(),
      ],
    };
    const validator = isMaxCount(maxCount);

    // WHEN
    const result = validator(fieldValue);

    // THEN
    expect(result).toBe(true);
  });
});
