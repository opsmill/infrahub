import type { ResolvedTheme } from "@/shared/hooks/use-resolved-theme";

const DARK_CLASS = "dark";

/**
 * The class on the document element is the app's single theme switch: every token in the stylesheet
 * keys off it, and reading it back is how components learn the current theme.
 */
export function applyTheme(theme: ResolvedTheme): void {
  document.documentElement.classList.toggle(DARK_CLASS, theme === "dark");
}
