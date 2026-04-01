import { describe, expect, it } from "vitest";

import { validateFloatAttribute } from "./validate-float-attribute";

describe("validateFloatAttribute", () => {
  it("accepts a valid float value", () => {
    const result = validateFloatAttribute({}, 7.7);
    expect(result).toEqual({ success: true, data: 7.7 });
  });

  it("accepts zero", () => {
    const result = validateFloatAttribute({}, 0);
    expect(result).toEqual({ success: true, data: 0 });
  });

  it("accepts negative float", () => {
    const result = validateFloatAttribute({}, -3.14);
    expect(result).toEqual({ success: true, data: -3.14 });
  });

  it("rejects NaN", () => {
    const result = validateFloatAttribute({}, NaN);
    expect(result).toEqual({ success: false, error: "Value must be a number" });
  });

  it("rejects null when required", () => {
    const result = validateFloatAttribute({ isRequired: true }, null);
    expect(result).toEqual({ success: false, error: "Required" });
  });

  it("accepts null when optional", () => {
    const result = validateFloatAttribute({ isRequired: false }, null);
    expect(result).toEqual({ success: true, data: 0 });
  });

  it("rejects value below min", () => {
    const result = validateFloatAttribute({ min: 0.0 }, -0.5);
    expect(result).toEqual({ success: false, error: "Value must be at least 0" });
  });

  it("rejects value above max", () => {
    const result = validateFloatAttribute({ max: 100.0 }, 150.3);
    expect(result).toEqual({ success: false, error: "Value must be at most 100" });
  });

  it("accepts value at min boundary", () => {
    const result = validateFloatAttribute({ min: 1.5 }, 1.5);
    expect(result).toEqual({ success: true, data: 1.5 });
  });

  it("accepts value at max boundary", () => {
    const result = validateFloatAttribute({ max: 100.0 }, 100.0);
    expect(result).toEqual({ success: true, data: 100.0 });
  });

  it("accepts value within range", () => {
    const result = validateFloatAttribute({ min: 0.0, max: 100.0 }, 50.5);
    expect(result).toEqual({ success: true, data: 50.5 });
  });

  it("accepts undefined when optional", () => {
    const result = validateFloatAttribute({ isRequired: false }, undefined);
    expect(result).toEqual({ success: true, data: 0 });
  });
});
