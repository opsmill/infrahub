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
    // Europe/Paris is UTC+2 in June (CEST) → 16:30 wall clock.
    expect(
      formatWithPattern(FIXED_INSTANT, { pattern: "yyyy-MM-dd HH:mm", timezone: "Europe/Paris" })
    ).toBe("2026-06-11 16:30");
  });

  test("renders the same instant differently in another timezone", () => {
    // America/New_York is UTC-4 in June (EDT) → 10:30 wall clock, same calendar day.
    expect(
      formatWithPattern(FIXED_INSTANT, {
        pattern: "yyyy-MM-dd HH:mm",
        timezone: "America/New_York",
      })
    ).toBe("2026-06-11 10:30");
  });

  test("crosses the date boundary when the zone shifts the day", () => {
    // 2026-06-11 23:30 UTC in Tokyo (UTC+9) is the next calendar day, 08:30.
    const lateUtc = new Date("2026-06-11T23:30:00Z");
    expect(
      formatWithPattern(lateUtc, { pattern: "yyyy-MM-dd HH:mm", timezone: "Asia/Tokyo" })
    ).toBe("2026-06-12 08:30");
  });

  test("falls back to the browser local zone when timezone is null/undefined", () => {
    const withNull = formatWithPattern(FIXED_INSTANT, {
      pattern: "yyyy-MM-dd HH:mm",
      timezone: null,
    });
    const withUndefined = formatWithPattern(FIXED_INSTANT, { pattern: "yyyy-MM-dd HH:mm" });
    // Both paths render in the browser zone → identical output (and match date-fns's local format).
    expect(withNull).toBe(withUndefined);
    expect(withNull).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/);
  });

  test("accepts string and number inputs", () => {
    expect(
      formatWithPattern(FIXED_INSTANT.toISOString(), { pattern: "yyyy", timezone: "UTC" })
    ).toBe("2026");
    expect(formatWithPattern(FIXED_INSTANT.getTime(), { pattern: "yyyy", timezone: "UTC" })).toBe(
      "2026"
    );
  });

  test("degrades instead of throwing on an invalid date", () => {
    // A malformed timestamp must not crash the (error-boundary-less) render subtree.
    expect(formatWithPattern("not-a-date", { pattern: "yyyy-MM-dd", timezone: "UTC" })).toBe(
      "not-a-date"
    );
  });

  test("degrades to the browser zone on an unknown timezone", () => {
    // A zone the runtime doesn't recognize must fall back to local rendering, not throw.
    const browserZone = formatWithPattern(FIXED_INSTANT, { pattern: "yyyy-MM-dd HH:mm" });
    expect(
      formatWithPattern(FIXED_INSTANT, { pattern: "yyyy-MM-dd HH:mm", timezone: "Not/AZone" })
    ).toBe(browserZone);
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
    const twoDaysAgo = new Date("2026-06-09T14:30:00Z");
    expect(formatRelativeTimeFromNow(twoDaysAgo)).toBe("2 days ago");
  });

  test("degrades instead of throwing on an invalid date", () => {
    expect(formatRelativeTimeFromNow("not-a-date")).toBe("not-a-date");
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
    expect(isInPreviousYear(new Date("2025-12-31T00:00:00Z"))).toBe(true);
  });

  test("false for a date in the current year", () => {
    expect(isInPreviousYear(FIXED_INSTANT)).toBe(false);
  });
});
