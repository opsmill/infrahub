type ExperimentalFeatures = { dark_theme?: boolean } | null | undefined;

/**
 * Whether this deployment offers the dark theme.
 *
 * An absent flag is not the same as a false one. False is an operator saying no, and always wins.
 * Absent means the backend predates the flag — and a frontend dev server pointed at such a backend
 * is still a development environment, whose default should be the theme being worked on. In a
 * production build the dev-server bit is statically false, so an old backend keeps built frontends
 * on light.
 */
export function canOfferDarkTheme(
  experimentalFeatures: ExperimentalFeatures,
  isDevServer: boolean
): boolean {
  return experimentalFeatures?.dark_theme ?? isDevServer;
}
