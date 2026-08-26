import { describe, expect, test } from "vitest";

import { getDefaultTheme } from "@/entities/config/domain/rules/get-default-theme";

describe("getDefaultTheme", () => {
  test("follows the desktop when the deployment offers the theme", () => {
    expect(getDefaultTheme({ canOfferDark: true, isDevServer: false, systemTheme: "dark" })).toBe(
      "dark"
    );
    expect(getDefaultTheme({ canOfferDark: true, isDevServer: false, systemTheme: "light" })).toBe(
      "light"
    );
  });

  test("a dev server overrides the desktop, so the theme being worked on is the one on screen", () => {
    expect(getDefaultTheme({ canOfferDark: true, isDevServer: true, systemTheme: "light" })).toBe(
      "dark"
    );
  });

  test("a deployment that does not offer the theme stays light on any desktop", () => {
    expect(getDefaultTheme({ canOfferDark: false, isDevServer: false, systemTheme: "dark" })).toBe(
      "light"
    );

    // Even the dev-server override cannot reach past an operator who said no.
    expect(getDefaultTheme({ canOfferDark: false, isDevServer: true, systemTheme: "dark" })).toBe(
      "light"
    );
  });
});
