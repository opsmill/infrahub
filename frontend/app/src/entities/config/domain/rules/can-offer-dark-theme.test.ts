import { describe, expect, test } from "vitest";

import { canOfferDarkTheme } from "@/entities/config/domain/rules/can-offer-dark-theme";

describe("canOfferDarkTheme", () => {
  test("an enabled flag offers the theme everywhere", () => {
    expect(canOfferDarkTheme({ dark_theme: true }, false)).toBe(true);
    expect(canOfferDarkTheme({ dark_theme: true }, true)).toBe(true);
  });

  test("a disabled flag is an operator saying no, and wins even on a dev server", () => {
    expect(canOfferDarkTheme({ dark_theme: false }, true)).toBe(false);
    expect(canOfferDarkTheme({ dark_theme: false }, false)).toBe(false);
  });

  test("a backend that predates the flag enables the theme only under a dev server", () => {
    expect(canOfferDarkTheme({}, true)).toBe(true);
    expect(canOfferDarkTheme(undefined, true)).toBe(true);

    // A production build asking about the same old backend stays light.
    expect(canOfferDarkTheme({}, false)).toBe(false);
    expect(canOfferDarkTheme(undefined, false)).toBe(false);
  });
});
