# Design System (`@infrahub/ui`)

> Part of: `dev/knowledge/frontend/`

Location: `frontend/packages/ui/`

`@infrahub/ui` is the in-repo design-system package. Components live there once they are stable, accessible, themeable, and shared across the app, Storybook, and any future surfaces (admin UI, embedded views, docs site).

The package is published locally via the workspace and consumed in `frontend/app` as `@infrahub/ui`.

## What's in the package today

| Component | Exports | Notes |
|---|---|---|
| `Button` | `Button`, `LinkButton`, `buttonVariants`, `ButtonProps`, `LinkButtonProps` | Migrated in #9065. Replaces ad-hoc `<button>` with Tailwind classes. |
| `Card` | `Card`, `CardHeader`, `CardContent`, `CardProps`, `CardHeaderProps`, `CardContentProps` | Migrated in #9048. Replaces hand-rolled `<section className="rounded-md border bg-white p-4 shadow-lg">` patterns. |
| `Modal` | `Modal`, `ModalOverlay`, `ModalProps`, `ModalOverlayProps` | Migrated in #9088. Use instead of HeadlessUI Dialog for new modals. |
| `Spinner` | `Spinner`, `SpinnerProps` | Loading indicator. |
| `Meter` | `Meter`, `MeterProps` | Migrated in #9100. Replaces ad-hoc progress-bar charts. |
| `ScrollArea` | `ScrollArea`, `ScrollAreaProps` | Migrated in #9101. Replaces `shared/components/ui/scroll-area`. |
| `IconButton` | `IconButton`, `IconButtonProps` | Square ghost icon button wrapping `Button`; `aria-label` required. |
| `Toolbar` | `Toolbar`, `Toolbar.Divider`, `ToolbarProps`, `ToolbarDividerProps` | Floating toolbar container (`role="toolbar"`, `aria-label` required) + vertical divider. |
| `FloatingPanel` | `FloatingPanel`, `FloatingPanelProps` | Floating overlay built on `Card` + `IconButton`: header (title/description/close) + scroll body; optional `dismissable` (outside-click + Escape). |
| `useDismiss` | `useDismiss` | Hook — outside-pointerdown + Escape dismissal. |

Source of truth: `frontend/packages/ui/src/index.ts`.

## How the package is consumed (resolution + styling)

- **Consumed from source, not built output.** `frontend/app` resolves `@infrahub/ui` to its TypeScript source — `package.json` `main` is `./src/index.ts` and the subpath exports point at `.tsx` files. The app's own Vite/Tailwind build compiles them. Consequence: the app never needs `@infrahub/ui` to be pre-built, and the package's own `pnpm build` (`tsc -b && vite build`) is independent of app builds and tests.
- **Cross-package Tailwind scanning.** Because components ship as source, each consumer's Tailwind build must *scan* the package source to emit its utility classes. The app does this via an `@source` directive in `frontend/app/src/app/styles/index.css`. The `schema-visualizer` submodule does **not** by default — it's a separate repo that builds a self-contained IIFE (`vite.config.webview.ts`, `external: []`). To consume `@infrahub/ui` there you must add both the dependency (`"@infrahub/ui": "file:../ui"`) **and** `@source "../../ui/src/**/*.{ts,tsx}";` to `frontend/packages/schema-visualizer/src/webview.css` — without the `@source` line the imported components bundle but render **unstyled**.

## When to consume from `@infrahub/ui`

Always, for the components above. Do not reimplement them inline in feature code, even if it "feels lighter":

- Card visual: bordered + rounded + shadow + padded surface.
- Button visual: any clickable styled button.
- Modal: any dialog/overlay.
- Spinner: any loading indicator.

If a component needs a slot the package doesn't expose yet, **extend the package** rather than forking the markup in feature code. Open a PR against `frontend/packages/ui/`.

## When to consume from `shared/components/ui/`

`frontend/app/src/shared/components/ui/` contains primitives that have not yet been migrated. They are still the canonical implementation for now. Examples: `combobox`, `popover`, `tooltip`, `dropdown-menu`, `badge`, `alert`, `accordion`, `pagination`, `resizable`, `command`.

When you touch one of these and notice it could be a generic primitive, consider migrating it to `@infrahub/ui` as part of the change.

## Migration policy

- Net-new generic primitives (no Infrahub-specific data dependencies) should land in `@infrahub/ui` from day one.
- Existing primitives in `shared/components/ui/` are migrated incrementally — see PRs #9048 (Card), #9065 (Button), #9088 (Modal) as references.
- Migration PRs include: the component, its Storybook story, focus-visible styles, and call-site updates across the app.

## Storybook

Each migrated component ships with a `*.stories.tsx`. Run Storybook from `frontend/packages/ui/` to preview variants before consuming. Stories double as the contract documentation: if a variant isn't in the story, treat it as not-yet-supported.

## Anti-patterns

| Anti-pattern | Why it's wrong |
|---|---|
| Re-implementing the card shell inline (`<section className="rounded-md border …">`) | Drift between callers, no shared theming, no a11y review. Use `Card` from `@infrahub/ui`. |
| Wrapping `Button` from `@infrahub/ui` to add a single class | Use `className` prop or extend variants in the package. |
| Importing `Button` / `Card` / `Modal` / `Spinner` from anywhere except `@infrahub/ui` | The shared packages are deduplicated for a reason — bundle size and styling consistency. |
| Adding a one-off `<dialog>` because Modal feels heavy | Use `Modal` — it handles focus trap, escape, and overlay. |

## Discovery commands

```bash
# What's exported from @infrahub/ui?
cat frontend/packages/ui/src/index.ts

# What components have Storybook stories?
ls frontend/packages/ui/src/components/*/

# Where in the app is a primitive consumed?
rg "from \"@infrahub/ui\"" frontend/app/src
```

## See also

- `dev/knowledge/frontend/shared-components.md` — full primitive inventory
- `dev/guidelines/frontend/styling.md` — Tailwind, CVA, layout primitives
- `dev/guidelines/frontend/component-patterns.md` — early-return + extraction patterns
