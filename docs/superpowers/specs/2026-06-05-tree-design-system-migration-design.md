# Migrate aria `Tree` to `@infrahub/ui`

**Date:** 2026-06-05
**Status:** Draft

## Goal

Move the `Tree`, `TreeItem`, `TreeItemContent`, and `TreeItemLoader` primitives from `frontend/app/src/shared/components/aria/tree.tsx` into the `@infrahub/ui` design-system package, add Storybook stories, and update the four call sites in the app to import from `@infrahub/ui`.

This continues the incremental migration documented in `dev/knowledge/frontend/design-system.md` (Card #9048, Button #9065, Modal #9088, Meter #9100, ScrollArea #9101, CheckboxCard most recent).

## Scope

### In scope

- New component file at `frontend/packages/ui/src/components/tree/tree.tsx`
- New Storybook file at `frontend/packages/ui/src/components/tree/tree.stories.tsx`
- Export from `frontend/packages/ui/src/index.ts`
- Migration of four consumers in `frontend/app/src` to import from `@infrahub/ui`
- Deletion of `frontend/app/src/shared/components/aria/tree.tsx` once unused

### Out of scope

- Migration of sibling `aria/checkbox.tsx`, `aria/style-rac.ts`, or any other `shared/components/aria/*` files. They have their own migration paths (`aria/checkbox.tsx` is being touched on this branch for a separate CheckboxCard PR). `aria/style-rac.ts` stays — it is still consumed by other files.
- API changes to the Tree primitives. This is a strict 1:1 port.
- Per-component subpath export in `package.json` (current convention exports from the root `index.ts` only; the recently removed `./checkbox-card` subpath confirms this direction).

## Public API (preserved 1:1)

```ts
export const Tree: typeof AriaTree;

export interface TreeItemProps extends AriaTreeItemProps {}
export function TreeItem(props: TreeItemProps): JSX.Element;

export interface TreeItemContentProps extends AriaTreeItemContentProps {
  onExpandedChange?: () => void;
}
export function TreeItemContent(props: TreeItemContentProps): JSX.Element;

export function TreeItemLoader(props: AriaTreeLoadMoreItemProps): JSX.Element;
```

No prop additions, no prop removals, no behavioural changes. Call sites change only the import path.

## Internal dependency rewrites

The package cannot import from `frontend/app/src`. Three app-only deps in the current implementation get inlined or substituted:

| Current (app) | Package replacement | Notes |
|---|---|---|
| `focusVisibleStyle` from `@/shared/components/aria/style-rac` | `focusVisibleStyle` from `../../styles/focus-visible` | The package already maintains a duplicate explicitly for this purpose (see comment at top of `style-rac.ts`). |
| `Row` from `@/shared/components/container` | inline `<div className="flex items-center gap-0" style={{ paddingLeft }}>` | `Row` is just `flex items-center gap-2`; the current Tree overrides `gap` to `0` via `className="gap-0"`, so the resolved markup is a plain `div`. |
| `LoadingIndicator` from `@/shared/components/loading/loading-indicator` | inline `<Spinner />` imported relatively from `../spinner/spinner` + `<span>Loading...</span>` inside a `flex items-center justify-start gap-2 text-gray-500 text-sm h-8` container | Matches the visual produced by `LoadingIndicator` (which itself already wraps `Spinner` + text). Relative import avoids any in-package circular dependency. |
| `classNames` from `@/shared/utils/common` | `cn` from `tailwind-variants` | Per the UI-package convention (see CheckboxCard, Card, etc.). |

No visual or behavioural change is intended. The `paddingLeft: (level - 1) * 23` indentation on `TreeItemContent` and `paddingLeft: level * 32` on `TreeItemLoader` are preserved exactly.

## File layout

```
frontend/packages/ui/src/components/tree/
  tree.tsx              # Tree, TreeItem, TreeItemContent, TreeItemLoader
  tree.stories.tsx      # Default, WithLoader, Playground
```

## Index export

Append to `frontend/packages/ui/src/index.ts`:

```ts
export {
  Tree,
  TreeItem,
  TreeItemContent,
  TreeItemLoader,
  type TreeItemProps,
  type TreeItemContentProps,
} from "./components/tree/tree";
```

No change to `package.json` exports. The root `.` entry already routes all named exports through `index.ts`, which matches the current convention.

## Storybook

`tree.stories.tsx` follows the CheckboxCard pattern: one `meta`, multiple named `Story` exports, each with its own render function.

- **Default** — a small static tree (e.g., 2–3 folders, one with nested file leaves) showing expand/collapse via `defaultExpandedKeys`, hover state on `TreeItem`, the chevron rotation on expand, and the dot icon on leaves. Demonstrates `Tree` + `TreeItem` + `TreeItemContent` together.
- **WithLoader** — same tree shape as Default but adds a `TreeItemLoader` row inside one branch. Documents the loading-state surface used by `ipam-tree` and `object-hierarchy-tree`.
- **Playground** — minimal `Tree` with `argTypes` for `aria-label` and `selectionMode` so the Storybook controls panel exposes meaningful knobs.

Stories use static data only (no React Query, no app state). They do not need to render `react-router` `href` or similar consumer-specific concerns.

## Call-site migration

Four files import from `@/shared/components/aria/tree`:

| File | Symbols imported |
|---|---|
| `entities/ipam/ipam-tree/ui/ipam-tree.tsx` | `Tree`, `TreeItem`, `TreeItemContent`, `TreeItemLoader` |
| `entities/nodes/hierarchy/ui/object-hierarchy-tree.tsx` | `Tree`, `TreeItem`, `TreeItemContent`, `TreeItemLoader` |
| `entities/nodes/hierarchy/ui/object-hierarchy-tree-lite.tsx` | `Tree` |
| `entities/diff/ui/diff-tree.tsx` | `Tree`, `TreeItem`, `TreeItemContent` |

Each is a single-line edit:

```diff
- import { Tree, TreeItem, TreeItemContent, TreeItemLoader } from "@/shared/components/aria/tree";
+ import { Tree, TreeItem, TreeItemContent, TreeItemLoader } from "@infrahub/ui";
```

After all four call sites are updated, delete `frontend/app/src/shared/components/aria/tree.tsx`.

## Verification

- `cd frontend/app && pnpm biome:fix` — format + lint
- `cd frontend/app && pnpm build` — TypeScript + Vite build (this also validates `@infrahub/ui`; `pnpm build` inside `packages/ui` is pre-existingly broken — see project memory)
- `cd frontend/app && pnpm test` — unit tests
- `cd frontend/packages/ui && pnpm storybook` — manual spot-check of the three new Tree stories
- Grep confirms no remaining `from "@/shared/components/aria/tree"` imports
- Grep confirms `frontend/app/src/shared/components/aria/tree.tsx` is deleted

## Risks

- **Visual regression at call sites.** Mitigated by strict 1:1 port (no styling change) and manual spot-check of each Tree consumer (ipam tree page, diff page, hierarchy view) after migration.
- **`Spinner` import cycle.** The new `TreeItemLoader` will import `Spinner` from a sibling component inside the same package (`../spinner/spinner`), not from `@infrahub/ui` itself, to avoid any in-package circular import.
- **Storybook drift.** Stories live next to the component, so future API changes that don't update the story will be obvious in review. No additional safeguard required.

## Open questions

None. All decisions resolved during brainstorming:

- Migration scope: strict 1:1 port
- Loader content: inline `Spinner` + "Loading..." label
- Sibling aria files: out of scope
