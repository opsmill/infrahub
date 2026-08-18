import { MoonIcon, SunIcon } from "lucide-react";

import { MenuItem } from "../components/menu/menu";
import { useResolvedTheme } from "./resolved-theme";
import { useThemeControl } from "./theme-context";

/**
 * A menu item that switches to the theme the page is not currently painting. Connected through
 * {@link useThemeControl}, so it renders nothing until a provider fills the context and says the
 * deployment offers a choice — an application only has to place it inside a Menu.
 *
 * Carries a visible "alpha" tag while the dark theme is pre-release.
 */
export function ThemeSwitchMenuItem() {
  const { canChoose, setTheme } = useThemeControl();
  const theme = useResolvedTheme();

  if (!canChoose) {
    return null;
  }

  const isDark = theme === "dark";

  return (
    <MenuItem onAction={() => setTheme(isDark ? "light" : "dark")}>
      {isDark ? <SunIcon /> : <MoonIcon />}
      {isDark ? "Light theme" : "Dark theme"}
      <span className="ml-auto rounded-md border border-transparent bg-yellow-100 px-1.5 py-0.5 text-xs font-semibold text-yellow-900 dark:bg-yellow-400/20 dark:text-yellow-300">
        alpha
      </span>
    </MenuItem>
  );
}
