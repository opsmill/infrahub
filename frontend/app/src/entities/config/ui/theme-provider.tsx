import { ThemeProvider as DesignSystemThemeProvider } from "@infrahub/ui";
import type React from "react";

import { canOfferDarkTheme } from "@/entities/config/domain/rules/can-offer-dark-theme";
import { useConfig } from "@/entities/config/ui/config-provider";

/**
 * Infrahub's theme policy. The design system owns the machinery — storing a choice, painting it,
 * exposing the switch — and this decides the two things that are ours to decide: whether the
 * deployment offers dark at all, and what a user who has never chosen should see.
 *
 * Lives in `entities/config` because the flag is config data. Nothing presentational imports it;
 * everything reads the theme through the design system.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const config = useConfig();
  const canChoose = canOfferDarkTheme(config.experimental_features, import.meta.env.DEV);

  return (
    <DesignSystemThemeProvider
      canChoose={canChoose}
      // Dark rather than the operating system's appearance: the point of enabling this on a
      // non-production deployment is that everyone working on it sees the theme being worked on,
      // which an OS-derived default would give only to those already running a dark desktop.
      defaultTheme={canChoose ? "dark" : "light"}
    >
      {children}
    </DesignSystemThemeProvider>
  );
}
