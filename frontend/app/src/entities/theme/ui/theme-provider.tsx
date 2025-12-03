import React, { useCallback, useSyncExternalStore } from "react";

import { THEME_KEY, type Theme } from "@/entities/theme/constants";

export type ThemeContextType = {
  theme: Theme;
  resolvedTheme: "light" | "dark";
  setTheme: (theme: Theme) => void;
};

export const ThemeContext = React.createContext<ThemeContextType>({
  theme: "system",
  resolvedTheme: "light",
  setTheme: () => {},
});

function getSystemTheme(): "light" | "dark" {
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function getStoredTheme(): Theme {
  if (typeof window === "undefined") return "system";
  const stored = localStorage.getItem(THEME_KEY);
  if (stored === "light" || stored === "dark" || stored === "system") {
    return stored;
  }
  return "system";
}

function applyTheme(theme: "light" | "dark") {
  const root = document.documentElement;
  if (theme === "dark") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
}

function subscribe(callback: () => void) {
  const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
  mediaQuery.addEventListener("change", callback);
  window.addEventListener("storage", callback);
  return () => {
    mediaQuery.removeEventListener("change", callback);
    window.removeEventListener("storage", callback);
  };
}

function getSnapshot(): { theme: Theme; resolved: "light" | "dark" } {
  const theme = getStoredTheme();
  const resolved = theme === "system" ? getSystemTheme() : theme;
  applyTheme(resolved);
  return { theme, resolved };
}

function getServerSnapshot(): { theme: Theme; resolved: "light" | "dark" } {
  return { theme: "system", resolved: "light" };
}

let cachedSnapshot = getSnapshot();

function getCachedSnapshot() {
  const newSnapshot = getSnapshot();
  if (
    newSnapshot.theme !== cachedSnapshot.theme ||
    newSnapshot.resolved !== cachedSnapshot.resolved
  ) {
    cachedSnapshot = newSnapshot;
  }
  return cachedSnapshot;
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const { theme, resolved } = useSyncExternalStore(subscribe, getCachedSnapshot, getServerSnapshot);

  const setTheme = useCallback((newTheme: Theme) => {
    localStorage.setItem(THEME_KEY, newTheme);
    const resolved = newTheme === "system" ? getSystemTheme() : newTheme;
    applyTheme(resolved);
    cachedSnapshot = { theme: newTheme, resolved };
    window.dispatchEvent(new Event("storage"));
  }, []);

  const value: ThemeContextType = {
    theme,
    resolvedTheme: resolved,
    setTheme,
  };

  return <ThemeContext value={value}>{children}</ThemeContext>;
}

export function useTheme() {
  const context = React.use(ThemeContext);

  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider.");
  }

  return context;
}
