import type { ResolvedTheme } from "./resolved-theme";

// The theme this browser was explicitly told to use, absent until the user has chosen.
const CHOICE_KEY = "infrahub.theme.choice";

/**
 * ⚠ Any pre-paint script must duplicate this key verbatim — such a script runs before the module
 * graph exists and cannot import it. Renaming the key means updating every pre-paint script in the
 * same commit, or a reload flashes the wrong palette. The application's copy lives in
 * `frontend/app/index.html`.
 */
const RESOLVED_KEY = "infrahub.theme.resolved";

function read(key: string): ResolvedTheme | null {
  try {
    const stored = localStorage.getItem(key);
    return stored === "dark" || stored === "light" ? stored : null;
  } catch {
    // Storage is unavailable in Safari private browsing and behind some privacy settings.
    // The theme still applies for this page; it just will not survive a reload.
    return null;
  }
}

function write(key: string, theme: ResolvedTheme): void {
  try {
    localStorage.setItem(key, theme);
  } catch {
    // See read().
  }
}

/** The theme this browser was explicitly told to use, or null when the user has never chosen. */
export function readStoredChoice(): ResolvedTheme | null {
  return read(CHOICE_KEY);
}

export function storeChoice(theme: ResolvedTheme): void {
  write(CHOICE_KEY, theme);
}

/**
 * Records what the app actually settled on, which is the pre-paint script's only source. The raw
 * choice would be the wrong thing to paint from: it may name a theme the deployment no longer
 * offers, whereas the mirror is written after that decision has been applied — so a deployment
 * that stopped offering dark reloads straight into light even for a user whose stored choice is
 * dark.
 */
export function mirrorResolvedTheme(theme: ResolvedTheme): void {
  write(RESOLVED_KEY, theme);
}
