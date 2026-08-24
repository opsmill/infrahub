# Design System (`@infrahub/ui`)

> Part of: `dev/knowledge/frontend/`

Location: `frontend/packages/ui/`

`@infrahub/ui` is the in-repo design-system package. Components live there once they are stable, accessible, themeable, and shared across the app, Storybook, and any future surfaces (admin UI, embedded views, docs site).

The package is published locally via the workspace and consumed in `frontend/app` as `@infrahub/ui`.

## What's in the package today

Most components wrap `react-aria-components` primitives with Tailwind styling. Compact inventory — one row per component family, `*Props` type exports elided:

| Component family | Purpose |
|---|---|
| `Button` / `LinkButton` | Any clickable styled button (+ `buttonVariants`). Migrated in #9065. |
| `Card` (`CardHeader`, `CardContent`) | Bordered + rounded + shadowed content surface. Migrated in #9048. |
| `Modal` (`ModalOverlay`) | Dialog/overlay with focus trap and escape handling. Migrated in #9088. |
| `Sheet` | Side-panel overlay; integrates the dismiss guard (see hooks below). |
| `Popover` (`PopoverDialog`, `PopoverTrigger`) | React-aria popover. See the app-popover duality note below. |
| `Tooltip` | Hover/focus tooltip with arrow; supports non-interactive triggers. |
| `Menu` (`MenuItem`, `MenuSection`, `MenuTrigger`) | Dropdown menu. |
| `Breadcrumbs` (`Breadcrumb`, `BreadcrumbItem`, loading/error variants) | Trail of links/buttons with `/` separator. |
| `Select` (`SelectTrigger`, `SelectList`, `SelectItem`) | Styled select built on `ListBox` + `Popover`. |
| `ListBox` (`ListBoxItem`, `ListBoxLoadMoreItem`) | Virtualized option list with load-more support. |
| `Autocomplete` | Search field filtering a wrapped collection (react-aria `useFilter`). |
| `Checkbox`, `CheckboxCard`, `Label` | Form field primitives; `CheckboxCard` is a card-style selectable choice. |
| `Tree` (`TreeItem`, `TreeItemContent`, `TreeItemLoader`) | Expandable tree with lazy loading. |
| `SortableList` / `SortableItem` | Drag-and-drop reorderable list (react-aria `useDragAndDrop`). |
| `ResizablePanelGroup` / `ResizablePanel` / `ResizableHandle` | Split panes built on `react-resizable-panels`. |
| `ScrollArea` | Styled scroll container. Migrated in #9101. |
| `Meter` | Progress/utilization bar. Migrated in #9100. |
| `Spinner` | Loading indicator. |
| `DismissGuardContext` / `useDismissGuard` | Hook + context to block overlay dismissal (used by `Sheet`; consumers such as dirty forms mark themselves undismissable). |

This table is a snapshot. Source of truth: `frontend/packages/ui/src/index.ts` — regenerate the inventory from it rather than trusting the table.

## How the package is consumed (resolution + styling)

- **Consumed from source, not built output.** `frontend/app` resolves `@infrahub/ui` to its TypeScript source — `package.json` `main` is `./src/index.ts`, and the `exports` map has only two entries: `.` → `./src/index.ts` and `./styles.css` → `./src/index.css`. The app's own Vite/Tailwind build compiles the source. Consequence: the package has no build script at all (its `scripts` cover Storybook, Chromatic, dev, format, and lint only) — building `frontend/app` is the verification path for package changes.
- **Cross-package Tailwind scanning.** Because components ship as source, each consumer's Tailwind build must *scan* the package source to emit its utility classes. The app does this via an `@source` directive in `frontend/app/src/app/styles/index.css`. The `schema-visualizer` submodule does **not** by default — it's a separate repo that builds a self-contained IIFE (`vite.config.webview.ts`, `external: []`). To consume `@infrahub/ui` there you must add both the dependency (`"@infrahub/ui": "file:../ui"`) **and** `@source "../../ui/src/**/*.{ts,tsx}";` to `frontend/packages/schema-visualizer/src/webview.css` — without the `@source` line the imported components bundle but render **unstyled**.

## Sibling package: `@infrahub/graph`

`frontend/packages/graph` (`@infrahub/graph`) is a second workspace package for **graph-view primitives** that compose `@infrahub/ui`. It is consumed the same way (from source, `workspace:*`) and is itself a `@infrahub/ui` consumer, so the app's `@source` directive must also scan `packages/graph/src`.

| Component | Exports | Notes |
|---|---|---|
| `Toolbar` | `Toolbar`, `Toolbar.Divider`, `ToolbarProps`, `ToolbarDividerProps` | Floating toolbar container built on react-aria's `Toolbar` (`aria-label` required): one tab stop, arrow keys move between controls. + vertical divider. |
| `FloatingPanel` | `FloatingPanel`, `FloatingPanelProps` | Floating overlay built on `Card` + a ghost square `Button`: header (title/description/close) + scroll body; optional `dismissable` (outside-click + Escape). |
| `ExportMenu` | `ExportMenu`, `ExportFormat`, `ExportMenuProps` | PNG/SVG export popover. |
| `GraphControls` | `GraphControls`, `GraphControlsProps`, `EdgeStyle`, `LayoutDirection` | Zoom / fit / edge-style / layout controls; uses `useReactFlow` from `@xyflow/react`. |
| `useDismiss` | `useDismiss` | Hook — outside-pointerdown + Escape dismissal. |

Source of truth: `frontend/packages/graph/src/index.ts`. Adopted by `path-traversal`.

A third directory exists under `frontend/packages/`: `plugins/` holds a single standalone Vite + module-federation plugin template (`plugins/template`) that is **not** a pnpm workspace member (the workspace lists `app`, `packages/schema-visualizer`, `packages/ui`, and `packages/graph`) and is unrelated to the design system.

## When to consume from `@infrahub/ui`

Always, for the components above. Do not reimplement them inline in feature code, even if it "feels lighter":

- Card visual: bordered + rounded + shadow + padded surface.
- CheckboxCard visual: selectable card choice with checkbox semantics.
- Button visual: any clickable styled button.
- Modal: any dialog/overlay.
- Spinner: any loading indicator.

If a component needs a slot the package doesn't expose yet, **extend the package** rather than forking the markup in feature code. Open a PR against `frontend/packages/ui/`.

## When to consume from `shared/components/ui/`

`frontend/app/src/shared/components/ui/` contains primitives that have not yet been migrated. They are still the canonical implementation for now. Examples: `combobox`, `popover`, `dropdown-menu`, `badge`, `alert`, `accordion`, `pagination`, `command` (`tooltip` and `resizable` have already moved to `@infrahub/ui`).

**Popover exists in both places.** `shared/components/ui/popover.tsx` is Radix-based (`@radix-ui/react-popover`), adds `PopoverAnchor` and `PopoverTabs*` subcomponents, and marks its content with `data-react-aria-top-layer` so clicking inside it does not count as an outside interaction for an enclosing react-aria overlay such as the package `Sheet`. `@infrahub/ui` exports a separate react-aria `Popover` / `PopoverDialog` / `PopoverTrigger`. Both are actively used in the app (roughly 23 vs 26 importing files); the dismiss guard itself lives in `@infrahub/ui` (`Sheet` + `useDismissGuard`), not in either popover.

When you touch one of these and notice it could be a generic primitive, consider migrating it to `@infrahub/ui` as part of the change.

## Migration policy

- Net-new generic primitives (no Infrahub-specific data dependencies) should land in `@infrahub/ui` from day one.
- Existing primitives in `shared/components/ui/` are migrated incrementally — Card, Button, and Modal are migrated precedents.
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
