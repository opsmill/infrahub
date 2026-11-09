import type React from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import {
  DatePreferencesContext,
  dateOnlyPattern,
  type ResolvedDatePreferences,
  useFormatDate,
} from "@/shared/context/date-preferences-context";

const FIXED_INSTANT = new Date("2026-06-11T14:30:00Z");

function wrapperFor(value: ResolvedDatePreferences | null) {
  return ({ children }: { children: React.ReactNode }) =>
    value === null ? (
      <>{children}</>
    ) : (
      <DatePreferencesContext value={value}>{children}</DatePreferencesContext>
    );
}

describe("useFormatDate", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(FIXED_INSTANT);
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  test("datetime variant uses the resolved user pattern + timezone", async () => {
    const { result } = await renderHook(() => useFormatDate(), {
      wrapper: wrapperFor({ pattern: "yyyy-MM-dd HH:mm", timezone: "Europe/Paris" }),
    });
    // UTC+2 in June → 16:30.
    expect(result.current.formatDate(FIXED_INSTANT)).toBe("2026-06-11 16:30");
    expect(result.current.timezone).toBe("Europe/Paris");
  });

  test("datetime variant applies the resolved timezone (different zone → different clock)", async () => {
    const { result } = await renderHook(() => useFormatDate(), {
      wrapper: wrapperFor({ pattern: "yyyy-MM-dd HH:mm", timezone: "America/New_York" }),
    });
    expect(result.current.formatDate(FIXED_INSTANT, "datetime")).toBe("2026-06-11 10:30");
  });

  test("relative variant is timezone-independent", async () => {
    const { result } = await renderHook(() => useFormatDate(), {
      wrapper: wrapperFor({ pattern: "yyyy-MM-dd HH:mm", timezone: "Asia/Tokyo" }),
    });
    const twoDaysAgo = new Date("2026-06-09T14:30:00Z");
    expect(result.current.formatDate(twoDaysAgo, "relative")).toBe("2 days ago");
  });

  test("date variant renders the date portion only, derived from the full pattern", async () => {
    const { result } = await renderHook(() => useFormatDate(), {
      wrapper: wrapperFor({ pattern: "yyyy-MM-dd HH:mm", timezone: "Europe/Paris" }),
    });
    expect(result.current.formatDate(FIXED_INSTANT, "date")).toBe("2026-06-11");
  });

  test("date variant derives from a slash-style pattern too", async () => {
    const { result } = await renderHook(() => useFormatDate(), {
      wrapper: wrapperFor({ pattern: "dd/MM/yyyy HH:mm", timezone: "UTC" }),
    });
    expect(result.current.formatDate(FIXED_INSTANT, "date")).toBe("11/06/2026");
  });

  test("default source (null pattern) falls back to the browser locale, not a hardcoded pattern", async () => {
    const { result } = await renderHook(() => useFormatDate(), {
      wrapper: wrapperFor({ pattern: null, timezone: null }),
    });
    // Locale datetime string (medium date + short time) — not the ISO pattern.
    const out = result.current.formatDate(FIXED_INSTANT, "datetime");
    expect(out).not.toMatch(/^\d{4}-\d{2}-\d{2} /);
    expect(out.length).toBeGreaterThan(0);
  });

  test("no provider mounted → browser-locale fallback, never crashes", async () => {
    const { result } = await renderHook(() => useFormatDate(), { wrapper: wrapperFor(null) });
    expect(result.current.timezone).toBeNull();
    expect(result.current.formatDate(FIXED_INSTANT)).toBeTruthy();
  });
});

describe("dateOnlyPattern", () => {
  test("strips the time portion from a space-separated pattern", () => {
    expect(dateOnlyPattern("yyyy-MM-dd HH:mm")).toBe("yyyy-MM-dd");
  });

  test("handles the ISO_8601 preset's quoted 'T' separator", () => {
    expect(dateOnlyPattern("yyyy-MM-dd'T'HH:mm:ssXXX")).toBe("yyyy-MM-dd");
  });

  test("handles the US_12H preset's day-period token", () => {
    expect(dateOnlyPattern("MM/dd/yyyy hh:mm a")).toBe("MM/dd/yyyy");
  });

  test("returns a date-only pattern unchanged", () => {
    expect(dateOnlyPattern("yyyy-MM-dd")).toBe("yyyy-MM-dd");
  });
});
