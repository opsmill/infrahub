/** The palette actually in effect. Always concrete — a "follow the system" choice is resolved away
 * before it reaches here, so every consumer gets an answer it can render without asking the browser
 * anything.
 *
 * Lives in `shared` because generic components follow the theme too, and `shared` must not depend on
 * where preferences come from. The React context that carries this value lands alongside it. */
export type ResolvedTheme = "light" | "dark";
