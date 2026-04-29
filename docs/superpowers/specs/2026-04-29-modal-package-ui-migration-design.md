# Migrate `Modal` to `@infrahub/ui`

**Date:** 2026-04-29
**Author:** bilal@opsmill.com
**Scope:** Move `Modal` and `ModalOverlay` (and the `Stacked` helper they depend on) out of `frontend/app/src/shared/components/aria/` and into the shared `@infrahub/ui` package, on the same pattern as the recent `Card` and `Button` migrations.

## Context

The frontend has been incrementally promoting low-level UI primitives from `frontend/app/src/shared/components/` into `frontend/packages/ui/` so they can be shared, documented in Storybook, and visually regression-tested with Chromatic. `Card` (#9048) and `Button` (#9065) are already migrated. `Modal` is the next primitive in that queue. A `Sheet` migration is also planned and will reuse the same stacking helper.

Today, `Modal` lives at `frontend/app/src/shared/components/aria/modal.tsx`. It exports `Modal` and `ModalOverlay`, both wrapping `react-aria-components`. It depends on:

- `Stacked` — a small React-context primitive at `frontend/app/src/shared/components/aria/utils/stacked.tsx` that lets nested `Modal` instances offset and scale relative to one another. Used only by `Modal` today.
- `classNames` — `clsx` + `tailwind-merge` wrapper from `frontend/app/src/shared/utils/common.ts`. The `@infrahub/ui` package uses `cn` from `tailwind-variants` for the same purpose.

There are 9 callsites in the app importing from `@/shared/components/aria/modal`.

## Goal

After this migration:

- `Modal`, `ModalOverlay`, `ModalProps`, and `ModalOverlayProps` are exported from `@infrahub/ui` (root re-export) and `@infrahub/ui/modal` (subpath).
- `Stacked` is an internal helper inside `@infrahub/ui`, not part of the public API, but located so the planned `Sheet` migration can reuse it without reaching into `modal/`.
- All 9 app callsites import from `@infrahub/ui`. The legacy files in `aria/` are deleted.
- Storybook covers the default usage and the stacking behavior.

## Design

### File layout

```
frontend/packages/ui/src/
├── components/
│   └── modal/
│       ├── modal.tsx           # Modal + ModalOverlay + types
│       └── modal.stories.tsx   # Default + InfiniteNested stories
└── utils/
    ├── compose-aria-class-name.ts   # existing
    └── stacked.tsx                  # Stacked context helper
```

`stacked.tsx` is placed under `utils/` rather than nested in `modal/`. It is internal to the package (not surfaced from `src/index.ts`) but accessible to both `modal/` now and `sheet/` later via a relative import. `utils/` is already a mixed bag (`compose-aria-class-name.ts` is a function), so housing a small stateful helper there is consistent with the existing convention. A dedicated `_internal/` folder is unnecessary for a single file.

### API surface

`packages/ui/src/components/modal/modal.tsx` exposes:

```ts
export interface ModalOverlayProps extends AriaModalOverlayProps {}
export interface ModalProps
  extends Omit<AriaModalOverlayProps, "children">,
    Pick<DialogProps, "aria-label" | "children"> {}

export function ModalOverlay(props: ModalOverlayProps): JSX.Element
export function Modal(props: ModalProps): JSX.Element
```

Behavior is byte-for-byte identical to the current implementation: same Tailwind classes, same enter/exit animations, same `Stacked`-driven `top` and `scale` math, same `isDismissable = true` default. The only edits during the move are:

1. Replace `classNames` (from `@/shared/utils/common`) with `cn` from `tailwind-variants` — matches the convention in `button.tsx` and `card.tsx`.
2. Update the `Stacked` import to `../../utils/stacked`.

`Stacked` itself moves over unchanged.

### Package wiring

**`packages/ui/package.json`** — add the `./modal` subpath:

```jsonc
"exports": {
  ".": "./src/index.ts",
  "./card": "./src/components/card/card.tsx",
  "./modal": "./src/components/modal/modal.tsx",
  "./styles.css": "./src/index.css"
}
```

**`packages/ui/src/index.ts`** — append:

```ts
export {
  Modal,
  ModalOverlay,
  type ModalOverlayProps,
  type ModalProps,
} from "./components/modal/modal";
```

`Stacked` is intentionally not exported.

### Storybook stories

`modal.stories.tsx` follows the button/card story shape (`Meta`, `StoryObj`, `parameters: { layout: "centered" }`, args for `isOpen`).

**`Default`** — a single `Modal` with `isOpen` controlled by an arg. Body contains a heading, a paragraph, and a footer row with a "Cancel" and a "Confirm" `Button`. Demonstrates the standard usage.

**`InfiniteNested`** — a trigger `Button` that opens a `Modal` containing body text plus an "Open another" `Button`. The inner button opens *another* `Modal` recursively, with no upper bound. Each nested level renders the same component. This exercises the `Stacked` context: every new layer pushes prior layers back via the `top` (`50 - depth * 4` %) and `scale` (`1 - depth * 0.05`) math, and closing a layer pops it.

Sketch:

```tsx
function NestedModal({ depth = 0 }: { depth?: number }) {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <>
      <Button onPress={() => setIsOpen(true)}>Open another</Button>
      <Modal isOpen={isOpen} onOpenChange={setIsOpen} aria-label={`Modal level ${depth}`}>
        <p>Level {depth}</p>
        <NestedModal depth={depth + 1} />
      </Modal>
    </>
  );
}
```

The story renders `<NestedModal />`. `argTypes` is empty for this story.

No vitest/unit tests are added in this migration. This matches the current state of `packages/ui` (Button and Card ship stories but no unit tests). The orphaned screenshot folder at `aria/utils/__screenshots__/stacked.test.tsx/` is not preserved — see Cleanup.

### Callsite migration

All 9 callsites switch to the bare root path `from "@infrahub/ui"`, matching how `Button` and `Card` are imported today. No prop or behavior changes.

| File | Imports |
|---|---|
| `shared/components/modals/modal-confirm.tsx` | `Modal` |
| `shared/components/modals/modal-delete.tsx` | `Modal` |
| `entities/repository/ui/check-connectivity-modal.tsx` | `Modal` |
| `entities/config/ui/about-modal.tsx` | `Modal` |
| `entities/navigation/ui/search-anywhere/search-anywhere-dialog.tsx` | `ModalOverlay` |
| `entities/schema/ui/computed-attribute-display.tsx` | `Modal` |
| `entities/schema/ui/schema-viewer-modal.tsx` | `Modal`, `type ModalProps` |
| `entities/user-profile/ui/account-token-create-action.tsx` | `Modal` |
| `entities/branches/ui/modal-delete-branch.tsx` | `Modal` |

### Cleanup

Delete:

- `frontend/app/src/shared/components/aria/modal.tsx`
- `frontend/app/src/shared/components/aria/utils/stacked.tsx`
- `frontend/app/src/shared/components/aria/utils/__screenshots__/` (entire folder — only the orphaned `stacked.test.tsx/Stacked-keeps-different-groups-in-independent-stack-chains-1.png` remains; the test source no longer exists)

The `aria/__screenshots__/sheet.test.tsx/` folder is out of scope for this migration and is left untouched.

## Build sequence

1. **`packages/ui` first** — must build in isolation before the app depends on it.
   - Create `packages/ui/src/utils/stacked.tsx` (copy from app, no edits).
   - Create `packages/ui/src/components/modal/modal.tsx` (copy from app, swap `classNames` → `cn`, update `Stacked` import path).
   - Create `packages/ui/src/components/modal/modal.stories.tsx`.
   - Update `packages/ui/package.json` (`exports`) and `packages/ui/src/index.ts`.
   - Verify: `cd frontend/packages/ui && pnpm build && pnpm storybook`.

2. **App side**
   - Update all 9 callsite imports.
   - Delete the legacy files and orphaned screenshot folder.
   - Run `cd frontend/app && pnpm biome:fix`, then `pnpm tsc --noEmit`, then `pnpm test`.

3. **Final verification**
   - `cd frontend/app && pnpm build`.
   - `cd frontend/app && pnpm test:e2e -- modal` (the dialog/branch-delete flows that exercise modals).
   - `grep -r "aria/modal\|aria/utils/stacked" frontend/app/src` returns no hits.
   - Spot-check `.betterer.results` for unexpected drift.

## Risks and notes

- **`React.use(StackContext)`** — `Stacked` uses the React 19 `use` API. `packages/ui` already pins React 19.2.5, so this transfers cleanly.
- **No `'use client'` directive** — neither Button nor Card declares one; `Modal` follows suit. The consumer is a Vite SPA, not a Next.js app.
- **Tailwind content scanning** — Modal's classes (`fixed`, `data-entering:zoom-in-80`, the gradient utilities) must be reachable by the app's Tailwind config. Card and Button already work, so the scan path covers `packages/ui` already; verify by inspecting the Tailwind content config during implementation.
- **`aria-label`** — Modal forwards `aria-label` to the inner `AriaDialog`. All 9 current callsites pass one. The Default story should pass one too, so the pattern is discoverable.
- **Betterer baseline** — adding new files to `packages/ui` should not move betterer counts. If it does, the implementation plan handles regen.

## Out of scope

- Adding vitest/unit tests for `Modal` or `Stacked`.
- Migrating other `aria/*` components (Sheet, Popover, Menu, etc.) — Sheet has its own planned migration that will consume the `Stacked` helper this migration places in `utils/`.
- Changing any callsite's behavior or prop usage beyond the import path.
- Touching `aria/__screenshots__/sheet.test.tsx/`.
