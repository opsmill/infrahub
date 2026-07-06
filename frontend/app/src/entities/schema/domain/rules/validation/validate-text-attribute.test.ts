import { describe, expect, it } from "vitest";

import { validateTextAttribute } from "./validate-text-attribute";

describe("validateTextAttribute", () => {
  it("should return success false with 'Required' error when value is null and isRequired is true", () => {
    // GIVEN
    const params = { isRequired: true };
    const value = null;

    // WHEN
    const result = validateTextAttribute(params, value);

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
    const result = validateTextAttribute(params, value);

    // THEN
    expect(result).toEqual({
      success: false,
      error: "Required",
    });
  });

  it("should return success true with empty string when value is null and isRequired is false", () => {
    // GIVEN
    const params = { isRequired: false };
    const value = null;

    // WHEN
    const result = validateTextAttribute(params, value);

    // THEN
    expect(result).toEqual({
      success: true,
      data: "",
    });
  });

  it("should return success false when value length is less than minLength", () => {
    // GIVEN
    const params = { minLength: 5 };
    const value = "abc";

    // WHEN
    const result = validateTextAttribute(params, value);

    // THEN
    expect(result).toEqual({
      success: false,
      error: "Text must be at least 5 characters long",
    });
  });

  it("should return success true when value length equals minLength", () => {
    // GIVEN
    const params = { minLength: 3 };
    const value = "abc";

    // WHEN
    const result = validateTextAttribute(params, value);

    // THEN
    expect(result).toEqual({
      success: true,
      data: "abc",
    });
  });

  it("should return success true when value length is greater than minLength", () => {
    // GIVEN
    const params = { minLength: 3 };
    const value = "abcd";

    // WHEN
    const result = validateTextAttribute(params, value);

    // THEN
    expect(result).toEqual({
      success: true,
      data: "abcd",
    });
  });

  it("should ignore minLength when it is 0", () => {
    // GIVEN
    const params = { minLength: 0 };
    const value = "";

    // WHEN
    const result = validateTextAttribute(params, value);

    // THEN
    expect(result).toEqual({
      success: true,
      data: "",
    });
  });

  it("should return success false when value length is greater than maxLength", () => {
    // GIVEN
    const params = { maxLength: 3 };
    const value = "abcd";

    // WHEN
    const result = validateTextAttribute(params, value);

    // THEN
    expect(result).toEqual({
      success: false,
      error: "Text must be at most 3 characters long",
    });
  });

  it("should return success true when value length equals maxLength", () => {
    // GIVEN
    const params = { maxLength: 3 };
    const value = "abc";

    // WHEN
    const result = validateTextAttribute(params, value);

    // THEN
    expect(result).toEqual({
      success: true,
      data: "abc",
    });
  });

  it("should return success true when value length is less than maxLength", () => {
    // GIVEN
    const params = { maxLength: 3 };
    const value = "ab";

    // WHEN
    const result = validateTextAttribute(params, value);

    // THEN
    expect(result).toEqual({
      success: true,
      data: "ab",
    });
  });

  it("should ignore maxLength when it is 0", () => {
    // GIVEN
    const params = { maxLength: 0 };
    const value = "any length string";

    // WHEN
    const result = validateTextAttribute(params, value);

    // THEN
    expect(result).toEqual({
      success: true,
      data: "any length string",
    });
  });

  it("should validate against both minLength and maxLength constraints", () => {
    // GIVEN
    const params = { minLength: 2, maxLength: 4 };

    // WHEN
    const resultTooShort = validateTextAttribute(params, "a");
    const resultTooLong = validateTextAttribute(params, "abcde");
    const resultValid = validateTextAttribute(params, "abc");

    // THEN
    expect(resultTooShort).toEqual({
      success: false,
      error: "Text must be at least 2 characters long",
    });

    expect(resultTooLong).toEqual({
      success: false,
      error: "Text must be at most 4 characters long",
    });

    expect(resultValid).toEqual({
      success: true,
      data: "abc",
    });
  });

  it("should validate length constraints even when not required and value provided, including empty string", () => {
    // GIVEN
    const params = { isRequired: false, minLength: 2, maxLength: 4 };

    // WHEN
    const resultTooShort = validateTextAttribute(params, "a");
    const resultTooLong = validateTextAttribute(params, "abcde");
    const resultValid = validateTextAttribute(params, "abc");
    const resultNull = validateTextAttribute(params, null);
    const resultUndefined = validateTextAttribute(params, undefined);
    const resultEmptyString = validateTextAttribute(params, "");

    // THEN
    expect(resultTooShort).toEqual({
      success: false,
      error: "Text must be at least 2 characters long",
    });

    expect(resultTooLong).toEqual({
      success: false,
      error: "Text must be at most 4 characters long",
    });

    expect(resultValid).toEqual({
      success: true,
      data: "abc",
    });

    expect(resultNull).toEqual({
      success: true,
      data: "",
    });

    expect(resultUndefined).toEqual({
      success: true,
      data: "",
    });

    expect(resultEmptyString).toEqual({
      success: true,
      data: "",
    });
  });
});
