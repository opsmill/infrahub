# System inventory: instance badge and bar

## Covered

- `Badge` (`frontend/app/src/shared/components/ui/badge.tsx`), CVA variants `red`, `warning`
  (amber), `green`, `blue`, `purple`, `gray`, each with light and dark classes. Base: `rounded-md
  border px-1.5 py-0.5 font-semibold text-xs`.
- `Tooltip` from `@infrahub/ui` (`frontend/packages/ui/src/components/tooltip`): used in
  `preference-fields.tsx` for the (i) hint; carries the full label when the badge truncates.
- `Card variant="secondary"` (`@infrahub/ui`): the header shell in `app-header.tsx`
  (`h-12.5 flex-row items-center gap-2 p-2`).
- Theme tokens (`frontend/packages/ui/src/styles/theme.css`): `--danger`, `--warning-strong`,
  `--success`, `--info`, `--active` (indigo), `--foreground-muted`, each defined for light and dark.
  Purple has no semantic token; the Badge `purple` variant already uses the categorical ramp
  (`purple-100/800`, dark `purple-400/300`), which `dev/knowledge/frontend/theming.md` allows for
  a categorical hue with one definition site.
- `DetailRow` (`shared/components/display/detail-row`), `FormField`, `Form`, `FormSubmit`,
  `Combobox`: the Global preferences form rows (`preference-fields.tsx`, `global-preferences-form.tsx`).
- `Input` (`shared/components/ui/input`) for the label field.
- `InfrahubLogo` and the login card layout (`pages/login.tsx`: `max-w-sm flex-col items-center gap-6`).
- `AppLayout` (`pages/app-layout.tsx`): `h-screen` outer `p-0.5`, inner row `gap-0.5` with sidebar
  and a column of header + outlet. The bar mounts as the first child of the outer column.
- `useTitle` (`shared/hooks/useTitle.ts`): the only `document.title` writer.
- `useConfig()` (`entities/config/ui/config-provider.tsx`): public config loaded before first render;
  the badge and bar read `instance.label` and `instance.color` from it.

## Close

- `Badge` has no `indigo` variant. The `blue` variant maps to `custom-blue`, which is the Infrahub
  brand blue, not indigo. Adding an `indigo` variant on `--active` / `--active-surface` is one line.
- `Badge` is a `span` with no `title`/tooltip and no truncation. The instance badge wraps it with
  `max-w-* truncate` and a `Tooltip`.
- `Combobox` lists text items only; a color choice needs a swatch next to each name. The prototype
  renders a small `rounded-full` swatch in the item label; if `Combobox` cannot render a node as the
  item, a `Select` from `@infrahub/ui` or a radio group of swatches replaces it.
- `AppHeader` has no slot; the badge is added as a child in a fixed position. The test
  `app-header.test.tsx` asserts child order and changes with it.

## Missing

- A thin full-width color bar: no component. Four lines (`h-0.5` or `h-1` div with a `bg-*` token
  class per preset), rendered only when a color is set.
- A map from the preset enum to classes (badge variant + bar class): one `domain/rules` module.
- A prototype route: the app has no `_proto` route. The jam adds one top-level route without the
  app layout, because every direction changes the shell (header, bar, login page). Each direction
  renders its own shell copy (sidebar, header) with fake data. Marked `PROTOTYPE design-jam
  instance-badge` and deleted before implementation.

## Where the prototype mounts

Top-level route `/_proto/instance-badge`, outside `AppLayout`, with the history panel at panel
level (no `frame`), because every direction changes the shell. Directions render a copy of the
sidebar and header with worst-case data: a 32-character label (`zurich-west-2 PRODUCTION-MAIN`),
a long branch name, a deep breadcrumb, the sidebar collapsed and expanded, light and dark.
