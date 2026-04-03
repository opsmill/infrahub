import { describe, expect, it } from "vitest";

import { getDecisionNumericValue } from "./constants";

describe("getDecisionNumericValue", () => {
  it("returns 6 for Allow", () => {
    // GIVEN
    const label = "Allow";

    // WHEN
    const result = getDecisionNumericValue(label);

    // THEN
    expect(result).toBe(6);
  });

  it("returns 1 for Deny", () => {
    // GIVEN
    const label = "Deny";

    // WHEN
    const result = getDecisionNumericValue(label);

    // THEN
    expect(result).toBe(1);
  });

  it("returns undefined for unknown label", () => {
    // GIVEN
    const label = "Unknown";

    // WHEN
    const result = getDecisionNumericValue(label);

    // THEN
    expect(result).toBeUndefined();
  });
});
