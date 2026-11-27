import { describe, expect, it } from "vitest";

import { formatUsagePercent } from "./format-usage-percent";

describe("formatUsagePercent", () => {
  it.each([
    [0, "0%"],
    [0.05, "<0.1%"],
    [3, "3%"],
    [3.25, "3.3%"],
    [42.9, "42%"],
  ])("formats %s as %s", (value, expected) => {
    // WHEN
    const label = formatUsagePercent(value);

    // THEN
    expect(label).toBe(expected);
  });
});
