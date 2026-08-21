import { useSyncExternalStore } from "react";

export type ResolvedTheme = "light" | "dark";

const DARK_CLASS = "dark";

/**
 * The class on the document element is the single theme switch: every token in the stylesheet keys
 * off it, and reading it back is how components learn the current theme. Whatever decides the theme
 * only ever has to set the class.
 */
export function applyTheme(theme: ResolvedTheme): void {
  document.documentElement.classList.toggle(DARK_CLASS, theme === "dark");
}

function subscribe(onStoreChange: () => void): () => void {
  const observer = new MutationObserver(onStoreChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  return () => observer.disconnect();
}

function getSnapshot(): ResolvedTheme {
  return document.documentElement.classList.contains(DARK_CLASS) ? "dark" : "light";
}

/**
 * The theme the page is currently painting. Reads the document element rather than any preference,
 * so a consumer can never disagree with what is on screen.
 */
export function useResolvedTheme(): ResolvedTheme {
  return useSyncExternalStore(subscribe, getSnapshot, () => "light");
}
