import { describe, expect, test } from "vitest";

import type { EffectivePreferences } from "@/entities/preferences/domain/model/preference";
import { resolveDatePreferences } from "@/entities/preferences/domain/rules/resolve-date-preferences";

describe("resolveDatePreferences", () => {
  test("maps a USER date-format key to its date-fns pattern", () => {
    // GIVEN a user-set EU date format
    const preferences: EffectivePreferences = {
      dateFormat: { value: "EU_DATETIME", source: "USER" },
      timezone: { value: null, source: "DEFAULT" },
    };

    // WHEN resolved
    const resolved = resolveDatePreferences(preferences);

    // THEN the pattern is the preset for that key
    expect(resolved.pattern).toBe("dd/MM/yyyy HH:mm");
  });

  test("maps a GLOBAL date-format key just like a USER one", () => {
    // GIVEN an org-wide date format
    const preferences: EffectivePreferences = {
      dateFormat: { value: "US_12H", source: "GLOBAL" },
      timezone: { value: null, source: "DEFAULT" },
    };

    // WHEN resolved
    const resolved = resolveDatePreferences(preferences);

    // THEN the pattern is the preset for that key
    expect(resolved.pattern).toBe("MM/dd/yyyy hh:mm a");
  });

  test("keeps the USER timezone value", () => {
    // GIVEN a user-set timezone
    const preferences: EffectivePreferences = {
      dateFormat: { value: null, source: "DEFAULT" },
      timezone: { value: "Europe/Paris", source: "USER" },
    };

    // WHEN resolved
    const resolved = resolveDatePreferences(preferences);

    // THEN the timezone passes through
    expect(resolved.timezone).toBe("Europe/Paris");
  });

  test("resolves a DEFAULT source to null so consumers use the browser locale/zone", () => {
    // GIVEN both fields left at their DEFAULT source (even with values present)
    const preferences: EffectivePreferences = {
      dateFormat: { value: "EU_DATETIME", source: "DEFAULT" },
      timezone: { value: "Europe/Paris", source: "DEFAULT" },
    };

    // WHEN resolved
    const resolved = resolveDatePreferences(preferences);

    // THEN nothing is applied
    expect(resolved).toEqual({ pattern: null, timezone: null });
  });

  test("resolves a non-DEFAULT source with a missing value to null", () => {
    // GIVEN a USER source but no stored value
    const preferences: EffectivePreferences = {
      dateFormat: { value: null, source: "USER" },
      timezone: { value: null, source: "USER" },
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
