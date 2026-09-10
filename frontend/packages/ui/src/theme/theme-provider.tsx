import { type ReactNode, useLayoutEffect, useMemo, useState } from "react";

import { applyTheme, type ResolvedTheme } from "./resolved-theme";
import { ThemeContext } from "./theme-context";
import { mirrorResolvedTheme, readStoredChoice, storeChoice } from "./theme-storage";

export interface ThemeProviderProps {
  /**
   * Whether this deployment lets the user pick. False paints {@link defaultTheme} regardless of
   * what this browser has stored, and hides the switch — the stored choice is ignored, never
   * deleted, so turning the choice back on restores the user to the theme they picked.
   */
  canChoose: boolean;
  /** What to paint when the user has not chosen, or when they are not being offered a choice. */
  defaultTheme: ResolvedTheme;
  children: ReactNode;
}

/**
 * Wires the theme machinery: resolves a stored choice against what the caller offers, paints it
 * before the children render, mirrors it for the next pre-paint, and fills {@link ThemeContext} so
 * a {@link ThemeSwitchMenuItem} anywhere below just works.
 *
 * It deliberately holds no opinion on *which* theme a deployment should offer or default to —
 * that is the application's policy, and it arrives entirely through the two props.
 */
export function ThemeProvider({ canChoose, defaultTheme, children }: ThemeProviderProps) {
  const [choice, setChoice] = useState<ResolvedTheme | null>(readStoredChoice);

  const theme: ResolvedTheme = canChoose ? (choice ?? defaultTheme) : defaultTheme;

  // Before paint, not after: the pre-paint script can only replay a theme this browser has already
  // resolved once, so a first-time visitor starts with no class at all. A passive effect would let
  // that first commit paint in the wrong palette and then snap.
  useLayoutEffect(() => {
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
