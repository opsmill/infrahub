import { describe, expect, test } from "vitest";

import { lastCoveredDay } from "./license-dates";

describe("lastCoveredDay", () => {
  test("falls on the day before an end at midnight", () => {
    expect(lastCoveredDay("2027-03-01T00:00:00Z").toISOString()).toBe("2027-02-28T23:59:59.999Z");
  });

  test("falls on the same day for an end after midnight, even by less than a second", () => {
    expect(lastCoveredDay("2027-03-01T00:00:00.500Z").toISOString()).toBe(
      "2027-03-01T00:00:00.499Z"
    );
  });
});
