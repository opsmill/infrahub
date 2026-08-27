import { describe, expect, test } from "vitest";

import type { EffectivePreferences } from "@/entities/preferences/domain/model/preference";
import {
  inheritedValue,
  resolveDatePreferences,
} from "@/entities/preferences/domain/rules/resolve-date-preferences";

// Fixtures follow the `inherited` invariant documented on `EffectivePreference`.
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

describe("inheritedValue", () => {
  test("returns the GLOBAL value, which is what an unset field inherits", () => {
    expect(
      inheritedValue({
        value: "Europe/Paris",
        source: "GLOBAL",
        inherited: { value: "Europe/Paris", source: "GLOBAL" },
      })
    ).toBe("Europe/Paris");
  });

  test("returns null for a DEFAULT source so the browser zone applies", () => {
    expect(
      inheritedValue({
        value: null,
        source: "DEFAULT",
        inherited: { value: null, source: "DEFAULT" },
      })
    ).toBeNull();
  });

  test("ignores a value carried on a DEFAULT inherited layer, as the pattern resolver does", () => {
    expect(
      inheritedValue({
        value: "Europe/Paris",
        source: "DEFAULT",
        inherited: { value: "Europe/Paris", source: "DEFAULT" },
      })
    ).toBeNull();
  });

  test("returns the GLOBAL layer a USER override shadows, which is what clearing it restores", () => {
    // A caller's own override must not hide the layer beneath it: that layer is what clearing the
    // override restores, so the preview needs it while the field is empty.
    expect(
      inheritedValue({
        value: "Asia/Tokyo",
        source: "USER",
        inherited: { value: "Europe/Paris", source: "GLOBAL" },
      })
    ).toBe("Europe/Paris");
  });

  test("returns null for a USER override that shadows nothing", () => {
    expect(
      inheritedValue({
        value: "Asia/Tokyo",
        source: "USER",
        inherited: { value: null, source: "DEFAULT" },
      })
    ).toBeNull();
  });

  test("reads the inherited layer of any field, not just the timezone", () => {
    // The rule is about the inherited layer, not about zones: a date-format key resolves identically.
    expect(
      inheritedValue({
        value: "EU_DATETIME",
        source: "USER",
        inherited: { value: "ISO_DATETIME", source: "GLOBAL" },
      })
    ).toBe("ISO_DATETIME");
  });
});
