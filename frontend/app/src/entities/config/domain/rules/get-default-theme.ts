type Theme = "light" | "dark";

/**
 * What a user who has never picked a theme should see.
 *
 * The desktop's appearance, because a preference someone has already expressed to their operating
 * system beats any default we could invent for them. A frontend dev server is the exception: there
 * the point is that whoever is working on the theme has it on screen, which an OS-derived default
 * would give only to those already running a dark desktop.
 *
 * A deployment that does not offer dark is light, whatever the desktop asks for — the operating
 * system expresses a preference, not a permission.
 */
export function getDefaultTheme({
  canOfferDark,
  isDevServer,
  systemTheme,
}: {
  canOfferDark: boolean;
  isDevServer: boolean;
  systemTheme: Theme;
}): Theme {
  if (!canOfferDark) {
    return "light";
  }

  return isDevServer ? "dark" : systemTheme;
}
