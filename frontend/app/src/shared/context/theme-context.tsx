import { createContext, use } from "react";

import type { ResolvedTheme } from "@/shared/hooks/use-resolved-theme";

export type ThemeControl = {
  /**
   * Whether this deployment offers a theme at all. False hides the control outright rather than
   * disabling it: a visible switch that cannot be used reads as a bug, and offering a choice the
   * deployment will not honour is worse than offering none.
   */
  canChoose: boolean;
  setTheme: (theme: ResolvedTheme) => void;
};

/** The default leaves the app light and the control hidden, which is what an unwired tree should do. */
export const ThemeContext = createContext<ThemeControl>({
  canChoose: false,
  setTheme: () => {},
});

export function useThemeControl(): ThemeControl {
  return use(ThemeContext);
}
