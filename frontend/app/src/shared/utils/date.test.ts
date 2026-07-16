import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { formatDate, formatRelativeTimeFromNow, isInPreviousYear } from "@/shared/utils/date";

// A fixed UTC instant: 2026-06-11 14:30:00 UTC.
const FIXED_INSTANT = new Date("2026-06-11T14:30:00Z");

describe("formatDate (pure)", () => {
  test("renders a pattern in an explicit IANA timezone", () => {
    // Europe/Paris is UTC+2 in June (CEST) → 16:30 wall clock.
    expect(
      formatDate(FIXED_INSTANT, { pattern: "yyyy-MM-dd HH:mm", timezone: "Europe/Paris" })
    ).toBe("2026-06-11 16:30");
  });

  test("renders the same instant differently in another timezone", () => {
    // America/New_York is UTC-4 in June (EDT) → 10:30 wall clock, same calendar day.
    expect(
      formatDate(FIXED_INSTANT, { pattern: "yyyy-MM-dd HH:mm", timezone: "America/New_York" })
    ).toBe("2026-06-11 10:30");
  });

  test("crosses the date boundary when the zone shifts the day", () => {
    // 2026-06-11 23:30 UTC in Tokyo (UTC+9) is the next calendar day, 08:30.
    const lateUtc = new Date("2026-06-11T23:30:00Z");
    expect(formatDate(lateUtc, { pattern: "yyyy-MM-dd HH:mm", timezone: "Asia/Tokyo" })).toBe(
      "2026-06-12 08:30"
    );
  });

  test("falls back to the browser local zone when timezone is null/undefined", () => {
    const withNull = formatDate(FIXED_INSTANT, { pattern: "yyyy-MM-dd HH:mm", timezone: null });
    const withUndefined = formatDate(FIXED_INSTANT, { pattern: "yyyy-MM-dd HH:mm" });
    // Both paths render in the browser zone → identical output (and match date-fns's local format).
    expect(withNull).toBe(withUndefined);
    expect(withNull).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/);
  });

  test("accepts string and number inputs", () => {
    expect(formatDate(FIXED_INSTANT.toISOString(), { pattern: "yyyy", timezone: "UTC" })).toBe(
      "2026"
    );
    expect(formatDate(FIXED_INSTANT.getTime(), { pattern: "yyyy", timezone: "UTC" })).toBe("2026");
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
