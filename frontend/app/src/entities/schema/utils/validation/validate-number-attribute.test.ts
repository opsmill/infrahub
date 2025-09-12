import { describe, expect, it } from "vitest";

import { validateNumberAttribute } from "./validate-number-attribute";

describe("validateNumberAttribute", () => {
  it("should return success false with 'Required' error when value is null and isRequired is true", () => {
    // GIVEN
    const params = { isRequired: true };
    const value = null;

    // WHEN
    const result = validateNumberAttribute(params, value);

    // THEN
    expect(result).toEqual({
      success: false,
      error: "Required",
    });
  });

  it("should return success false with 'Required' error when value is undefined and isRequired is true", () => {
    // GIVEN
    const params = { isRequired: true };
    const value = undefined;

    // WHEN
    const result = validateNumberAttribute(params, value);

    // THEN
    expect(result).toEqual({
      success: false,
      error: "Required",
    });
  });

  it("should return success true with 0 when value is null and isRequired is false", () => {
    // GIVEN
    const params = { isRequired: false };
    const value = null;

    // WHEN
    const result = validateNumberAttribute(params, value);

    // THEN
    expect(result).toEqual({
      success: true,
      data: 0,
    });
  });

  it("should return success false when value is NaN", () => {
    // GIVEN
    const params = {};
    const value = NaN;

    // WHEN
    const result = validateNumberAttribute(params, value);

    // THEN
    expect(result).toEqual({
      success: false,
      error: "Value must be a number",
    });
  });

  it("should return success false when value is less than min", () => {
    // GIVEN
    const params = { min: 5 };
    const value = 3;

    // WHEN
    const result = validateNumberAttribute(params, value);

    // THEN
    expect(result).toEqual({
      success: false,
      error: "Value must be at least 5",
    });
  });

  it("should return success true when value equals min", () => {
    // GIVEN
    const params = { min: 5 };
    const value = 5;

    // WHEN
    const result = validateNumberAttribute(params, value);

    // THEN
    expect(result).toEqual({
      success: true,
      data: 5,
    });
  });

  it("should return success true when value is greater than min", () => {
    // GIVEN
    const params = { min: 5 };
    const value = 7;

    // WHEN
    const result = validateNumberAttribute(params, value);

    // THEN
    expect(result).toEqual({
      success: true,
      data: 7,
    });
  });

  it("should ignore min when it is null", () => {
    // GIVEN
    const params = { min: null };
    const value = -999;

    // WHEN
    const result = validateNumberAttribute(params, value);

    // THEN
    expect(result).toEqual({
      success: true,
      data: -999,
    });
  });

  it("should return success false when value is greater than max", () => {
    // GIVEN
    const params = { max: 10 };
    const value = 11;

    // WHEN
    const result = validateNumberAttribute(params, value);

    // THEN
    expect(result).toEqual({
      success: false,
      error: "Value must be at most 10",
    });
  });

  it("should return success true when value equals max", () => {
    // GIVEN
    const params = { max: 10 };
    const value = 10;

    // WHEN
    const result = validateNumberAttribute(params, value);

    // THEN
    expect(result).toEqual({
      success: true,
      data: 10,
    });
  });

  it("should return success true when value is less than max", () => {
    // GIVEN
    const params = { max: 10 };
    const value = 9;

    // WHEN
    const result = validateNumberAttribute(params, value);

    // THEN
    expect(result).toEqual({
      success: true,
      data: 9,
    });
  });

  it("should ignore max when it is null", () => {
    // GIVEN
    const params = { max: null };
    const value = 999_999;

    // WHEN
    const result = validateNumberAttribute(params, value);

    // THEN
    expect(result).toEqual({
      success: true,
      data: 999_999,
    });
  });

  it("should validate against both min and max constraints", () => {
    // GIVEN
    const params = { min: 5, max: 10 };

    // WHEN
    const resultTooSmall = validateNumberAttribute(params, 4);
    const resultTooBig = validateNumberAttribute(params, 11);
    const resultValid = validateNumberAttribute(params, 7);

    // THEN
    expect(resultTooSmall).toEqual({
      success: false,
      error: "Value must be at least 5",
    });

    expect(resultTooBig).toEqual({
      success: false,
      error: "Value must be at most 10",
    });

    expect(resultValid).toEqual({
      success: true,
      data: 7,
    });
  });

  it("should validate constraints even when not required and value provided", () => {
    // GIVEN
    const params = { isRequired: false, min: 5, max: 10 };

    // WHEN
    const resultTooSmall = validateNumberAttribute(params, 4);
    const resultTooBig = validateNumberAttribute(params, 11);
    const resultValid = validateNumberAttribute(params, 7);
    const resultNull = validateNumberAttribute(params, null);
    const resultUndefined = validateNumberAttribute(params, undefined);

    // THEN
    expect(resultTooSmall).toEqual({
      success: false,
      error: "Value must be at least 5",
    });

    expect(resultTooBig).toEqual({
      success: false,
      error: "Value must be at most 10",
    });

    expect(resultValid).toEqual({
      success: true,
      data: 7,
    });

    expect(resultNull).toEqual({
      success: true,
      data: 0,
    });

    expect(resultUndefined).toEqual({
      success: true,
      data: 0,
    });
  });
});
