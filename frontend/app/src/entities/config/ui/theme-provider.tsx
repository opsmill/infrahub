import { ThemeProvider as DesignSystemThemeProvider, useSystemTheme } from "@infrahub/ui";
import type React from "react";

import { canOfferDarkTheme } from "@/entities/config/domain/rules/can-offer-dark-theme";
import { getDefaultTheme } from "@/entities/config/domain/rules/get-default-theme";
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
  const systemTheme = useSystemTheme();

  const isDevServer = import.meta.env.DEV;
  const canChoose = canOfferDarkTheme(config.experimental_features, isDevServer);

  return (
    <DesignSystemThemeProvider
      canChoose={canChoose}
      defaultTheme={getDefaultTheme({ canOfferDark: canChoose, isDevServer, systemTheme })}
    >
      {children}
    </DesignSystemThemeProvider>
  );
}
