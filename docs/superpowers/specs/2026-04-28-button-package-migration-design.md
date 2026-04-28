# Button package migration

**Date:** 2026-04-28
**Branch:** `bab-migrate-button` (continues from the size+shape redesign already on this branch)
**Scope:** Move `frontend/app/src/shared/components/aria/button.tsx` and the `Spinner` component into `frontend/packages/ui` (`@infrahub/ui`), switch the Button's variant engine from `class-variance-authority` to `tailwind-variants`, and update all consumers.

## Context

The size+shape redesign of `Button` is already merged on this branch. The next step is to publish that Button (and `LinkButton`) from the shared `@infrahub/ui` package so it's the single canonical implementation. The package today contains an older, plain-HTML Button (`frontend/packages/ui/src/components/button/button.tsx`) that has nothing in common with the new react-aria-based Button. That older file is unused by the app and gets discarded.

The package already uses `tailwind-variants` for `Card` and (the soon-to-be-deleted) old Button, so adopting `tailwind-variants` here is consistent with the package's house style. The `tv()` API is a near drop-in for `cva()` — same `variants`, `compoundVariants`, and `defaultVariants` shape — and `tailwind-variants` exports `cn` which has the same `clsx + twMerge` semantics as the app's `classNames` util.

## Goals

1. Move `Button`, `LinkButton`, and `Spinner` into `@infrahub/ui` with full feature parity.
2. Convert the Button variants from `cva` to `tv` (with `cn`).
3. Delete the obsolete package Button (`packages/ui/src/components/button/button.tsx` + its stories).
4. Update all 129 `Button`/`LinkButton` consumers and 28 `Spinner` consumers to import from `@infrahub/ui`.
5. Delete `frontend/app/src/shared/components/aria/button.tsx` and `frontend/app/src/shared/components/ui/spinner.tsx` once the migration is complete.

## Non-goals

- Migrating other `aria/*` components (autocomplete, breadcrumbs, popover, etc.) to the package.
- Moving `frontend/app/src/shared/components/aria/style-rac.ts`. It stays in the app for the other aria/* components that depend on it. The package keeps its own copy of the focus-visible string (see below).
- Adding test infrastructure for react-aria components in the package.
- Cleaning up the homepage `ButtonShowcase` block — that's an independent issue.

## Package layout

```
frontend/packages/ui/src/
├── components/
│   ├── button/
│   │   ├── button.tsx              # NEW: Button + LinkButton, tv-based, react-aria-components
│   │   └── button.stories.tsx      # REWRITTEN: variants × sizes × shapes grid
│   ├── card/
│   │   └── card.tsx                # unchanged
│   └── spinner/
│       └── spinner.tsx             # NEW: copied from app, classNames → cn
├── styles/
│   └── focus-visible.ts            # NEW: focusVisibleStyle string (duplicate of app's)
├── index.css                       # unchanged
└── index.ts                        # public exports updated
```

`focus-visible.ts` is a deliberate duplicate of the `focusVisibleStyle` constant from `frontend/app/src/shared/components/aria/style-rac.ts`. The app version stays as the source of truth for app-only `aria/*` components; the package version is internal to the package and consumed by the package Button. Both must stay in sync — a one-line comment in each file points at the other.

## Public API (`@infrahub/ui`)

```ts
// frontend/packages/ui/src/index.ts
export {
  Button,
  LinkButton,
  buttonVariants,
  type ButtonProps,
  type LinkButtonProps,
} from "./components/button/button";
export { Spinner, type SpinnerProps } from "./components/spinner/spinner";
export {
  Card,
  CardHeader,
  CardContent,
  type CardProps,
  type CardHeaderProps,
  type CardContentProps,
} from "./components/card/card";
```

`focusVisibleStyle` is **not** exported — it's package-internal. If a future consumer needs it, we'll re-evaluate then.

## Button conversion (cva → tv)

Mechanical translation. The `tv` function accepts a single object whose top-level keys are `base`, `variants`, `compoundVariants`, and `defaultVariants`. The cva `[base classes]` first argument moves under the `base` key. Everything else is identical.

```ts
import { tv, cn, type VariantProps } from "tailwind-variants";
import {
  Button as AriaButton,
  type ButtonProps as AriaButtonProps,
  Link as AriaLink,
  type LinkProps as AriaLinkProps,
  composeRenderProps,
} from "react-aria-components";
import { Spinner } from "../spinner/spinner";
import { focusVisibleStyle } from "../../styles/focus-visible";

const buttonVariants = tv({
  base: [
    "relative inline-flex shrink-0 cursor-pointer items-center justify-center whitespace-nowrap",
    "rounded-xl border text-sm outline-none",
    "shadow-[0px_3px_6px_-2px_rgba(0,0,0,0.02),0px_1px_1px_rgba(0,0,0,0.04)]",
    "transition-all duration-150 ease-out",
    "data-disabled:pointer-events-none data-disabled:cursor-default data-disabled:opacity-60 data-disabled:shadow-none",
    "data-pending:cursor-default data-pending:select-none",
    "data-pressed:scale-95 data-pressed:shadow-none data-pressed:duration-75",
    "[&_svg:not([class*='size-'])]:size-3.5 [&_svg]:pointer-events-none [&_svg]:shrink-0",
  ],
  variants: { variant: { /* …8 variants unchanged… */ }, size: { xs: "h-7", sm: "h-8", md: "h-9" }, shape: { default: "rounded-lg", square: "aspect-square rounded-lg", circle: "aspect-square rounded-full" } },
  compoundVariants: [
    { shape: "default", size: "xs", class: "gap-1 px-2" },
    { shape: "default", size: "sm", class: "gap-1.5 px-2" },
    { shape: "default", size: "md", class: "gap-2 px-3" },
  ],
  defaultVariants: { variant: "primary", size: "md", shape: "default" },
});
```

`Button` and `LinkButton` function bodies are copied verbatim from the app, with `classNames(...)` replaced by `cn(...)` from `tailwind-variants`. The `isPending` / `isDisabledAndFocusable` / `composeRenderProps` logic is preserved exactly. `Spinner` is imported from `../spinner/spinner` (sibling package component).

## Spinner conversion

Copy `frontend/app/src/shared/components/ui/spinner.tsx` verbatim into `frontend/packages/ui/src/components/spinner/spinner.tsx`, with one change: replace `import { classNames } from "@/shared/utils/common"` with `import { cn } from "tailwind-variants"`. Rename the call site `classNames(...)` → `cn(...)`. The `fill-custom-blue-600` class stays — same Tailwind-color-resolution mechanism as everything else.

## Package dependencies

Add to `frontend/packages/ui/package.json`:

```json
"dependencies": {
  // existing entries…
  "react-aria-components": "^1.17.0"
}
```

`tailwind-variants` and `tailwind-merge` are already present. `lucide-react` stays (still used elsewhere). No `clsx` addition — `tailwind-variants` brings what it needs internally.

## Consumer migration

| Old import | New import | Files |
| --- | --- | --- |
| `from "@/shared/components/aria/button"` | `from "@infrahub/ui"` | 129 |
| `from "@/shared/components/ui/spinner"` | `from "@infrahub/ui"` | 28 |

Codemod-able: simple find-and-replace on the import string. The exported symbol names (`Button`, `LinkButton`, `ButtonProps`, `LinkButtonProps`, `buttonVariants`, `Spinner`) are unchanged, so the import bindings on the right-hand side need no edits.

After migration:

- Delete `frontend/app/src/shared/components/aria/button.tsx`.
- Delete `frontend/app/src/shared/components/ui/spinner.tsx`.
- Delete `frontend/packages/ui/src/components/button/button.tsx` (the old version) and `button.stories.tsx`.
- Add new `frontend/packages/ui/src/components/button/button.stories.tsx` reflecting the new API (variants × sizes × shapes grid).

## Tailwind class resolution

The Button base classes use stock Tailwind colors (`cyan`, `rose`, `amber`, `emerald`, `neutral`, `stone`). The Spinner and `focus-visible.ts` reference `custom-blue-600`, a custom theme color defined in the app's Tailwind config.

For these custom colors to compile:

- The app's Tailwind v4 content scan must include the package source. Verify `frontend/app/vite.config.ts` (or wherever `@tailwindcss/vite` is wired) lists `../packages/ui/src/**/*.{ts,tsx}` in the content sources. If not, add it.
- Confirm by running the dev server and inspecting that focus rings still render with the right color and the spinner fills with the right color.

## Migration plan (high level)

1. Add `react-aria-components` to `packages/ui/package.json`. Run `pnpm install`.
2. Create `packages/ui/src/styles/focus-visible.ts`. Create `packages/ui/src/components/spinner/spinner.tsx`.
3. Replace `packages/ui/src/components/button/button.tsx` with the new tv-based Button + LinkButton. Update `button.stories.tsx`.
4. Update `packages/ui/src/index.ts` exports.
5. Codemod consumers (Button + Spinner imports → `@infrahub/ui`).
6. Delete the two old app source files.
7. Verify Tailwind color resolution (focus ring + spinner fill) in the dev server.
8. Run unit tests + biome.

The implementation plan that follows will break this into TDD-style bite-sized steps with codemod commands and verification at each stage.

## Risks

- **Tailwind content scan misses the package.** Symptom: focus ring is invisible or the spinner is unstyled. Mitigation: include the package's source paths in the app's Tailwind content config; verify on dev server before merging.
- **react-aria peer-dep duplication.** With pnpm and a workspace package, both `frontend/app` and `frontend/packages/ui` resolve to the same `react-aria-components`. If hoisting goes wrong, react-aria would lose its singleton state and components would break. Verify with `pnpm why react-aria-components` after install — should show one version, two consumers.
- **Storybook stories using new API.** The package runs Storybook (`pnpm storybook`); the new stories must compile and render under the package's standalone Tailwind setup. Stock colors will work; the custom colors won't unless the package's storybook config also includes the app's theme. If it doesn't, drop the focus-ring story or accept a missing color in Storybook only.
- **Drift between app's `focusVisibleStyle` and package's copy.** Mitigation: cross-reference comment in both files. Long term, consolidate when more `aria/*` components migrate.
- **Codemod misses.** A find/replace on import strings is reliable when bindings don't change. Run TypeScript at the end to catch any miss.

## Out of scope (deferred)

- Migrating other `aria/*` components (autocomplete, breadcrumbs, menu, popover, select, tooltip, tree, etc.) to the package.
- Consolidating `focusVisibleStyle` between app and package (deferred until more components move).
- Removing `class-variance-authority` from the app entirely (other components may still use it; verify and remove only if zero remaining uses after this migration).
- Adding Vitest unit tests for the package Button.
