import React from "react";

import type { ResolvedTheme } from "@/entities/config/domain/model/theme";

const MEDIA_QUERY = "(prefers-color-scheme: dark)";

function subscribeToSystemTheme(onChange: () => void): () => void {
  const query = window.matchMedia(MEDIA_QUERY);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

function getSystemTheme(): ResolvedTheme {
  return window.matchMedia(MEDIA_QUERY).matches ? "dark" : "light";
}

export function useSystemTheme(): ResolvedTheme {
  return React.useSyncExternalStore(subscribeToSystemTheme, getSystemTheme);
}
