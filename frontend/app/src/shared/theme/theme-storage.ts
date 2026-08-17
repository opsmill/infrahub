import type { ResolvedTheme } from "@/shared/hooks/use-resolved-theme";

/**
 * ⚠ These two keys are repeated verbatim in the pre-paint script in `index.html`. That script runs
 * before the module graph exists and so cannot import them; changing a name here means changing it
 * there in the same commit, or a reload flashes the wrong palette.
 */
const CHOICE_KEY = "infrahub.theme.choice";
const RESOLVED_KEY = "infrahub.theme.resolved";

function read(key: string): ResolvedTheme | null {
  try {
    const stored = localStorage.getItem(key);
    return stored === "dark" || stored === "light" ? stored : null;
  } catch {
    // Storage is unavailable in Safari private browsing and behind some privacy settings. The theme
    // still applies for this page; it just will not survive a reload.
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
 * Records what the app actually settled on, which is what the pre-paint script reads when the user
 * has expressed no choice of their own. Without it, a reload cannot know the feature flag's value
 * until the config request returns, and would have to guess.
 */
export function mirrorResolvedTheme(theme: ResolvedTheme): void {
  write(RESOLVED_KEY, theme);
}
