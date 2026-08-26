import { describe, expect, test } from "vitest";

import type { EffectivePreferences } from "@/entities/preferences/domain/model/preference";
import {
  inheritedTimezone,
  resolveDatePreferences,
} from "@/entities/preferences/domain/rules/resolve-date-preferences";

// Fixture invariant, mirroring the API: a non-USER source inherits its own {value, source} (nothing
// is being shadowed), while a USER source states the layer it shadows — never USER itself.
describe("resolveDatePreferences", () => {
  test("maps a USER date-format key to its date-fns pattern", () => {
    // GIVEN a user-set EU date format
    const preferences: EffectivePreferences = {
      dateFormat: {
        value: "EU_DATETIME",
        source: "USER",
        inherited: { value: null, source: "DEFAULT" },
      },
      timezone: { value: null, source: "DEFAULT", inherited: { value: null, source: "DEFAULT" } },
    };

    // WHEN resolved
    const resolved = resolveDatePreferences(preferences);

    // THEN the pattern is the preset for that key
    expect(resolved.pattern).toBe("dd/MM/yyyy HH:mm");
  });

  test("maps a GLOBAL date-format key just like a USER one", () => {
    // GIVEN an org-wide date format
    const preferences: EffectivePreferences = {
      dateFormat: {
        value: "US_12H",
        source: "GLOBAL",
        inherited: { value: "US_12H", source: "GLOBAL" },
      },
      timezone: { value: null, source: "DEFAULT", inherited: { value: null, source: "DEFAULT" } },
    };

    // WHEN resolved
    const resolved = resolveDatePreferences(preferences);

    // THEN the pattern is the preset for that key
    expect(resolved.pattern).toBe("MM/dd/yyyy hh:mm a");
  });

  test("keeps the USER timezone value", () => {
    // GIVEN a user-set timezone
    const preferences: EffectivePreferences = {
      dateFormat: { value: null, source: "DEFAULT", inherited: { value: null, source: "DEFAULT" } },
      timezone: {
        value: "Europe/Paris",
        source: "USER",
        inherited: { value: null, source: "DEFAULT" },
      },
    };

    // WHEN resolved
    const resolved = resolveDatePreferences(preferences);

    // THEN the timezone passes through
    expect(resolved.timezone).toBe("Europe/Paris");
  });

  test("resolves a DEFAULT source to null so consumers use the browser locale/zone", () => {
    // GIVEN both fields left at their DEFAULT source (even with values present)
    const preferences: EffectivePreferences = {
      dateFormat: {
        value: "EU_DATETIME",
        source: "DEFAULT",
        inherited: { value: "EU_DATETIME", source: "DEFAULT" },
      },
      timezone: {
        value: "Europe/Paris",
        source: "DEFAULT",
        inherited: { value: "Europe/Paris", source: "DEFAULT" },
      },
    };

    // WHEN resolved
    const resolved = resolveDatePreferences(preferences);

    // THEN nothing is applied
    expect(resolved).toEqual({ pattern: null, timezone: null });
  });

  test("resolves a non-DEFAULT source with a missing value to null", () => {
    // GIVEN a USER source but no stored value
    const preferences: EffectivePreferences = {
      dateFormat: { value: null, source: "USER", inherited: { value: null, source: "DEFAULT" } },
      timezone: { value: null, source: "USER", inherited: { value: null, source: "DEFAULT" } },
    };

    // WHEN resolved
    const resolved = resolveDatePreferences(preferences);

    // THEN nothing is applied
    expect(resolved).toEqual({ pattern: null, timezone: null });
  });

  test("resolves undefined preferences (no data yet) to null on both fields", () => {
    // GIVEN no preferences data
    // WHEN resolved
    const resolved = resolveDatePreferences(undefined);

    // THEN both fields fall back to null
    expect(resolved).toEqual({ pattern: null, timezone: null });
  });
});

describe("inheritedTimezone", () => {
  test("returns the GLOBAL value, which is what an unset field inherits", () => {
    expect(inheritedTimezone({ value: "Europe/Paris", source: "GLOBAL" })).toBe("Europe/Paris");
  });

  test("returns null for a DEFAULT source so the browser zone applies", () => {
    expect(inheritedTimezone({ value: null, source: "DEFAULT" })).toBeNull();
  });

  test("ignores a value carried on a DEFAULT source, as the pattern resolver does", () => {
    expect(inheritedTimezone({ value: "Europe/Paris", source: "DEFAULT" })).toBeNull();
  });

  test("discards a USER value: dropping the override is exactly what stops it applying", () => {
    // The API resolves the inherited value away once an override wins, so it is unknowable here —
    // null (browser zone) is honest, the caller's own zone would be a stale guess.
    expect(inheritedTimezone({ value: "Asia/Tokyo", source: "USER" })).toBeNull();
  });
});
