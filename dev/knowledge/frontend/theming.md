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

### Theme-varying vs theme-invariant: `@theme inline` vs `@theme`

The distinction matters and gets this wrong silently, so it is worth stating plainly:

| Form | Emits the custom property? | Generates a utility? | Use it for |
|---|---|---|---|
| `:root`/`.dark` + `--color-x: var(--x)` in `@theme inline` | yes, from `:root`/`.dark` | yes | anything whose **value differs per theme** |
| plain `@theme { --height-page-body: … }` | yes | yes | **theme-invariant** scales — dimensions, timings, type steps |
| plain `:root { --x: … }` alone | yes | **no** | a helper var read from inside a `calc()`, with no utility of its own |

**The trap:** putting a theme-varying value in a plain `@theme` block bakes it into the utility at
build time, and the `.dark` override becomes dead CSS. Nothing fails — the class is still emitted,
the markup still looks right, and only the rendered pixels are wrong in one theme. A theme-varying
token must be declared in `:root` **and** `.dark`, then bridged through `@theme inline`.
`count-badge.test.tsx` guards exactly this for `--inset-shadow-raised`, by comparing the computed
inset layer between themes rather than the class string.

### Non-colour token families

`theme.css` is not colour-only. A plain `@theme` block at the end holds the theme-invariant scales,
because `.dark` has no business overriding a dimension:

| Token | Utility | What it encodes |
|---|---|---|
| `--text-xxs` | `text-xxs` | One step below `text-xs`, for dense metadata. Carries **no** `--text-xxs--line-height`: adding one changes every existing call site |
| `--detail-label-width` | — (helper) | The term column of a definition-style row; read from inside a surviving `minmax()` |
| `--grid-template-columns-detail-row` | `grid-cols-detail-row` | That column plus `auto` |
| `--height-page-body` / `-tabs` | `h-page-body` / `h-page-body-tabs` | Viewport minus the page chrome; the `-tabs` variant for shells with their own tab row |
| `--inset-filter-tab` | `-top-filter-tab` | Offset of the labelled tab above a filter popover |
| `--animate-skeleton` | `animate-skeleton` | Skeleton pulse. Owns its keyframes, so it works with `tailwindcss-animate` disabled (as it is under CI) |

### Status, diff and accent families

Four status families, each with a foreground, a `-surface` tint, and where it exists a `-strong`
fill one step hotter than the foreground:

| Family | Hue | Extra members |
|---|---|---|
| `--success` | green | `-surface`, `-strong` |
| `--warning` | amber | `-surface`, `-strong`, `-border` |
| `--info` | sky | `-surface` |
| `--danger` | rose | `-surface`, `-strong` |

The light values follow one recipe — foreground `-700`, `-surface` as `--alpha(-500 / 15%)`. The
dark values are tuned per family, so **take every value from `theme.css`; do not derive it.**

Pick the hue by role, not by appearance:

- Warning is amber. Do not reach for yellow.
- Info is sky. Cyan belongs to `--accent` and `--ring`; blue-violet belongs to `--active`.
- Brand is `--accent`, with `--accent-surface` for a pale tint, `--accent-strong` for a saturated
  fill, and `--accent-foreground` for text on that fill.

**Diff status is its own family, not the status palette.** Use `--diff-added` / `-removed` /
`-updated` / `-conflict` (each with a `-surface`) for anything in a diff view. Its members are read
against each other in one viewport, and a removal is a successful operation — so `--danger` is the
wrong token for it, and retuning error states must not restyle diffs.

## How dark mode switches on

The `dark` class on `document.documentElement` is the only switch. The primitives live in the
design system (`frontend/packages/ui/src/theme/`), so anything built on `@infrahub/ui` can read and
offer the theme; the application owns only the *policy* that decides it. Three things manage the
class:

1. **The pre-paint script** in `frontend/app/index.html` — a blocking inline script in `<head>`
   that applies the class before the first frame, from the `infrahub.theme.resolved` localStorage
   mirror. It is deliberately outside the module graph (it must run before any bundle loads), so
   the storage key is duplicated there verbatim — renaming the key means changing both files in
   the same commit.
2. **`ThemeProvider`** (`frontend/app/src/entities/config/ui/theme-provider.tsx`) — the policy.
   Decides the real theme once config arrives: the `dark_theme` experimental flag gates whether
   dark is offered at all, `infrahub.theme.choice` holds this browser's explicit choice, and the
   resolved outcome is applied to the class and mirrored back to storage (`applyTheme` and the
   storage helpers come from `@infrahub/ui`). It fills the design system's `ThemeContext`, which is
   what makes `ThemeSwitchMenuItem` — the ready-made switch a menu can drop in — render and work.
   An absent flag (backend predates it) counts as enabled under a Vite dev server only — see
   `entities/config/domain/rules/can-offer-dark-theme.ts`. A browser with no stored choice follows
   the desktop's `prefers-color-scheme`; a Vite dev server overrides that to dark so whoever is
   working on the theme has it on screen — see
   `entities/config/domain/rules/get-default-theme.ts`.
3. **`useResolvedTheme`** (from `@infrahub/ui`) — how components *read* the current theme: a
   `useSyncExternalStore` subscription to the class via MutationObserver. Components never read
   storage or config for this; the document element is the single source of truth.

The deployment gate is `INFRAHUB_EXPERIMENTAL_DARK_THEME`, in the shared config block of both
compose files: `development/docker-compose.yml` defaults it to `true` and the root compose file to
`false`, so our own stacks carry the theme and a shipped deployment stays without it until an
operator opts in.

## Content that carries its own colours

Three renderers bake colours into their output and cannot be themed by CSS tokens:

- **Mermaid diagrams** — themed through `mermaid.initialize({ theme })`, called from a small rehype
  plugin sequenced before the rendering plugin
  (`shared/components/editor/markdown/markdown-with-mermaid.tsx`). The rendering plugin's own
  `mermaidConfig` option is silently ignored by its browser build; its documentation says to call
  `initialize` manually, and the browser build renders against that same global config. Two traps
  worth knowing: the `mermaid` version range must stay compatible with the one `mermaid-isomorphic`
  declares (two instances in the tree would mean configuring the wrong one), and the call must live
  *inside* the pipeline — a render-phase call is dropped by the React Compiler, and an effect races
  the child's async processing. A diagram's own `%%{init}%%` directive still wins, by mermaid's own
  precedence.
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
| Mermaid renders in the active theme, reacts to a flip, author directive wins | `shared/components/editor/markdown/markdown-with-mermaid.test.tsx` (asserts the colours baked into the real SVG) |
| First-paint, persistence, flag-off journeys | `tests/e2e/test_theme.py` (pytest-playwright, needs a stack) |
| Docs screenshots stay light | pinned in `tests/e2e/helpers.py::save_screenshot_for_docs` |

The design-system package has no test runner, so tests for its theme primitives are hosted in the
application suite. The pre-paint script itself is reachable only by the e2e suite — it sits outside
the module graph, so no vitest test can import it.
