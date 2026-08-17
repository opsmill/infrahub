import type { ResolvedTheme } from "@/shared/context/theme-context";

import type { ThemeChoice } from "@/entities/preferences/domain/model/theme";

/**
 * Resolves a stored choice to the palette to paint. The browser's appearance is consulted only for
 * an explicit SYSTEM choice: dark is pre-release, so an absent, unreadable or unrecognised choice
 * falls back to light rather than inferring dark from a setting the user never pointed here.
 *
 * Pure by contract — no storage, no DOM. The caller supplies the browser's current appearance.
 */
export function resolveTheme(
  choice: ThemeChoice | null | undefined,
  systemPrefersDark: boolean
): ResolvedTheme {
  switch (choice) {
    case "DARK":
      return "dark";
    case "SYSTEM":
      return systemPrefersDark ? "dark" : "light";
    default:
      return "light";
  }
}
