import React from "react";

import { type ResolvedTheme, type Theme, ThemeSchema } from "@/entities/config/domain/model/theme";
import { useFeatureFlag } from "@/entities/config/ui/hooks/use-feature-flag";
import { useSystemTheme } from "@/entities/config/ui/hooks/use-system-theme";

const THEME_STORAGE_KEY = "infrahub.theme.choice";

interface ThemeContextValue {
  /** The user's choice. */
  theme: Theme;
  /** The palette actually painted. */
  resolvedTheme: ResolvedTheme;
  setTheme: (theme: Theme) => void;
}

export const ThemeContext = React.createContext<ThemeContextValue>({
  theme: "light",
  resolvedTheme: "light",
  setTheme: () => {},
});

function readStoredTheme(): Theme | null {
  try {
    const parsedTheme = ThemeSchema.safeParse(localStorage.getItem(THEME_STORAGE_KEY));
    return parsedTheme.success ? parsedTheme.data : null;
  } catch {
    // Storage throws when the user blocks site data.
    return null;
  }
}

function writeStoredTheme(theme: Theme): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Blocked site data or a full quota: the theme still applies to this page but will not survive a reload.
  }
}

function paint(theme: ResolvedTheme): void {
  const root = document.documentElement;
  const isDark = theme === "dark";
  if (root.classList.contains("dark") === isDark) return;

  // Frozen transitions make every surface switch palette in the same frame.
  const freeze = document.createElement("style");
  freeze.textContent = "*,*::before,*::after{transition:none!important}";
  document.head.append(freeze);
  root.classList.toggle("dark", isDark);
  // Reading a computed value flushes styles while the freeze is still in place.
  getComputedStyle(root).getPropertyValue("opacity");
  setTimeout(() => freeze.remove(), 1);
}

/** This browser's stored choice, following changes made in other tabs. */
function useStoredTheme(): [Theme | null, (theme: Theme) => void] {
  const [storedTheme, setStoredTheme] = React.useState(readStoredTheme);

  React.useEffect(() => {
    const handleStorage = (event: StorageEvent) => {
      if (event.key === THEME_STORAGE_KEY || event.key === null) {
        setStoredTheme(readStoredTheme());
      }
    };
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  const storeTheme = (theme: Theme) => {
    writeStoredTheme(theme);
    setStoredTheme(theme);
  };

  return [storedTheme, storeTheme];
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const isDarkThemeEnabled = useFeatureFlag("dark_theme");
  const systemTheme = useSystemTheme();
  const [storedTheme, storeTheme] = useStoredTheme();

  const theme: Theme = isDarkThemeEnabled ? (storedTheme ?? "system") : "light";
  const resolvedTheme: ResolvedTheme = theme === "system" ? systemTheme : theme;

  // Before the browser paints, so no frame this provider commits shows the wrong palette.
  React.useLayoutEffect(() => {
    paint(resolvedTheme);
  }, [resolvedTheme]);

  return (
    <ThemeContext value={{ theme, resolvedTheme, setTheme: storeTheme }}>{children}</ThemeContext>
  );
}

export function useTheme(): ThemeContextValue {
  const context = React.use(ThemeContext);

  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider.");
  }

  return context;
}
