# Tree Design-System Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `Tree`, `TreeItem`, `TreeItemContent`, `TreeItemLoader` from `frontend/app/src/shared/components/aria/tree.tsx` into `@infrahub/ui` with Storybook stories, then migrate the four app call sites.

**Architecture:** Strict 1:1 port — same public API, same behaviour. App-only deps (`Row`, `LoadingIndicator`, app `focusVisibleStyle`, `classNames`) get substituted with their package equivalents (inline div, `Spinner` + label, package `focusVisibleStyle`, `cn` from `tailwind-variants`). One root export from `frontend/packages/ui/src/index.ts`; no per-component subpath in `package.json`.

**Tech Stack:** React 19, TypeScript 5.9, `react-aria-components` 1.18, `tailwind-variants`, Tailwind CSS 4, Storybook 10, Vite 8.

---

## Spec

This plan implements `docs/superpowers/specs/2026-06-05-tree-design-system-migration-design.md`. Read it first.

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `frontend/packages/ui/src/components/tree/tree.tsx` | Create | Tree primitives — `Tree`, `TreeItem`, `TreeItemContent`, `TreeItemLoader` + types |
| `frontend/packages/ui/src/components/tree/tree.stories.tsx` | Create | Storybook stories: `Default`, `WithLoader`, `Playground` |
| `frontend/packages/ui/src/index.ts` | Modify | Add the new exports |
| `frontend/app/src/entities/ipam/ipam-tree/ui/ipam-tree.tsx` | Modify | Switch import to `@infrahub/ui` |
| `frontend/app/src/entities/nodes/hierarchy/ui/object-hierarchy-tree.tsx` | Modify | Switch import to `@infrahub/ui` |
| `frontend/app/src/entities/nodes/hierarchy/ui/object-hierarchy-tree-lite.tsx` | Modify | Switch import to `@infrahub/ui` |
| `frontend/app/src/entities/diff/ui/diff-tree.tsx` | Modify | Switch import to `@infrahub/ui` |
| `frontend/app/src/shared/components/aria/tree.tsx` | Delete | Source file no longer used |

## Working directory

All commands assume CWD = `/Users/bilal/opsmill/infrahub` unless explicitly `cd`'d.

## Note about TDD shape

This is a strict 1:1 UI component port — no behaviour change. The verification loop is "Storybook renders + types pass + app builds", not red/green unit tests. Tasks follow build → render → commit, not test-first. This matches the precedent set by Card, CheckboxCard, and the other UI-package migrations.

## Note about focus-ring color

The app's `focusVisibleStyle` uses `custom-blue-600`; the package's mirror uses `cyan-700`. This is intentional and matches every other migrated primitive (Card, Modal, CheckboxCard…). The Tree's focus ring color will shift accordingly — that's expected, not a regression.

---

### Task 1: Create the Tree component file

**Files:**
- Create: `frontend/packages/ui/src/components/tree/tree.tsx`

- [ ] **Step 1: Create the directory**

```bash
mkdir -p frontend/packages/ui/src/components/tree
```

- [ ] **Step 2: Write the component file**

Create `frontend/packages/ui/src/components/tree/tree.tsx` with these exact contents:

```tsx
import { ChevronRightIcon } from "lucide-react";
import type React from "react";
import {
  Tree as AriaTree,
  TreeItem as AriaTreeItem,
  TreeItemContent as AriaTreeItemContent,
  type TreeItemContentProps as AriaTreeItemContentProps,
  type TreeItemProps as AriaTreeItemProps,
  TreeLoadMoreItem as AriaTreeLoadMoreItem,
  type TreeLoadMoreItemProps as AriaTreeLoadMoreItemProps,
  Button,
} from "react-aria-components";
import { cn } from "tailwind-variants";

import { Spinner } from "../spinner/spinner";
import { focusVisibleStyle } from "../../styles/focus-visible";

export const Tree = AriaTree;

export interface TreeItemProps extends AriaTreeItemProps {}

export const TreeItem = ({ className, ...props }: TreeItemProps) => {
  return (
    <AriaTreeItem
      className={cn(
        focusVisibleStyle,
        "cursor-pointer rounded-md border border-transparent text-sm mix-blend-multiply hover:bg-neutral-100",
        className,
      )}
      {...props}
    />
  );
};

export interface TreeItemContentProps extends AriaTreeItemContentProps {
  onExpandedChange?: () => void;
}

export const TreeItemContent = ({
  onExpandedChange,
  children,
  ...props
}: TreeItemContentProps) => {
  return (
    <AriaTreeItemContent {...props}>
      {(contentProps) => {
        const { hasChildItems, isExpanded, level } = contentProps;
        return (
          <div
            className="flex items-center gap-0"
            style={{ paddingLeft: (level - 1) * 23 }}
          >
            {hasChildItems ? (
              <Button
                slot="chevron"
                onPress={onExpandedChange}
                className={cn(
                  "inline-flex size-8 shrink-0 items-center justify-center duration-200",
                  isExpanded && "rotate-90",
                )}
              >
                <ChevronRightIcon className="size-4" />
              </Button>
            ) : (
              <div className="inline-flex size-8 shrink-0 items-center justify-center">
                <DotIcon />
              </div>
            )}

            {typeof children === "function" ? children(contentProps) : children}
          </div>
        );
      }}
    </AriaTreeItemContent>
  );
};

export function TreeItemLoader(props: AriaTreeLoadMoreItemProps) {
  return (
    <AriaTreeLoadMoreItem {...props}>
      {({ level }) => (
        <div
          className="flex h-8 items-center justify-start gap-2 text-gray-500 text-sm"
          style={{ paddingLeft: level * 32 }}
        >
          <Spinner />
          <span>Loading...</span>
        </div>
      )}
    </AriaTreeLoadMoreItem>
  );
}

const DotIcon = (props: React.HTMLAttributes<SVGSVGElement>) => (
  <svg
    aria-hidden="true"
    focusable="false"
    width="26"
    height="6"
    viewBox="0 0 6 6"
    fill="currentColor"
    xmlns="http://www.w3.org/2000/svg"
    {...props}
  >
    <path
      fillRule="evenodd"
      clipRule="evenodd"
      d="M2.9999 4.3C3.71787 4.3 4.2999 3.71797 4.2999 3C4.2999 2.28203 3.71787 1.7 2.9999 1.7C2.28193 1.7 1.6999 2.28203 1.6999 3C1.6999 3.71797 2.28193 4.3 2.9999 4.3ZM2.9999 5.1C4.1597 5.1 5.0999 4.1598 5.0999 3C5.0999 1.8402 4.1597 0.900002 2.9999 0.900002C1.8401 0.900002 0.899902 1.8402 0.899902 3C0.899902 4.1598 1.8401 5.1 2.9999 5.1Z"
    />
  </svg>
);
```

- [ ] **Step 3: Format and lint**

```bash
cd frontend/app && pnpm biome:fix ../packages/ui/src/components/tree/tree.tsx
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/packages/ui/src/components/tree/tree.tsx
git commit -m "feat(ui): add Tree primitives to @infrahub/ui"
```

---

### Task 2: Export Tree from the package index

**Files:**
- Modify: `frontend/packages/ui/src/index.ts`

- [ ] **Step 1: Add the export**

Append to `frontend/packages/ui/src/index.ts` (location: after the `ResizablePanelGroup` export block at the bottom, before EOF):

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

- [ ] **Step 2: Format**

```bash
cd frontend/app && pnpm biome:fix ../packages/ui/src/index.ts
```

Expected: no errors.

- [ ] **Step 3: Verify the type-check resolves the export**

```bash
cd frontend/app && pnpm exec tsc --noEmit
```

Expected: succeeds. (If the app build is being run for the first time, it may take a minute.)

- [ ] **Step 4: Commit**

```bash
git add frontend/packages/ui/src/index.ts
git commit -m "feat(ui): export Tree from @infrahub/ui index"
```

---

### Task 3: Add Storybook stories for Tree

**Files:**
- Create: `frontend/packages/ui/src/components/tree/tree.stories.tsx`

- [ ] **Step 1: Create the stories file**

Create `frontend/packages/ui/src/components/tree/tree.stories.tsx` with these exact contents:

```tsx
import type { Meta, StoryObj } from "@storybook/react-vite";

import { Collection, type TreeProps } from "react-aria-components";

import { Tree, TreeItem, TreeItemContent, TreeItemLoader } from "./tree";

type FolderNode = {
  id: string;
  name: string;
  children?: FolderNode[];
};

const TREE_DATA: FolderNode[] = [
  {
    id: "docs",
    name: "docs",
    children: [
      { id: "docs/readme", name: "README.md" },
      { id: "docs/getting-started", name: "getting-started.md" },
    ],
  },
  {
    id: "src",
    name: "src",
    children: [
      {
        id: "src/components",
        name: "components",
        children: [
          { id: "src/components/button.tsx", name: "button.tsx" },
          { id: "src/components/card.tsx", name: "card.tsx" },
        ],
      },
      { id: "src/index.ts", name: "index.ts" },
    ],
  },
];

const meta: Meta<typeof Tree> = {
  component: Tree,
  parameters: {
    layout: "centered",
  },
};

export default meta;

type Story = StoryObj<typeof meta>;

function renderItem(item: FolderNode) {
  return (
    <TreeItem id={item.id} textValue={item.name}>
      <TreeItemContent>{item.name}</TreeItemContent>
      <Collection items={item.children ?? []}>{renderItem}</Collection>
    </TreeItem>
  );
}

function DefaultRender() {
  return (
    <Tree
      aria-label="Project files"
      items={TREE_DATA}
      defaultExpandedKeys={["docs", "src", "src/components"]}
      className="w-72"
    >
      {renderItem}
    </Tree>
  );
}

function WithLoaderRender() {
  return (
    <Tree
      aria-label="Project files (loading)"
      items={TREE_DATA}
      defaultExpandedKeys={["docs", "src"]}
      className="w-72"
    >
      {(item) => (
        <TreeItem id={item.id} textValue={item.name}>
          <TreeItemContent>{item.name}</TreeItemContent>
          <Collection items={item.children ?? []}>{renderItem}</Collection>
          {item.id === "src" && <TreeItemLoader />}
        </TreeItem>
      )}
    </Tree>
  );
}

function PlaygroundRender(args: Omit<TreeProps<FolderNode>, "children" | "items">) {
  return (
    <Tree {...args} items={TREE_DATA} className="w-72">
      {renderItem}
    </Tree>
  );
}

export const Default: Story = {
  render: DefaultRender,
};

export const WithLoader: Story = {
  render: WithLoaderRender,
};

export const Playground: Story = {
  args: {
    "aria-label": "Project files",
    selectionMode: "single",
    defaultExpandedKeys: ["docs", "src"],
  },
  argTypes: {
    "aria-label": { control: "text" },
    selectionMode: {
      control: "select",
      options: ["none", "single", "multiple"],
    },
  },
  render: PlaygroundRender,
};
```

- [ ] **Step 2: Format**

```bash
cd frontend/app && pnpm biome:fix ../packages/ui/src/components/tree/tree.stories.tsx
```

Expected: no errors.

- [ ] **Step 3: Verify Storybook renders the stories**

```bash
cd frontend/packages/ui && pnpm storybook
```

In the browser at `http://localhost:6006`, navigate to "Tree" and confirm all three stories render:
- **Default** — collapsed/expanded folders, chevron rotates on click, dot leaves render
- **WithLoader** — same as Default but a "Loading..." row appears inside `src`
- **Playground** — controls panel exposes `aria-label` (text) and `selectionMode` (select)

Stop Storybook (`Ctrl-C`) when done.

- [ ] **Step 4: Commit**

```bash
git add frontend/packages/ui/src/components/tree/tree.stories.tsx
git commit -m "feat(ui): add Storybook stories for Tree"
```

---

### Task 4: Migrate `ipam-tree.tsx` to import from `@infrahub/ui`

**Files:**
- Modify: `frontend/app/src/entities/ipam/ipam-tree/ui/ipam-tree.tsx`

- [ ] **Step 1: Replace the import**

In `frontend/app/src/entities/ipam/ipam-tree/ui/ipam-tree.tsx`, find this line:

```ts
import { Tree, TreeItem, TreeItemContent, TreeItemLoader } from "@/shared/components/aria/tree";
```

Replace with:

```ts
import { Tree, TreeItem, TreeItemContent, TreeItemLoader } from "@infrahub/ui";
```

- [ ] **Step 2: Verify no other lines need changing**

```bash
grep -n "aria/tree" frontend/app/src/entities/ipam/ipam-tree/ui/ipam-tree.tsx
```

Expected: no output. If anything remains, fix it.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/src/entities/ipam/ipam-tree/ui/ipam-tree.tsx
git commit -m "refactor(ipam): import Tree from @infrahub/ui"
```

---

### Task 5: Migrate `object-hierarchy-tree.tsx` to import from `@infrahub/ui`

**Files:**
- Modify: `frontend/app/src/entities/nodes/hierarchy/ui/object-hierarchy-tree.tsx`

- [ ] **Step 1: Replace the import**

In `frontend/app/src/entities/nodes/hierarchy/ui/object-hierarchy-tree.tsx`, find this line:

```ts
import { Tree, TreeItem, TreeItemContent, TreeItemLoader } from "@/shared/components/aria/tree";
```

Replace with:

```ts
import { Tree, TreeItem, TreeItemContent, TreeItemLoader } from "@infrahub/ui";
```

- [ ] **Step 2: Verify no other lines need changing**

```bash
grep -n "aria/tree" frontend/app/src/entities/nodes/hierarchy/ui/object-hierarchy-tree.tsx
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/src/entities/nodes/hierarchy/ui/object-hierarchy-tree.tsx
git commit -m "refactor(hierarchy): import Tree from @infrahub/ui"
```

---

### Task 6: Migrate `object-hierarchy-tree-lite.tsx` to import from `@infrahub/ui`

**Files:**
- Modify: `frontend/app/src/entities/nodes/hierarchy/ui/object-hierarchy-tree-lite.tsx`

- [ ] **Step 1: Replace the import**

In `frontend/app/src/entities/nodes/hierarchy/ui/object-hierarchy-tree-lite.tsx`, find this line:

```ts
import { Tree } from "@/shared/components/aria/tree";
```

Replace with: nothing here — instead, extend the existing `@infrahub/ui` import on line 1 to include `Tree`.

Find line 1:

```ts
import { Button } from "@infrahub/ui";
```

Replace with:

```ts
import { Button, Tree } from "@infrahub/ui";
```

Then remove the now-unused line:

```ts
import { Tree } from "@/shared/components/aria/tree";
```

- [ ] **Step 2: Verify**

```bash
grep -n "aria/tree" frontend/app/src/entities/nodes/hierarchy/ui/object-hierarchy-tree-lite.tsx
```

Expected: no output.

- [ ] **Step 3: Sort imports / format**

```bash
cd frontend/app && pnpm biome:fix src/entities/nodes/hierarchy/ui/object-hierarchy-tree-lite.tsx
```

Expected: no errors (biome may reorder the imports — that's fine).

- [ ] **Step 4: Commit**

```bash
git add frontend/app/src/entities/nodes/hierarchy/ui/object-hierarchy-tree-lite.tsx
git commit -m "refactor(hierarchy): import Tree from @infrahub/ui"
```

---

### Task 7: Migrate `diff-tree.tsx` to import from `@infrahub/ui`

**Files:**
- Modify: `frontend/app/src/entities/diff/ui/diff-tree.tsx`

- [ ] **Step 1: Replace the import**

In `frontend/app/src/entities/diff/ui/diff-tree.tsx`, find this line:

```ts
import { Tree, TreeItem, TreeItemContent } from "@/shared/components/aria/tree";
```

Replace with:

```ts
import { Tree, TreeItem, TreeItemContent } from "@infrahub/ui";
```

- [ ] **Step 2: Sort imports / format**

```bash
cd frontend/app && pnpm biome:fix src/entities/diff/ui/diff-tree.tsx
```

Expected: no errors.

- [ ] **Step 3: Verify**

```bash
grep -n "aria/tree" frontend/app/src/entities/diff/ui/diff-tree.tsx
```

Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/src/entities/diff/ui/diff-tree.tsx
git commit -m "refactor(diff): import Tree from @infrahub/ui"
```

---

### Task 8: Confirm zero remaining consumers, then delete the source file

**Files:**
- Delete: `frontend/app/src/shared/components/aria/tree.tsx`

- [ ] **Step 1: Grep for any remaining references**

```bash
grep -rn "shared/components/aria/tree" frontend/app/src --include="*.tsx" --include="*.ts"
```

Expected: no output.

If anything still imports from `aria/tree`, stop and migrate it the same way (one-line import swap). Only continue once the grep is empty.

- [ ] **Step 2: Delete the file**

```bash
git rm frontend/app/src/shared/components/aria/tree.tsx
```

- [ ] **Step 3: Commit**

```bash
git commit -m "refactor: remove unused shared/components/aria/tree.tsx"
```

---

### Task 9: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run app type-check + build**

```bash
cd frontend/app && pnpm build
```

Expected: succeeds with no errors. Per project memory, `pnpm build` inside `frontend/packages/ui` is pre-existingly broken — verify via the app build, not the package build.

- [ ] **Step 2: Run unit tests**

```bash
cd frontend/app && pnpm test
```

Expected: all tests pass. No new test files are introduced by this migration, but existing tests that touch the trees should still pass.

- [ ] **Step 3: Run biome over the whole app**

```bash
cd frontend/app && pnpm biome:fix
```

Expected: no errors, no remaining formatting changes.

- [ ] **Step 4: Manual spot-check (browser)**

```bash
cd frontend/app && pnpm dev
```

In the app:
1. Open the IPAM page — IPAM tree renders, expand/collapse works, loader appears when fetching children.
2. Open a diff — diff tree renders, nodes link correctly, selection highlight on current hash works.
3. Open an object detail with hierarchy — object hierarchy tree renders, loader appears under nodes with children, ancestor expansion works.

If any of those break, stop and investigate before declaring the migration complete.

Stop the dev server (`Ctrl-C`) when done.

- [ ] **Step 5: Final commit (if biome made any cleanup-only edits)**

If `git status` shows no remaining changes, skip this step. Otherwise:

```bash
git add -u
git commit -m "chore: biome cleanup after Tree migration"
```

- [ ] **Step 6: Done**

Confirm `git log --oneline` shows the migration commits in order:

```
chore: biome cleanup after Tree migration   (optional)
refactor: remove unused shared/components/aria/tree.tsx
refactor(diff): import Tree from @infrahub/ui
refactor(hierarchy): import Tree from @infrahub/ui   (lite)
refactor(hierarchy): import Tree from @infrahub/ui
refactor(ipam): import Tree from @infrahub/ui
feat(ui): add Storybook stories for Tree
feat(ui): export Tree from @infrahub/ui index
feat(ui): add Tree primitives to @infrahub/ui
```
