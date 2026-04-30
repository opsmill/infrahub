# Migrate Resizable to `@infrahub/ui`

## Goal

Move the `Resizable*` components from `frontend/app/src/shared/components/ui/resizable.tsx` into the shared `@infrahub/ui` package, following the same pattern established by the recent ScrollArea migration (commit `6c4decbc00`).

## Current State

- **Source file:** `frontend/app/src/shared/components/ui/resizable.tsx` — three exports (`ResizablePanelGroup`, `ResizablePanel`, `ResizableHandle`) wrapping `react-resizable-panels`.
- **Working tree:** an unstaged style change to `ResizableHandle` drops `relative`, adds `rounded-full`, and recolors hover/focus from `bg-custom-blue-600` to `bg-cyan-600`. This change should be carried into the migrated file.
- **Callers (2):**
  - `frontend/app/src/pages/ipam/ipam-layout.tsx`
  - `frontend/app/src/pages/objects/layout.tsx`
- **Library:** `react-resizable-panels@^4.10.0` is currently a dependency of `frontend/app`.

## Target State

- New component lives at `frontend/packages/ui/src/components/resizable/resizable.tsx`.
- Stories at `frontend/packages/ui/src/components/resizable/resizable.stories.tsx`.
- `@infrahub/ui` re-exports `ResizablePanelGroup`, `ResizablePanel`, `ResizableHandle` from its barrel `index.ts`.
- `react-resizable-panels` moves from `frontend/app/package.json` to `frontend/packages/ui/package.json` (no other consumer in the app).
- Both callers import from `@infrahub/ui` instead of the local path.
- The original `frontend/app/src/shared/components/ui/resizable.tsx` is deleted.

## Component API

The public API stays identical to the current source — no new props, no new components.

```ts
export function ResizablePanelGroup(props: ResizablePrimitive.GroupProps): JSX.Element;
export const ResizablePanel: typeof ResizablePrimitive.Panel;
export function ResizableHandle(props: ResizablePrimitive.SeparatorProps): JSX.Element;
```

Because the components add no fields beyond the primitive's prop types, no custom `ResizablePanelGroupProps` / `ResizableHandleProps` interfaces are introduced. (ScrollArea introduced one because it added `scrollX`/`scrollY`/etc.; resizable doesn't.)

## Style Adjustments in the Migration

1. Replace `classNames` (from `@/shared/utils/common`) with `cn` (from `tailwind-variants`) — matches the ScrollArea migration and the existing convention inside `@infrahub/ui`.
2. Apply the unstaged working-tree change to `ResizableHandle`:
   - Drop `relative`
   - Add `rounded-full`
   - Hover/focus: `bg-cyan-600` (was `bg-custom-blue-600`)

## Stories

Mirror the ScrollArea stories file structure. Provide:

- A `Default` story that shows a horizontal `ResizablePanelGroup` with two `ResizablePanel`s separated by a `ResizableHandle`.
- A `Vertical` story showing the same with `orientation="vertical"` (the API uses `orientation`, as seen in the IPAM caller).
- A `Playground` story for interactive prop tweaking.

The exact content is for illustration; what matters is parity with the ScrollArea stories shape (`Meta`, `StoryObj`, `parameters: { layout: "padded" }`, plus a `Default` and `Playground`).

## Migration Steps

1. Create `frontend/packages/ui/src/components/resizable/resizable.tsx` with the three exports, using `cn` and incorporating the unstaged style changes.
2. Create `frontend/packages/ui/src/components/resizable/resizable.stories.tsx`.
3. Add `"react-resizable-panels": "^4.10.0"` to `frontend/packages/ui/package.json` dependencies.
4. Add a re-export line to `frontend/packages/ui/src/index.ts`:
   ```ts
   export { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "./components/resizable/resizable";
   ```
5. Update both caller files to import from `@infrahub/ui`:
   - `frontend/app/src/pages/ipam/ipam-layout.tsx`
   - `frontend/app/src/pages/objects/layout.tsx`
6. Delete `frontend/app/src/shared/components/ui/resizable.tsx`.
7. Remove `"react-resizable-panels"` from `frontend/app/package.json` dependencies.
8. Run `pnpm install` in `frontend/packages/ui` and `frontend/app` to update lockfiles.
9. Run `pnpm biome:fix` in `frontend/app` to clean import order.
10. If `frontend/app/.betterer.results` references the deleted file, regenerate per the ScrollArea commit's pattern.

## Verification

- `cd frontend/app && pnpm build` succeeds (typecheck + Vite build).
- `cd frontend/app && pnpm test` passes.
- `cd frontend/packages/ui && pnpm build` succeeds.
- Manual sanity check in the dev server:
  - Open an object detail page — the hierarchy panel resizer still works.
  - Open an IPAM page — the tree panel resizer still works.
- New cyan handle color is visible on hover/focus.

## Out of Scope

- No changes to the resizable component's API surface (no new props).
- No refactoring of caller layouts or panel sizing logic.
- No upgrade of `react-resizable-panels`.
