import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import {
  formatRelativeTimeFromNow,
  formatWithPattern,
  isInPreviousYear,
} from "@/shared/utils/date";

// A fixed UTC instant: 2026-06-11 14:30:00 UTC.
const FIXED_INSTANT = new Date("2026-06-11T14:30:00Z");

describe("formatWithPattern (pure)", () => {
  test("renders a pattern in an explicit IANA timezone", () => {
    // GIVEN a fixed instant and a Paris timezone (UTC+2 in June, CEST)
    // WHEN formatted
    const result = formatWithPattern(FIXED_INSTANT, {
      pattern: "yyyy-MM-dd HH:mm",
      timezone: "Europe/Paris",
    });

    // THEN the wall clock is shifted to 16:30
    expect(result).toBe("2026-06-11 16:30");
  });

  test("renders the same instant differently in another timezone", () => {
    // GIVEN the same instant and a New York timezone (UTC-4 in June, EDT)
    // WHEN formatted
    const result = formatWithPattern(FIXED_INSTANT, {
      pattern: "yyyy-MM-dd HH:mm",
      timezone: "America/New_York",
    });

    // THEN the wall clock is 10:30, same calendar day
    expect(result).toBe("2026-06-11 10:30");
  });

  test("crosses the date boundary when the zone shifts the day", () => {
    // GIVEN a late-UTC instant and a Tokyo timezone (UTC+9)
    const lateUtc = new Date("2026-06-11T23:30:00Z");

    // WHEN formatted
    const result = formatWithPattern(lateUtc, {
      pattern: "yyyy-MM-dd HH:mm",
      timezone: "Asia/Tokyo",
    });

    // THEN it rolls over to the next calendar day, 08:30
    expect(result).toBe("2026-06-12 08:30");
  });

  test("falls back to the browser local zone when timezone is null/undefined", () => {
    // GIVEN the same instant formatted with a null and an omitted timezone
    // WHEN formatted both ways
    const withNull = formatWithPattern(FIXED_INSTANT, {
      pattern: "yyyy-MM-dd HH:mm",
      timezone: null,
    });
    const withUndefined = formatWithPattern(FIXED_INSTANT, { pattern: "yyyy-MM-dd HH:mm" });

    // THEN both render in the browser zone → identical output (and match date-fns's local format)
    expect(withNull).toBe(withUndefined);
    expect(withNull).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/);
  });

  test("accepts string and number inputs", () => {
    // GIVEN the instant as an ISO string and as an epoch number
    // WHEN each is formatted
    const fromString = formatWithPattern(FIXED_INSTANT.toISOString(), {
      pattern: "yyyy",
      timezone: "UTC",
    });
    const fromNumber = formatWithPattern(FIXED_INSTANT.getTime(), {
      pattern: "yyyy",
      timezone: "UTC",
    });

    // THEN both resolve to the same year
    expect(fromString).toBe("2026");
    expect(fromNumber).toBe("2026");
  });

  test("degrades instead of throwing on an invalid date", () => {
    // GIVEN a malformed timestamp (the render subtree has no error boundary)
    // WHEN formatted
    const result = formatWithPattern("not-a-date", { pattern: "yyyy-MM-dd", timezone: "UTC" });

    // THEN it degrades to the raw input rather than crashing
    expect(result).toBe("not-a-date");
  });

  test("degrades to the browser zone on an unknown timezone", () => {
    // GIVEN a zone the runtime doesn't recognize
    const browserZone = formatWithPattern(FIXED_INSTANT, { pattern: "yyyy-MM-dd HH:mm" });

    // WHEN formatted with that zone
    const result = formatWithPattern(FIXED_INSTANT, {
      pattern: "yyyy-MM-dd HH:mm",
      timezone: "Not/AZone",
    });

    // THEN it falls back to local rendering rather than throwing
    expect(result).toBe(browserZone);
  });
});

describe("formatRelativeTimeFromNow", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(FIXED_INSTANT);
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  test("renders a suffixed relative distance", () => {
    // GIVEN an instant two days before now
    const twoDaysAgo = new Date("2026-06-09T14:30:00Z");

    // WHEN formatted relative to now
    const result = formatRelativeTimeFromNow(twoDaysAgo);

    // THEN it reads as a suffixed distance
    expect(result).toBe("2 days ago");
  });

  test("degrades instead of throwing on an invalid date", () => {
    // GIVEN a malformed timestamp
    // WHEN formatted relative to now
    const result = formatRelativeTimeFromNow("not-a-date");

    // THEN it degrades to the raw input
    expect(result).toBe("not-a-date");
  });
});

describe("isInPreviousYear", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(FIXED_INSTANT);
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  test("true for a date in the previous calendar year", () => {
    // GIVEN a date in the previous calendar year
    // WHEN checked
    const result = isInPreviousYear(new Date("2025-12-31T00:00:00Z"));

    // THEN it is in the previous year
    expect(result).toBe(true);
  });

  test("false for a date in the current year", () => {
    // GIVEN a date in the current year
    // WHEN checked
    const result = isInPreviousYear(FIXED_INSTANT);

    // THEN it is not in the previous year
    expect(result).toBe(false);
  });
});
