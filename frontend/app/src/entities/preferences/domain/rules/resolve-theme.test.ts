import { describe, expect, test } from "vitest";

import type { ThemeChoice } from "@/entities/preferences/domain/model/theme";
import { resolveTheme } from "@/entities/preferences/domain/rules/resolve-theme";

describe("resolveTheme", () => {
  test.each([
    ["LIGHT", false, "light"],
    ["LIGHT", true, "light"],
    ["DARK", false, "dark"],
    ["DARK", true, "dark"],
  ] as const)("%s ignores the system appearance (systemPrefersDark=%s)", (choice, systemPrefersDark, expected) => {
    expect(resolveTheme(choice, systemPrefersDark)).toBe(expected);
  });

  test.each([
    [true, "dark"],
    [false, "light"],
  ] as const)("SYSTEM follows the system appearance (systemPrefersDark=%s)", (systemPrefersDark, expected) => {
    expect(resolveTheme("SYSTEM", systemPrefersDark)).toBe(expected);
  });

  test("falls back to light when no choice is set", () => {
    // GIVEN nothing stored at any layer and no deployment default supplied
    // WHEN resolved
    // THEN light, never the system appearance — dark is pre-release and must not be reached by
    // inference from a browser setting the user never pointed at this application.
    expect(resolveTheme(null, true)).toBe("light");
    expect(resolveTheme(undefined, true)).toBe("light");
  });

  test("rejects an unknown stored value by falling back to light", () => {
    // GIVEN a value that is not a Theme member, e.g. written by a newer version and read by an older
    // WHEN resolved
    // THEN light rather than a crash or an unstyled page
    expect(resolveTheme("SOLARIZED" as ThemeChoice, true)).toBe("light");
  });
});
