import { describe, expect, it } from "vitest";

import { isMinLength, isRequired } from "./validation";

describe("validation", () => {
  describe("isRequired", () => {
    it("should return 'Required' when value is null", () => {
      // GIVEN
      const field = { value: null };

      // WHEN
      const result = isRequired(field);

      // THEN
      expect(result).toBe("Required");
    });

    it("should return 'Required' when value is empty string", () => {
      // GIVEN
      const field = { value: "" };

      // WHEN
      const result = isRequired(field);

      // THEN
      expect(result).toBe("Required");
    });

    it("should return true when value is provided", () => {
      // GIVEN
      const field = { value: "test" };

      // WHEN
      const result = isRequired(field);

      // THEN
      expect(result).toBe(true);
    });
  });

  describe("isMinLength", () => {
    it("should return 'Required' when value is falsy", () => {
      // GIVEN
      const validator = isMinLength(3);
      const field = { value: null };

      // WHEN
      const result = validator(field);

      // THEN
      expect(result).toBe("Required");
    });

    it("should return true when value is not a string", () => {
      // GIVEN
      const validator = isMinLength(3);
      const field = { value: 123 };

      // WHEN
      const result = validator(field);

      // THEN
      expect(result).toBe(true);
    });

    it("should return error message when string length is less than minimum", () => {
      // GIVEN
      const validator = isMinLength(3);
      const field = { value: "ab" };

      // WHEN
      const result = validator(field);

      // THEN
      expect(result).toBe("Value must be at least 3 characters long");
    });

    it("should return true when string length equals minimum", () => {
      // GIVEN
      const validator = isMinLength(3);
      const field = { value: "abc" };

      // WHEN
      const result = validator(field);

      // THEN
      expect(result).toBe(true);
    });

    it("should return true when string length is greater than minimum", () => {
      // GIVEN
      const validator = isMinLength(3);
      const field = { value: "abcd" };

      // WHEN
      const result = validator(field);

      // THEN
      expect(result).toBe(true);
    });
  });
});
