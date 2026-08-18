# Theming

> Part of: `dev/knowledge/frontend/` | Related: [Styling Guidelines](../../guidelines/frontend/styling.md)

How the light and dark themes work, and how to change them safely. The short version: every colour
the app paints should resolve through a semantic token defined once per theme in a single file, and
dark mode is nothing more than a `dark` class on the document element swapping those definitions.

## Where colours live

`frontend/packages/ui/src/styles/theme.css` is the single source of truth. It has three parts, and
a colour change touches one, two, or three of them depending on the change:

| Block | What it holds |
|---|---|
| `:root { … }` | The light palette: one custom property per semantic token, plus `color-scheme: light` |
| `.dark { … }` | The dark palette: the **same property names** with dark values, plus `color-scheme: dark` |
| `@theme inline { … }` | The Tailwind bridge: `--color-<name>: var(--<name>)` lines that turn each token into utilities (`bg-<name>`, `text-<name>`, `ring-<name>`, …) |

### Change a colour in dark only

Edit its value inside the `.dark` block. Nothing else — no component changes, no `dark:` variants,
no light-theme risk, because the light value in `:root` is untouched.

### Change a colour in both themes

Edit the token's value in `:root` and in `.dark`. Every call site follows.

### Add a new token

Three edits in `theme.css`: a light value in `:root`, a dark value in `.dark`, and a
`--color-<name>: var(--<name>);` line in `@theme inline`. Then use `bg-<name>` / `text-<name>`
etc. in components. Name the token for its **role** (`--active`, `--danger-surface`, `--content`),
never its colour — a token called `--indigo` cannot honestly hold anything else.

Paired tokens follow the `X` / `X-surface` convention (`--danger` / `--danger-surface`,
`--active` / `--active-surface`): the bare name is the foreground/stroke, `-surface` is the tinted
background behind it.

## How dark mode switches on

The `dark` class on `document.documentElement` is the only switch. Three things manage it:

1. **The pre-paint script** in `frontend/app/index.html` — a blocking inline script in `<head>`
   that applies the class before the first frame, from the `infrahub.theme.resolved` localStorage
   mirror. It is deliberately outside the module graph (it must run before any bundle loads), so
   the storage key is duplicated there verbatim — renaming the key means changing both files in
   the same commit.
2. **`ThemeProvider`** (`frontend/app/src/entities/config/ui/theme-provider.tsx`) — decides the
   real theme once config arrives: the `dark_theme` experimental flag gates whether dark is offered
   at all, `infrahub.theme.choice` holds this browser's explicit choice, and the resolved outcome
   is applied to the class and mirrored back to storage. An absent flag (backend predates it)
   counts as enabled under a Vite dev server only — see
   `entities/config/domain/rules/can-offer-dark-theme.ts`.
3. **`useResolvedTheme`** (`frontend/app/src/shared/hooks/use-resolved-theme.ts`) — how components
   *read* the current theme: a `useSyncExternalStore` subscription to the class via
   MutationObserver. Components never read storage or config for this; the document element is the
   single source of truth.

The deployment gate is `INFRAHUB_EXPERIMENTAL_DARK_THEME`, passed through in
`development/docker-compose.yml` only (default `true` there). The root compose file deliberately
has no passthrough while the theme is alpha.

## Content that carries its own colours

Three renderers bake colours into their output and cannot be themed by CSS tokens:

- **Mermaid diagrams** — themed by prefixing each diagram with an `%%{init}%%` directive
  (`shared/components/editor/markdown/mermaid-theme.ts`). The rehype plugin's `mermaidConfig` is
  silently ignored by its browser build, so the diagram source is the only working channel.
- **GraphiQL** — has its own theme; the sandbox page passes the app's resolved theme through
  `forcedTheme` so it can never disagree with the app around it.
- **Schema-defined colours** (role badges, kind palettes, user-picked hex values) — data, not
  style. Rendered as-is in both themes; out of scope for tokens.

## When a `dark:` variant is acceptable

Almost never — a fixed palette class (`bg-white`, `bg-gray-50`) is a bug even when it *looks* fine
in light, and pairing it with a `dark:` override duplicates per call site what a token defines
once. The two legitimate exceptions, both from
[Styling Guidelines](../../guidelines/frontend/styling.md):

- No token can express the difference — swapping assets, dark-only effects (backdrop blur).
- Categorical ramps where the hue carries no meaning (the sidebar avatar colours): there is no
  semantic name to give a token, and the ramp has a single definition site, so the duplication a
  token prevents cannot arise.

## Verifying a colour change

- **Contrast**: WCAG AA needs 4.5:1 for normal text, 3:1 for large text and UI parts. Measure
  against the surface the element *actually sits on*, compositing translucent layers — a mid-ramp
  shade that passes on one theme's background usually fails on the other's (that is why `--active`
  holds `indigo-700` in light but `indigo-400` in dark).
- **Probing gotcha**: Tailwind only generates classes that appear in source. A class assembled
  dynamically in a devtools probe (`bg-${hue}-400/15`) silently resolves to nothing and reads as
  transparent — probe with the exact class strings the component ships.
- **Both themes, always**: toggle via the account-menu switch, or
  `document.documentElement.classList.toggle("dark")` in the console. The light theme is the
  shipped default; a dark fix must not move light pixels unless that is the intent.

## Test coverage

| Concern | Test |
|---|---|
| Flag/choice resolution, retention across flag flips | `entities/config/ui/theme-provider.test.tsx`, `entities/config/domain/rules/can-offer-dark-theme.test.ts` |
| Reading the theme from the class | `shared/hooks/use-resolved-theme.test.tsx` |
| The switch in the account menu, alpha tag, gating | `entities/user-profile/ui/account-menu.test.tsx` |
| Mermaid directive injection, nested-fence safety | `shared/components/editor/markdown/mermaid-theme.test.ts` |
| First-paint, persistence, flag-off journeys | `tests/e2e/theme.spec.ts` (Playwright, needs a stack) |
| Docs screenshots stay light | pinned in `tests/utils.ts` |

The pre-paint script itself is reachable only by the e2e suite — it sits outside the module graph,
so no vitest test can import it.
