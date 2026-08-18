import type React from "react";
import { useEffect, useMemo, useState } from "react";

import { ThemeContext } from "@/shared/context/theme-context";
import type { ResolvedTheme } from "@/shared/hooks/use-resolved-theme";
import { applyTheme } from "@/shared/theme/apply-theme";
import { mirrorResolvedTheme, readStoredChoice, storeChoice } from "@/shared/theme/theme-storage";

import { canOfferDarkTheme } from "@/entities/config/domain/rules/can-offer-dark-theme";
import { useConfig } from "@/entities/config/ui/config-provider";

/**
 * Decides the theme from the deployment's flag and this browser's choice, and fills the shared
 * control context. Lives in `entities/config` because the flag is config data; `shared` components
 * read the resulting theme off the document element and never import this.
 *
 * A choice made while the feature was enabled is kept, not cleared, when the flag goes off. Turning
 * a flag off is an operator's decision about a deployment, and it should not reach through and
 * delete what users picked — flipping it back restores them to the theme they chose.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const config = useConfig();
  const canChoose = canOfferDarkTheme(config.experimental_features, import.meta.env.DEV);

  const [choice, setChoice] = useState<ResolvedTheme | null>(readStoredChoice);

  // Dark rather than the operating system's appearance: the point of enabling this on a
  // non-production deployment is that everyone working on it sees the theme being worked on, which
  // an OS-derived default would give only to the engineers already running a dark desktop.
  const theme: ResolvedTheme = canChoose ? (choice ?? "dark") : "light";

  useEffect(() => {
    applyTheme(theme);
    mirrorResolvedTheme(theme);
  }, [theme]);

  const control = useMemo(
    () => ({
      canChoose,
      setTheme: (next: ResolvedTheme) => {
        storeChoice(next);
        setChoice(next);
      },
    }),
    [canChoose]
  );

  return <ThemeContext value={control}>{children}</ThemeContext>;
}
