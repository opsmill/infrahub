import { useSyncExternalStore } from "react";

/** The palette actually in effect. Always concrete — a "follow the system" choice is resolved away
 * before it reaches here, so every consumer gets an answer it can render without asking the browser
 * anything. */
export type ResolvedTheme = "light" | "dark";

const DARK_CLASS = "dark";

function subscribe(onStoreChange: () => void): () => void {
  const observer = new MutationObserver(onStoreChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  return () => observer.disconnect();
}

function getSnapshot(): ResolvedTheme {
  return document.documentElement.classList.contains(DARK_CLASS) ? "dark" : "light";
}

/**
 * Reads the active palette, for the surfaces that cannot express themselves in CSS alone — a
 * third-party component taking a theme prop, or a renderer that bakes colors into its output.
 *
 * Reads the document class rather than a preference, deliberately: that class is what the CSS
 * actually keys off, so a consumer of this hook cannot disagree with what the rest of the page has
 * already painted. Whatever decides the theme only has to set the class.
 */
export function useResolvedTheme(): ResolvedTheme {
  return useSyncExternalStore(subscribe, getSnapshot, () => "light");
}
