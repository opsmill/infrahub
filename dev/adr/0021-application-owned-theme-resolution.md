# 21. The application resolves the theme once and hands the answer down

**Status:** Accepted
**Date:** 2026-08-24
**Author:** @opsmill-team

**Source:** `dev/specs/archive/infp-46-dark-theme-completion/research.md` (R3, generalising R4 and R7)

## Context

Several things the application renders carry their own colours and cannot be themed by CSS tokens:
the GraphQL sandbox, Mermaid diagrams, and the schema visualizer, which lives in a separate
repository. Each has its own notion of a theme, and each will happily resolve
`prefers-color-scheme` on its own if handed the string `"system"`.

If more than one thing performs that resolution, they can disagree. A user whose desktop says dark
but who has explicitly chosen light would get a light application containing a dark GraphiQL — and
the disagreement is invisible until someone looks at the two side by side.

The same question arises for the application's own components: any of them could read
`prefers-color-scheme` directly rather than reading what is actually on screen.

## Decision

The theme is resolved in exactly one place — the application's `ThemeProvider` — and every consumer
receives the resolved answer, `"light"` or `"dark"`.

Three rules follow:

1. **`"system"` is never passed down.** The resolved theme type is the two-value union
   `ResolvedTheme = "light" | "dark"`; there is no third value to leak.
2. **Components read what is painted, not what is preferred.** `useResolvedTheme` subscribes to the
   `dark` class on the document element via `MutationObserver`, so a consumer cannot disagree with
   what is on screen.
3. **Reading the operating system's preference is separate from acting on it.** `useSystemTheme`
   reports `prefers-color-scheme` and holds no opinion; whether that preference wins is the
   application's policy, expressed in `entities/config/domain/rules/`.

## Consequences

### Positive

- Two surfaces cannot disagree about the theme, because only one of them ever decides.
- Deployment policy — whether dark is offered, what an unchosen user sees — is expressed once, in
  one layer, rather than being re-derived by each renderer.
- The design system holds no opinion on which theme a deployment should offer, so it stays reusable.

### Negative

- Every embedded renderer needs an explicit theme prop threaded to it, including one in another
  repository, whose support had to be added upstream and pulled in through a submodule bump.

### Neutral

- A renderer with no theme prop cannot participate, and must be handled as content that carries its
  own colours. `dev/knowledge/frontend/theming.md` enumerates those surfaces.

## Alternatives Considered

### Pass `"system"` down and let each renderer resolve it

Superficially simpler — no resolution step in the application. Rejected because a user on "match
system" would then be correct only by coincidence: any explicit choice, or any deployment-level
default, is invisible to a renderer doing its own media query. Resolving once and handing down the
answer is the only binding that cannot drift.

### Let components read `prefers-color-scheme` directly

Same failure with a wider blast radius, and it makes the stored choice unobservable to the very
components that render it.
