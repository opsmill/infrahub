# Modal → `@infrahub/ui` Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `Modal` and `ModalOverlay` (and the internal `Stacked` helper) from `frontend/app/src/shared/components/aria/` into the `@infrahub/ui` package, swap all 9 app callsites to import from `@infrahub/ui`, and delete the legacy files.

**Architecture:** Follows the same pattern used for `Card` (#9048) and `Button` (#9065). Component code is copied with minimal edits — `classNames` swapped to `cn` from `tailwind-variants`, the Stacked import path updated. `Stacked` is placed under `packages/ui/src/utils/` (internal, not exported from the index) so the planned `Sheet` migration can reuse it without reaching into `modal/`.

**Tech Stack:** React 19.2.5, react-aria-components 1.17.0, Tailwind CSS 4.2, tailwind-variants 3.2.2, Vite 8 + Storybook 10.

**Spec:** `docs/superpowers/specs/2026-04-29-modal-package-ui-migration-design.md`

---

## File Structure

**Created in `frontend/packages/ui/`:**
- `src/utils/stacked.tsx` — internal stacking context helper (not exported from `src/index.ts`)
- `src/components/modal/modal.tsx` — `Modal` + `ModalOverlay` + types
- `src/components/modal/modal.stories.tsx` — Default + InfiniteNested stories

**Modified in `frontend/packages/ui/`:**
- `package.json` — add `./modal` subpath export
- `src/index.ts` — re-export `Modal`, `ModalOverlay`, `ModalProps`, `ModalOverlayProps`

**Modified in `frontend/app/src/`:**
- 9 callsite files — replace import path

**Deleted in `frontend/app/src/`:**
- `shared/components/aria/modal.tsx`
- `shared/components/aria/utils/stacked.tsx`
- `shared/components/aria/utils/__screenshots__/` (orphaned snapshot folder; whole tree)

---

## Task 1: Add `Stacked` helper to packages/ui

**Files:**
- Create: `frontend/packages/ui/src/utils/stacked.tsx`

This is a verbatim move from `frontend/app/src/shared/components/aria/utils/stacked.tsx` (no edits — neither this file nor its consumers reference `classNames`).

- [ ] **Step 1: Create the file**

Write `frontend/packages/ui/src/utils/stacked.tsx`:

```tsx
import React from "react";

interface StackContextValue {
  onChildOpen: () => void;
  onChildClose: () => void;
}

const StackContext = React.createContext<StackContextValue>({
  onChildOpen: () => {},
  onChildClose: () => {},
});

interface StackedProps {
  isStacked?: boolean;
  children: (stackOffset: number) => React.ReactNode;
}

export function Stacked({ isStacked, children }: StackedProps) {
  const parent = React.use(StackContext);
  const [layersAbove, setLayersAbove] = React.useState(0);

  React.useLayoutEffect(() => {
    if (!isStacked) return;
    parent.onChildOpen();
    return () => parent.onChildClose();
  }, [isStacked]);

  const onChildOpen = () => {
    setLayersAbove((c) => c + 1);
    parent.onChildOpen();
  };
  const onChildClose = () => {
    setLayersAbove((c) => c - 1);
    parent.onChildClose();
  };

  return <StackContext value={{ onChildOpen, onChildClose }}>{children(layersAbove)}</StackContext>;
}
```

- [ ] **Step 2: Type-check the package in isolation**

Run: `cd frontend/packages/ui && pnpm tsc -b --noEmit`
Expected: no errors. (`tsc -b` follows the package's `tsconfig.json` references; it should compile `src/utils/stacked.tsx` cleanly because `react` is already a dep of `@infrahub/ui`.)

---

## Task 2: Add `Modal` component to packages/ui

**Files:**
- Create: `frontend/packages/ui/src/components/modal/modal.tsx`

Two intentional edits relative to the app version:
1. `classNames` (`@/shared/utils/common`) → `cn` (`tailwind-variants`).
2. `Stacked` import path → `../../utils/stacked`.

- [ ] **Step 1: Create the file**

Write `frontend/packages/ui/src/components/modal/modal.tsx`:

```tsx
import {
  Dialog as AriaDialog,
  Modal as AriaModal,
  ModalOverlay as AriaModalOverlay,
  type DialogProps,
  type ModalOverlayProps as AriaModalOverlayProps,
} from "react-aria-components";
import { cn } from "tailwind-variants";

import { Stacked } from "../../utils/stacked";

export type ModalOverlayProps = AriaModalOverlayProps;

export function ModalOverlay({ className, ...props }: ModalOverlayProps) {
  return (
    <AriaModalOverlay
      isDismissable
      className={cn(
        "absolute inset-0 z-50 overflow-hidden bg-gray-600/25",
        "data-entering:fade-in-0 data-entering:animate-in data-entering:duration-200",
        "data-exiting:fade-out-0 data-exiting:animate-out data-exiting:duration-150",
        className,
      )}
      {...props}
    />
  );
}

export interface ModalProps
  extends Omit<AriaModalOverlayProps, "children">,
    Pick<DialogProps, "aria-label" | "children"> {}

export function Modal({
  "aria-label": ariaLabel,
  children,
  isOpen,
  onOpenChange,
  className,
  isDismissable = true,
  ...props
}: ModalProps) {
  return (
    <ModalOverlay isOpen={isOpen} onOpenChange={onOpenChange} isDismissable={isDismissable}>
      {({ state: { isOpen } }) => (
        <Stacked isStacked={isOpen}>
          {(depth) => (
            <AriaModal
              className={cn(
                "fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 transition-all duration-200",
                "no-scrollbar box-border flex max-h-[calc(var(--visual-viewport-height)*.95)] max-w-[90vw] flex-col overflow-hidden rounded-2xl bg-white p-2 shadow-lg",
                "data-entering:zoom-in-80 data-entering:animate-in data-entering:duration-200 data-entering:ease-out",
                "data-exiting:zoom-out-80 data-exiting:animate-out data-exiting:duration-150 data-exiting:ease-in",
                className,
              )}
              style={{
                top: `${50 - depth * 4}%`,
                scale: 1 - depth * 0.05,
              }}
              {...props}
            >
              <AriaDialog
                aria-label={ariaLabel}
                className="flex h-full min-h-0 w-full min-w-0 flex-col overflow-auto outline-hidden"
              >
                {children}
              </AriaDialog>
            </AriaModal>
          )}
        </Stacked>
      )}
    </ModalOverlay>
  );
}
```

- [ ] **Step 2: Type-check the package**

Run: `cd frontend/packages/ui && pnpm tsc -b --noEmit`
Expected: no errors.

---

## Task 3: Wire up package exports

**Files:**
- Modify: `frontend/packages/ui/package.json`
- Modify: `frontend/packages/ui/src/index.ts`

- [ ] **Step 1: Add `./modal` subpath in `package.json`**

In `frontend/packages/ui/package.json`, replace the current `exports` block:

```jsonc
"exports": {
  ".": "./src/index.ts",
  "./card": "./src/components/card/card.tsx",
  "./styles.css": "./src/index.css"
},
```

with:

```jsonc
"exports": {
  ".": "./src/index.ts",
  "./card": "./src/components/card/card.tsx",
  "./modal": "./src/components/modal/modal.tsx",
  "./styles.css": "./src/index.css"
},
```

- [ ] **Step 2: Re-export from the root `index.ts`**

Append to `frontend/packages/ui/src/index.ts`:

```ts
export {
  Modal,
  ModalOverlay,
  type ModalOverlayProps,
  type ModalProps,
} from "./components/modal/modal";
```

The full file should now read:

```ts
export {
  Button,
  buttonVariants,
  LinkButton,
  type ButtonProps,
  type LinkButtonProps,
} from "./components/button/button";
export { Spinner, type SpinnerProps } from "./components/spinner/spinner";
export {
  Card,
  CardContent,
  CardHeader,
  type CardContentProps,
  type CardHeaderProps,
  type CardProps,
} from "./components/card/card";
export {
  Modal,
  ModalOverlay,
  type ModalOverlayProps,
  type ModalProps,
} from "./components/modal/modal";
```

- [ ] **Step 3: Type-check the package**

Run: `cd frontend/packages/ui && pnpm tsc -b --noEmit`
Expected: no errors.

---

## Task 4: Add Storybook stories

**Files:**
- Create: `frontend/packages/ui/src/components/modal/modal.stories.tsx`

Two stories: `Default` (typical layout) and `InfiniteNested` (recursive modals exercising the `Stacked` math).

- [ ] **Step 1: Create the story file**

Write `frontend/packages/ui/src/components/modal/modal.stories.tsx`:

```tsx
import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";

import { Button } from "../button/button";
import { Modal } from "./modal";

const meta: Meta<typeof Modal> = {
  component: Modal,
  parameters: {
    layout: "centered",
  },
  args: {
    isOpen: true,
    "aria-label": "Example modal",
  },
  argTypes: {
    isOpen: { control: "boolean" },
  },
};

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  render: (args) => (
    <Modal {...args}>
      <div className="flex flex-col gap-3 p-3">
        <h2 className="font-medium text-base text-stone-900">Confirm action</h2>
        <p className="text-neutral-600 text-sm">
          This is a typical modal body. It can contain any content.
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="outline">Cancel</Button>
          <Button>Confirm</Button>
        </div>
      </div>
    </Modal>
  ),
};

function NestedModal({ depth = 0 }: { depth?: number }) {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <>
      <Button onPress={() => setIsOpen(true)}>Open another</Button>
      <Modal
        isOpen={isOpen}
        onOpenChange={setIsOpen}
        aria-label={`Modal level ${depth + 1}`}
      >
        <div className="flex flex-col gap-3 p-3">
          <p className="text-neutral-700 text-sm">Level {depth + 1}</p>
          <NestedModal depth={depth + 1} />
        </div>
      </Modal>
    </>
  );
}

export const InfiniteNested: Story = {
  args: {},
  argTypes: {},
  render: () => <NestedModal />,
};
```

- [ ] **Step 2: Type-check**

Run: `cd frontend/packages/ui && pnpm tsc -b --noEmit`
Expected: no errors.

- [ ] **Step 3: Lint the package**

Run: `cd frontend/packages/ui && pnpm lint`
Expected: clean. If oxlint flags anything, fix the specific issue and re-run.

- [ ] **Step 4: Boot Storybook and visually verify**

Run: `cd frontend/packages/ui && pnpm storybook`

Open the printed URL (typically `http://localhost:6006`). Confirm:
1. The `Modal / Default` story renders with the centered modal, body text, and the two buttons.
2. The `Modal / InfiniteNested` story shows the trigger button. Click it: a modal opens. Click "Open another" inside: a second modal opens, the first scales down and shifts up. Repeat — each new layer stacks. Closing the topmost pops it back.

Stop the dev server with `Ctrl+C`.

---

## Task 5: Commit packages/ui side

- [ ] **Step 1: Stage and verify**

Run:
```bash
git add frontend/packages/ui/src/utils/stacked.tsx \
        frontend/packages/ui/src/components/modal/modal.tsx \
        frontend/packages/ui/src/components/modal/modal.stories.tsx \
        frontend/packages/ui/src/index.ts \
        frontend/packages/ui/package.json
git status
```

Expected: only the five paths above are staged.

- [ ] **Step 2: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(ui): add Modal component

Adds Modal and ModalOverlay to @infrahub/ui (root re-export plus
@infrahub/ui/modal subpath). Internal Stacked helper lives in
src/utils/stacked.tsx so the upcoming Sheet migration can reuse it.

Storybook covers the default usage and an infinite-nested story to
exercise the Stacked depth math.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Update the 9 callsites

**Files modified — exact line replacements:**

| File | Line | Old | New |
|---|---|---|---|
| `frontend/app/src/shared/components/modals/modal-confirm.tsx` | 6 | `import { Modal } from "@/shared/components/aria/modal";` | merge with existing `@infrahub/ui` import (see Step 1) |
| `frontend/app/src/shared/components/modals/modal-delete.tsx` | 6 | `import { Modal } from "@/shared/components/aria/modal";` | `import { Modal } from "@infrahub/ui";` |
| `frontend/app/src/entities/repository/ui/check-connectivity-modal.tsx` | 4 | `import { Modal } from "@/shared/components/aria/modal";` | `import { Modal } from "@infrahub/ui";` |
| `frontend/app/src/entities/config/ui/about-modal.tsx` | 7 | `import { Modal } from "@/shared/components/aria/modal";` | merge with existing `@infrahub/ui` import |
| `frontend/app/src/entities/navigation/ui/search-anywhere/search-anywhere-dialog.tsx` | 3 | `import { ModalOverlay } from "@/shared/components/aria/modal";` | `import { ModalOverlay } from "@infrahub/ui";` |
| `frontend/app/src/entities/schema/ui/computed-attribute-display.tsx` | 6 | `import { Modal } from "@/shared/components/aria/modal";` | `import { Modal } from "@infrahub/ui";` |
| `frontend/app/src/entities/schema/ui/schema-viewer-modal.tsx` | 3 | `import { Modal, type ModalProps } from "@/shared/components/aria/modal";` | `import { Modal, type ModalProps } from "@infrahub/ui";` |
| `frontend/app/src/entities/user-profile/ui/account-token-create-action.tsx` | 7 | `import { Modal } from "@/shared/components/aria/modal";` | `import { Modal } from "@infrahub/ui";` |
| `frontend/app/src/entities/branches/ui/modal-delete-branch.tsx` | 6 | `import { Modal } from "@/shared/components/aria/modal";` | `import { Modal } from "@infrahub/ui";` |

Two of these files (`modal-confirm.tsx` line 2 and `about-modal.tsx`) already import other things from `@infrahub/ui`. Don't create a duplicate import line — merge into the existing one. Biome's import sort will normalize ordering after, but doing it by hand keeps diffs clean.

- [ ] **Step 1: Edit `modal-confirm.tsx`**

In `frontend/app/src/shared/components/modals/modal-confirm.tsx`:

Find:
```ts
import { Button } from "@infrahub/ui";
```
Replace with:
```ts
import { Button, Modal } from "@infrahub/ui";
```

Then delete the line:
```ts
import { Modal } from "@/shared/components/aria/modal";
```

- [ ] **Step 2: Edit `modal-delete.tsx`**

In `frontend/app/src/shared/components/modals/modal-delete.tsx`, find:
```ts
import { Modal } from "@/shared/components/aria/modal";
```
Replace with:
```ts
import { Modal } from "@infrahub/ui";
```

- [ ] **Step 3: Edit `check-connectivity-modal.tsx`**

In `frontend/app/src/entities/repository/ui/check-connectivity-modal.tsx`, find:
```ts
import { Modal } from "@/shared/components/aria/modal";
```
Replace with:
```ts
import { Modal } from "@infrahub/ui";
```

- [ ] **Step 4: Edit `about-modal.tsx`**

In `frontend/app/src/entities/config/ui/about-modal.tsx`:

Find the existing `@infrahub/ui` import (it imports `Button`, possibly with others):
```ts
import { Button } from "@infrahub/ui";
```
(If the existing line already imports more than `Button`, preserve those names; the rule is: add `Modal` to the existing brace list.)

Replace with:
```ts
import { Button, Modal } from "@infrahub/ui";
```

Then delete:
```ts
import { Modal } from "@/shared/components/aria/modal";
```

If the existing `@infrahub/ui` import already contained additional names (e.g. `Spinner`), the new line should list them in the same order Biome would produce — alphabetical: `import { Button, Modal, Spinner } from "@infrahub/ui";`. The `pnpm biome:fix` step at the end of this task will normalize anyway.

- [ ] **Step 5: Edit `search-anywhere-dialog.tsx`**

In `frontend/app/src/entities/navigation/ui/search-anywhere/search-anywhere-dialog.tsx`, find:
```ts
import { ModalOverlay } from "@/shared/components/aria/modal";
```
Replace with:
```ts
import { ModalOverlay } from "@infrahub/ui";
```

- [ ] **Step 6: Edit `computed-attribute-display.tsx`**

In `frontend/app/src/entities/schema/ui/computed-attribute-display.tsx`, find:
```ts
import { Modal } from "@/shared/components/aria/modal";
```
Replace with:
```ts
import { Modal } from "@infrahub/ui";
```

- [ ] **Step 7: Edit `schema-viewer-modal.tsx`**

In `frontend/app/src/entities/schema/ui/schema-viewer-modal.tsx`, find:
```ts
import { Modal, type ModalProps } from "@/shared/components/aria/modal";
```
Replace with:
```ts
import { Modal, type ModalProps } from "@infrahub/ui";
```

- [ ] **Step 8: Edit `account-token-create-action.tsx`**

In `frontend/app/src/entities/user-profile/ui/account-token-create-action.tsx`, find:
```ts
import { Modal } from "@/shared/components/aria/modal";
```
Replace with:
```ts
import { Modal } from "@infrahub/ui";
```

- [ ] **Step 9: Edit `modal-delete-branch.tsx`**

In `frontend/app/src/entities/branches/ui/modal-delete-branch.tsx`, find:
```ts
import { Modal } from "@/shared/components/aria/modal";
```
Replace with:
```ts
import { Modal } from "@infrahub/ui";
```

- [ ] **Step 10: Run Biome to normalize import order**

Run: `cd frontend/app && pnpm biome:fix`
Expected: clean run; biome may reorder import groups in the files just edited.

- [ ] **Step 11: Confirm no remaining references**

Run: `grep -rn "aria/modal" frontend/app/src --include='*.ts' --include='*.tsx'`
Expected: zero hits.

---

## Task 7: Delete the legacy files

**Files:**
- Delete: `frontend/app/src/shared/components/aria/modal.tsx`
- Delete: `frontend/app/src/shared/components/aria/utils/stacked.tsx`
- Delete: `frontend/app/src/shared/components/aria/utils/__screenshots__/` (entire folder; only contains the orphaned `stacked.test.tsx/Stacked-keeps-different-groups-in-independent-stack-chains-1.png`)

- [ ] **Step 1: Delete with git**

Run:
```bash
cd /Users/bilal/opsmill/infrahub
git rm frontend/app/src/shared/components/aria/modal.tsx
git rm frontend/app/src/shared/components/aria/utils/stacked.tsx
git rm -r frontend/app/src/shared/components/aria/utils/__screenshots__
```

Expected: each command prints an `rm` line.

- [ ] **Step 2: Confirm `aria/utils/` is empty (and remove it if so)**

Run: `ls frontend/app/src/shared/components/aria/utils 2>/dev/null || echo "gone"`
Expected: either `gone` (the folder was removed because it became empty) or empty output. If a stray file remains, do not delete it — it's out of scope.

- [ ] **Step 3: Confirm no other references to the deleted paths**

Run:
```bash
grep -rn "aria/utils/stacked\|aria/modal" frontend/app/src --include='*.ts' --include='*.tsx'
```
Expected: zero hits.

---

## Task 8: Type-check, lint, and unit tests

- [ ] **Step 1: Type-check the app**

Run: `cd frontend/app && pnpm tsc --noEmit`
Expected: zero errors.

- [ ] **Step 2: Lint**

Run: `cd frontend/app && pnpm biome:fix`
Expected: clean.

- [ ] **Step 3: Unit tests**

Run: `cd frontend/app && pnpm test`
Expected: all pass. None target Modal directly, but several render screens that mount Modal — they verify the component still renders.

---

## Task 9: Build, e2e, and betterer verification

- [ ] **Step 1: Build the app**

Run: `cd frontend/app && pnpm build`
Expected: build succeeds.

- [ ] **Step 2: E2E spot-check on modal-touching flows**

Run: `cd frontend/app && pnpm test:e2e --grep "modal|delete|branch"`
Expected: pass. (If `--grep` syntax differs in this Playwright config, fall back to running the full suite: `pnpm test:e2e`.)

- [ ] **Step 3: Check `.betterer.results` for unexpected drift**

Run: `cd frontend/app && git diff -- .betterer.results`
Expected: no diff, or only minor numerical drift mirroring file relocations. If betterer regenerates and shows new violations, investigate before committing — a real code quality regression here means the move introduced something unintended.

---

## Task 10: Commit and final sanity check

- [ ] **Step 1: Stage app changes**

Run:
```bash
cd /Users/bilal/opsmill/infrahub
git add frontend/app/src/shared/components/modals/modal-confirm.tsx \
        frontend/app/src/shared/components/modals/modal-delete.tsx \
        frontend/app/src/entities/repository/ui/check-connectivity-modal.tsx \
        frontend/app/src/entities/config/ui/about-modal.tsx \
        frontend/app/src/entities/navigation/ui/search-anywhere/search-anywhere-dialog.tsx \
        frontend/app/src/entities/schema/ui/computed-attribute-display.tsx \
        frontend/app/src/entities/schema/ui/schema-viewer-modal.tsx \
        frontend/app/src/entities/user-profile/ui/account-token-create-action.tsx \
        frontend/app/src/entities/branches/ui/modal-delete-branch.tsx
git add -u frontend/app/src/shared/components/aria/  # picks up the deletions
```

If `.betterer.results` was regenerated in Task 9 Step 3, also stage it:
```bash
git add frontend/app/.betterer.results
```

- [ ] **Step 2: Verify staged set**

Run: `git status`
Expected: nine modified callsites, two deleted source files, one deleted screenshot folder (or files within), and optionally `.betterer.results`. No other files.

- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
refactor: migrate Modal callsites to @infrahub/ui

Updates the 9 callsites of Modal/ModalOverlay to import from
@infrahub/ui and removes the legacy aria/modal.tsx and
aria/utils/stacked.tsx, plus the orphaned screenshot folder.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 4: Final grep**

Run:
```bash
grep -rn "aria/modal\|aria/utils/stacked" frontend/app/src --include='*.ts' --include='*.tsx'
grep -rn "from \"@infrahub/ui\"" frontend/app/src --include='*.ts' --include='*.tsx' | grep -i "modal\|overlay" | head -10
```
Expected: first command zero hits; second shows the new imports.

---

## Self-Review Checklist (informational)

Spec sections covered:
- File layout — Tasks 1, 2, 4
- API surface — Tasks 2, 3
- Package wiring — Task 3
- Storybook stories — Task 4
- Callsite migration — Task 6
- Cleanup — Task 7
- Build sequence — Tasks 5 (commit packages/ui first), 8, 9, 10
- Risks (`React.use`, no `'use client'`, Tailwind scan, `aria-label`, betterer) — Tasks 4 (storybook visual), 8, 9
- Out of scope items (no unit tests, leave sheet screenshots) — explicitly not added.

No placeholders. All file paths are absolute or repo-relative. All commands are runnable as-shown.
