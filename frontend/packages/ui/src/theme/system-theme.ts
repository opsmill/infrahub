import { useSyncExternalStore } from "react";

import type { ResolvedTheme } from "./resolved-theme";

const DARK_QUERY = "(prefers-color-scheme: dark)";

function subscribe(onStoreChange: () => void): () => void {
  const query = globalThis.matchMedia(DARK_QUERY);
  query.addEventListener("change", onStoreChange);
  return () => query.removeEventListener("change", onStoreChange);
}

function getSnapshot(): ResolvedTheme {
  return globalThis.matchMedia(DARK_QUERY).matches ? "dark" : "light";
}

/**
 * The appearance the operating system asks for, kept live: a desktop flipped between light and
 * dark re-renders whoever reads this. Reporting a preference is all it does — whether that
 * preference is worth honouring is the caller's decision.
 */
export function useSystemTheme(): ResolvedTheme {
  return useSyncExternalStore(subscribe, getSnapshot, () => "light");
}
