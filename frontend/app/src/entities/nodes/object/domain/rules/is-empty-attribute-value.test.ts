import { describe, expect, it } from "vitest";

import { isEmptyAttributeValue } from "./is-empty-attribute-value";

describe("isEmptyAttributeValue", () => {
  it.each([null, undefined, "", [], {}])("should treat %j as empty", (value) => {
    // WHEN
    const result = isEmptyAttributeValue(value);

    // THEN
    expect(result).toBe(true);
  });

  it.each([0, false, "x", ["a"], { a: 1 }])("should treat %j as a value", (value) => {
    // WHEN
    const result = isEmptyAttributeValue(value);

    // THEN
    expect(result).toBe(false);
  });
});
