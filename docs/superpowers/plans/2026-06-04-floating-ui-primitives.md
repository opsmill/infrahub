# Floating UI Primitives Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract framework-agnostic floating-UI primitives (`IconButton`, `Toolbar`, `FloatingPanel`, `useDismiss`) into the `@infrahub/ui` design system and adopt them in `path-traversal` (the visual source of truth) and the `schema-visualizer` submodule so both features are consistent.

**Architecture:** Three layers. (1) New primitives live in `@infrahub/ui` and **compose existing DS items** (`Button`, `Card`) — no ReactFlow, no app-only deps. (2) `path-traversal` (main app) swaps its hand-rolled toolbar/panel for the primitives. (3) The `schema-visualizer` submodule (a *separate git repo*) adds `@infrahub/ui` as a dependency and adopts the same primitives. Graph node/edge sharing is explicitly **out of scope** (deferred to a follow-up that will live in the schema-visualizer package).

**Tech Stack:** React 19 + React Compiler, TypeScript, Tailwind v4 (`@tailwindcss/vite`), `react-aria-components`, `tailwind-variants` (`tv`/`cn`), `lucide-react`, Vitest + `vitest-browser-react` + Playwright browser provider, Storybook.

---

## Key constraints (read before starting)

- **`@infrahub/ui` is consumed from source** via `file:../packages/ui` (`main: ./src/index.ts`). New exports MUST be added to `frontend/packages/ui/src/index.ts`. The app's Tailwind already scans `packages/ui/src/**` (via `@source` in `frontend/app/src/app/styles/index.css`), so **no app-side Tailwind wiring is needed**.
- **`@infrahub/ui` has ZERO tests today.** Task 1 stands up the harness by copying the submodule's working config.
- **The submodule is a separate git repo** (`opsmill/infrahub-schema-visualizer` at `frontend/packages/schema-visualizer`). Its changes (Tasks 9–11) are a **separate PR in that repo**, then the main repo bumps the submodule pointer (Task 12). It builds a self-contained IIFE (`vite.config.webview.ts`, `external: []`) — for imported primitives to render *styled*, its `webview.css` must `@source` the ui package (Task 9).
- **Palette:** all three are Tailwind v4; standard `gray-*`/`indigo-*`/`neutral-*` utilities resolve identically everywhere. Do **not** introduce a custom token layer. Primitives carry their own neutral classes; consumers pass accent classes via `className`.
- **Icons:** `FloatingPanel`'s close button uses `lucide-react` (`X`) — already a ui dependency — so the primitive stays consumer-agnostic. Consumers keep using `@iconify-icon/react` for their own content.
- **`onPress` not `onClick`:** primitives wrap react-aria `Button`, which uses `onPress`. The submodule's raw `<button onClick>` call sites convert during adoption (Tasks 10).
- **Commit cadence:** commit after each task's tests pass. Conventional commit messages.

## File structure

**Created in `@infrahub/ui` (`frontend/packages/ui/`):**
- `vitest.config.ts` — test harness config
- `vitest.setup.ts` — imports `./src/index.css` so Tailwind classes resolve in tests
- `src/hooks/use-dismiss.ts` + `src/hooks/use-dismiss.test.tsx`
- `src/components/icon-button/icon-button.tsx` + `.test.tsx` + `.stories.tsx`
- `src/components/toolbar/toolbar.tsx` + `.test.tsx` + `.stories.tsx`
- `src/components/floating-panel/floating-panel.tsx` + `.test.tsx` + `.stories.tsx`

**Modified in `@infrahub/ui`:**
- `package.json` — add `test` script + test devDeps + `exports` subpaths
- `src/index.ts` — barrel exports for the new primitives

**Modified in main app (`frontend/app/`):**
- `src/entities/path-traversal/ui/bottom-toolbar.tsx`
- `src/entities/path-traversal/ui/path-traversal-page.tsx`
- DELETE `src/entities/path-traversal/ui/use-dismiss.ts`
- NEW `src/entities/path-traversal/ui/bottom-toolbar.test.tsx`

**Modified in submodule repo (`frontend/packages/schema-visualizer/`, separate PR):**
- `package.json`, `src/webview.css`
- `src/components/toolbar/bottom-toolbar.tsx` (+ `.test.tsx`)
- `src/components/panels/{legend,node-details,filter}-panel.tsx`
- DELETE `src/hooks/use-dismiss.ts`

---

# UNIT A — `@infrahub/ui` primitives (main repo)

## Task 1: Test harness in `@infrahub/ui`

**Files:**
- Create: `frontend/packages/ui/vitest.config.ts`
- Create: `frontend/packages/ui/vitest.setup.ts`
- Modify: `frontend/packages/ui/package.json`
- Create: `frontend/packages/ui/src/components/button/button.test.tsx` (smoke test)

- [ ] **Step 1: Add test deps + script to `package.json`**

In `frontend/packages/ui/package.json`, add to `"scripts"`:
```json
    "test": "vitest run",
    "test:watch": "vitest watch",
```
Add to `"devDependencies"` (match the submodule's versions — check `frontend/packages/schema-visualizer/package.json` for exact pins, these are the current ones):
```json
    "@vitest/browser": "^4.1.5",
    "@vitest/browser-playwright": "^4.1.5",
    "playwright": "^1.48.0",
    "vitest": "^4.1.5",
    "vitest-browser-react": "^2.2.0",
```

- [ ] **Step 2: Create `vitest.config.ts`**

```ts
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { playwright } from "@vitest/browser-playwright";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [tailwindcss(), react()],
  test: {
    setupFiles: ["./vitest.setup.ts"],
    browser: {
      enabled: true,
      headless: true,
      provider: playwright(),
      instances: [{ browser: "chromium" }],
    },
    include: ["src/**/*.test.{ts,tsx}"],
    screenshotFailures: false,
  },
});
```

- [ ] **Step 3: Create `vitest.setup.ts`**

```ts
import "./src/index.css";
```

- [ ] **Step 4: Install deps**

Run: `cd frontend/app && pnpm install`
Expected: installs the new ui devDeps via the workspace.

- [ ] **Step 5: Write a smoke test on the existing Button**

`frontend/packages/ui/src/components/button/button.test.tsx`:
```tsx
import { describe, expect, test } from "vitest";
import { render } from "vitest-browser-react";

import { Button } from "./button";

describe("Button (harness smoke test)", () => {
  test("renders an accessible button", async () => {
    // GIVEN a button with a label
    const component = render(<Button>Click me</Button>);

    // THEN it is reachable by role + name
    await expect.element(component.getByRole("button", { name: "Click me" })).toBeVisible();
  });
});
```

- [ ] **Step 6: Run the smoke test**

Run: `cd frontend/packages/ui && pnpm test`
Expected: PASS (1 test). This proves the browser test runner works in the package.

- [ ] **Step 7: Commit**

```bash
git add frontend/packages/ui/vitest.config.ts frontend/packages/ui/vitest.setup.ts frontend/packages/ui/package.json frontend/packages/ui/src/components/button/button.test.tsx frontend/app/pnpm-lock.yaml
git commit -m "test(ui): establish vitest browser harness in @infrahub/ui"
```

---

## Task 2: `useDismiss` hook

**Files:**
- Create: `frontend/packages/ui/src/hooks/use-dismiss.ts`
- Create: `frontend/packages/ui/src/hooks/use-dismiss.test.tsx`
- Modify: `frontend/packages/ui/src/index.ts`

- [ ] **Step 1: Write the failing test**

`frontend/packages/ui/src/hooks/use-dismiss.test.tsx`:
```tsx
import { useRef } from "react";
import { describe, expect, test, vi } from "vitest";
import { userEvent } from "vitest/browser";
import { render } from "vitest-browser-react";

import { useDismiss } from "./use-dismiss";

function Harness({ onDismiss, active }: { onDismiss: () => void; active?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useDismiss(ref, onDismiss, active);
  return (
    <div>
      <button type="button">outside</button>
      <div ref={ref}>
        <button type="button">inside</button>
      </div>
    </div>
  );
}

describe("useDismiss", () => {
  test("calls onDismiss when clicking outside the ref", async () => {
    // GIVEN
    const onDismiss = vi.fn();
    const component = render(<Harness onDismiss={onDismiss} active />);

    // WHEN clicking outside
    await component.getByRole("button", { name: "outside" }).click();

    // THEN
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  test("does not call onDismiss when clicking inside the ref", async () => {
    // GIVEN
    const onDismiss = vi.fn();
    const component = render(<Harness onDismiss={onDismiss} active />);

    // WHEN clicking inside
    await component.getByRole("button", { name: "inside" }).click();

    // THEN
    expect(onDismiss).not.toHaveBeenCalled();
  });

  test("calls onDismiss when pressing Escape", async () => {
    // GIVEN
    const onDismiss = vi.fn();
    render(<Harness onDismiss={onDismiss} active />);

    // WHEN pressing Escape
    await userEvent.keyboard("{Escape}");

    // THEN
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  test("does nothing when active is false", async () => {
    // GIVEN
    const onDismiss = vi.fn();
    const component = render(<Harness onDismiss={onDismiss} active={false} />);

    // WHEN clicking outside and pressing Escape
    await component.getByRole("button", { name: "outside" }).click();
    await userEvent.keyboard("{Escape}");

    // THEN
    expect(onDismiss).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend/packages/ui && pnpm test use-dismiss`
Expected: FAIL — cannot resolve `./use-dismiss`.

- [ ] **Step 3: Implement the hook** (lifted verbatim from the path-traversal copy, which uses the safer `onDismissRef`)

`frontend/packages/ui/src/hooks/use-dismiss.ts`:
```ts
import { type RefObject, useEffect, useRef } from "react";

export function useDismiss(
  ref: RefObject<HTMLElement | null>,
  onDismiss: () => void,
  active = true,
) {
  const onDismissRef = useRef(onDismiss);
  onDismissRef.current = onDismiss;

  useEffect(() => {
    if (!active) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        onDismissRef.current();
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onDismissRef.current();
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [ref, active]);
}
```

- [ ] **Step 4: Export from the barrel**

In `frontend/packages/ui/src/index.ts`, add:
```ts
export { useDismiss } from "./hooks/use-dismiss";
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd frontend/packages/ui && pnpm test use-dismiss`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/packages/ui/src/hooks/use-dismiss.ts frontend/packages/ui/src/hooks/use-dismiss.test.tsx frontend/packages/ui/src/index.ts
git commit -m "feat(ui): add shared useDismiss hook"
```

---

## Task 3: `IconButton`

**Files:**
- Create: `frontend/packages/ui/src/components/icon-button/icon-button.tsx`
- Create: `frontend/packages/ui/src/components/icon-button/icon-button.test.tsx`
- Create: `frontend/packages/ui/src/components/icon-button/icon-button.stories.tsx`
- Modify: `frontend/packages/ui/src/index.ts`

- [ ] **Step 1: Write the failing test**

`frontend/packages/ui/src/components/icon-button/icon-button.test.tsx`:
```tsx
import { describe, expect, test, vi } from "vitest";
import { render } from "vitest-browser-react";

import { IconButton } from "./icon-button";

describe("IconButton", () => {
  test("exposes its accessible name from aria-label", async () => {
    // GIVEN an icon-only button with an aria-label
    const component = render(
      <IconButton aria-label="Zoom in">
        <svg aria-hidden="true" />
      </IconButton>,
    );

    // THEN it is reachable by role + accessible name
    await expect.element(component.getByRole("button", { name: "Zoom in" })).toBeVisible();
  });

  test("fires onPress when activated", async () => {
    // GIVEN
    const onPress = vi.fn();
    const component = render(
      <IconButton aria-label="Reload" onPress={onPress}>
        <svg aria-hidden="true" />
      </IconButton>,
    );

    // WHEN pressed
    await component.getByRole("button", { name: "Reload" }).click();

    // THEN
    expect(onPress).toHaveBeenCalledTimes(1);
  });

  test("does not fire onPress when disabled", async () => {
    // GIVEN
    const onPress = vi.fn();
    const component = render(
      <IconButton aria-label="Reload" onPress={onPress} isDisabled>
        <svg aria-hidden="true" />
      </IconButton>,
    );

    // WHEN pressed
    await component.getByRole("button", { name: "Reload" }).click();

    // THEN
    expect(onPress).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend/packages/ui && pnpm test icon-button`
Expected: FAIL — cannot resolve `./icon-button`.

- [ ] **Step 3: Implement IconButton** (wraps `Button`, makes `aria-label` required, defaults to a square ghost icon button)

`frontend/packages/ui/src/components/icon-button/icon-button.tsx`:
```tsx
import { Button, type ButtonProps } from "../button/button";

export type IconButtonProps = Omit<ButtonProps, "aria-label"> & {
  "aria-label": string;
};

/** Square, ghost-by-default icon button. Requires an aria-label for accessibility. */
export function IconButton({
  variant = "ghost",
  size = "sm",
  shape = "square",
  ...props
}: IconButtonProps) {
  return <Button variant={variant} size={size} shape={shape} {...props} />;
}
```

- [ ] **Step 4: Export from the barrel**

In `frontend/packages/ui/src/index.ts`, add:
```ts
export { IconButton, type IconButtonProps } from "./components/icon-button/icon-button";
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd frontend/packages/ui && pnpm test icon-button`
Expected: PASS (3 tests).

- [ ] **Step 6: Add a Storybook story**

`frontend/packages/ui/src/components/icon-button/icon-button.stories.tsx`:
```tsx
import type { Meta, StoryObj } from "@storybook/react-vite";
import { Plus } from "lucide-react";

import { IconButton } from "./icon-button";

const meta: Meta<typeof IconButton> = {
  title: "Components/IconButton",
  component: IconButton,
};
export default meta;

type Story = StoryObj<typeof IconButton>;

export const Default: Story = {
  args: { "aria-label": "Add", children: <Plus /> },
};
```

- [ ] **Step 7: Commit**

```bash
git add frontend/packages/ui/src/components/icon-button/ frontend/packages/ui/src/index.ts
git commit -m "feat(ui): add IconButton primitive"
```

---

## Task 4: `Toolbar` + `Toolbar.Divider`

**Files:**
- Create: `frontend/packages/ui/src/components/toolbar/toolbar.tsx`
- Create: `frontend/packages/ui/src/components/toolbar/toolbar.test.tsx`
- Create: `frontend/packages/ui/src/components/toolbar/toolbar.stories.tsx`
- Modify: `frontend/packages/ui/src/index.ts`

- [ ] **Step 1: Write the failing test**

`frontend/packages/ui/src/components/toolbar/toolbar.test.tsx`:
```tsx
import { describe, expect, test } from "vitest";
import { render } from "vitest-browser-react";

import { IconButton } from "../icon-button/icon-button";
import { Toolbar } from "./toolbar";

describe("Toolbar", () => {
  test("renders with the toolbar role and accessible name", async () => {
    // GIVEN
    const component = render(
      <Toolbar aria-label="Graph controls">
        <IconButton aria-label="Zoom in">
          <svg aria-hidden="true" />
        </IconButton>
      </Toolbar>,
    );

    // THEN
    await expect
      .element(component.getByRole("toolbar", { name: "Graph controls" }))
      .toBeVisible();
  });

  test("renders child controls reachable by name", async () => {
    // GIVEN
    const component = render(
      <Toolbar aria-label="Graph controls">
        <IconButton aria-label="Zoom in">
          <svg aria-hidden="true" />
        </IconButton>
        <Toolbar.Divider />
        <IconButton aria-label="Zoom out">
          <svg aria-hidden="true" />
        </IconButton>
      </Toolbar>,
    );

    // THEN both buttons + the separator exist
    await expect.element(component.getByRole("button", { name: "Zoom in" })).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Zoom out" })).toBeVisible();
    await expect.element(component.getByRole("separator")).toBeVisible();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend/packages/ui && pnpm test toolbar`
Expected: FAIL — cannot resolve `./toolbar`.

- [ ] **Step 3: Implement Toolbar**

`frontend/packages/ui/src/components/toolbar/toolbar.tsx`:
```tsx
import type { HTMLAttributes } from "react";
import { cn } from "tailwind-variants";

export interface ToolbarProps extends HTMLAttributes<HTMLDivElement> {
  "aria-label"?: string;
}

export function Toolbar({ className, ...props }: ToolbarProps) {
  return (
    <div
      role="toolbar"
      className={cn(
        "flex items-center gap-2 rounded-lg bg-white px-3 py-2 shadow-lg",
        className,
      )}
      {...props}
    />
  );
}

function ToolbarDivider({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      role="separator"
      aria-orientation="vertical"
      className={cn("h-6 w-px bg-gray-200", className)}
      {...props}
    />
  );
}

Toolbar.Divider = ToolbarDivider;
```

- [ ] **Step 4: Export from the barrel**

In `frontend/packages/ui/src/index.ts`, add:
```ts
export { Toolbar, type ToolbarProps } from "./components/toolbar/toolbar";
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd frontend/packages/ui && pnpm test toolbar`
Expected: PASS (2 tests).

- [ ] **Step 6: Add a Storybook story**

`frontend/packages/ui/src/components/toolbar/toolbar.stories.tsx`:
```tsx
import type { Meta, StoryObj } from "@storybook/react-vite";
import { Minus, Plus } from "lucide-react";

import { IconButton } from "../icon-button/icon-button";
import { Toolbar } from "./toolbar";

const meta: Meta<typeof Toolbar> = {
  title: "Components/Toolbar",
  component: Toolbar,
};
export default meta;

type Story = StoryObj<typeof Toolbar>;

export const Default: Story = {
  render: () => (
    <Toolbar aria-label="Example controls">
      <IconButton aria-label="Zoom out">
        <Minus />
      </IconButton>
      <Toolbar.Divider />
      <IconButton aria-label="Zoom in">
        <Plus />
      </IconButton>
    </Toolbar>
  ),
};
```

- [ ] **Step 7: Commit**

```bash
git add frontend/packages/ui/src/components/toolbar/ frontend/packages/ui/src/index.ts
git commit -m "feat(ui): add Toolbar primitive with Divider"
```

---

## Task 5: `FloatingPanel`

**Files:**
- Create: `frontend/packages/ui/src/components/floating-panel/floating-panel.tsx`
- Create: `frontend/packages/ui/src/components/floating-panel/floating-panel.test.tsx`
- Create: `frontend/packages/ui/src/components/floating-panel/floating-panel.stories.tsx`
- Modify: `frontend/packages/ui/src/index.ts`

- [ ] **Step 1: Write the failing test**

`frontend/packages/ui/src/components/floating-panel/floating-panel.test.tsx`:
```tsx
import { describe, expect, test, vi } from "vitest";
import { userEvent } from "vitest/browser";
import { render } from "vitest-browser-react";

import { FloatingPanel } from "./floating-panel";

describe("FloatingPanel", () => {
  test("renders title, description and body", async () => {
    // GIVEN
    const component = render(
      <FloatingPanel title="Filters" description="Refine results" onClose={() => {}}>
        <p>Body content</p>
      </FloatingPanel>,
    );

    // THEN
    await expect.element(component.getByRole("heading", { name: "Filters" })).toBeVisible();
    await expect.element(component.getByText("Refine results")).toBeVisible();
    await expect.element(component.getByText("Body content")).toBeVisible();
  });

  test("renders nothing when isOpen is false", async () => {
    // GIVEN
    const component = render(
      <FloatingPanel title="Filters" isOpen={false} onClose={() => {}}>
        <p>Body content</p>
      </FloatingPanel>,
    );

    // THEN
    expect(component.container.textContent).not.toContain("Filters");
    expect(component.container.textContent).not.toContain("Body content");
  });

  test("calls onClose when the close button is pressed", async () => {
    // GIVEN
    const onClose = vi.fn();
    const component = render(
      <FloatingPanel title="Filters" onClose={onClose}>
        <p>Body</p>
      </FloatingPanel>,
    );

    // WHEN
    await component.getByRole("button", { name: "Close panel" }).click();

    // THEN
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("when dismissable, Escape calls onClose", async () => {
    // GIVEN
    const onClose = vi.fn();
    render(
      <FloatingPanel title="Filters" onClose={onClose} dismissable>
        <p>Body</p>
      </FloatingPanel>,
    );

    // WHEN
    await userEvent.keyboard("{Escape}");

    // THEN
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("when NOT dismissable, Escape does not call onClose", async () => {
    // GIVEN
    const onClose = vi.fn();
    render(
      <FloatingPanel title="Filters" onClose={onClose}>
        <p>Body</p>
      </FloatingPanel>,
    );

    // WHEN
    await userEvent.keyboard("{Escape}");

    // THEN
    expect(onClose).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend/packages/ui && pnpm test floating-panel`
Expected: FAIL — cannot resolve `./floating-panel`.

- [ ] **Step 3: Implement FloatingPanel** (composes `Card`/`CardHeader`/`CardContent` + `IconButton` + `useDismiss`)

`frontend/packages/ui/src/components/floating-panel/floating-panel.tsx`:
```tsx
import { X } from "lucide-react";
import { type ReactNode, useRef } from "react";
import { cn } from "tailwind-variants";

import { useDismiss } from "../../hooks/use-dismiss";
import { Card, CardContent, CardHeader } from "../card/card";
import { IconButton } from "../icon-button/icon-button";

export interface FloatingPanelProps {
  title: ReactNode;
  description?: ReactNode;
  onClose: () => void;
  /** Defaults to true. When false the panel renders nothing. */
  isOpen?: boolean;
  /** When true, outside-click and Escape call onClose. Defaults to false. */
  dismissable?: boolean;
  /** Positioning + sizing classes supplied by the consumer (e.g. absolute inset/width). */
  className?: string;
  /** Optional extra header row rendered below the title (e.g. tabs). */
  headerContent?: ReactNode;
  /** Accessible label for the close button. */
  closeLabel?: string;
  children: ReactNode;
}

export function FloatingPanel({
  title,
  description,
  onClose,
  isOpen = true,
  dismissable = false,
  className,
  headerContent,
  closeLabel = "Close panel",
  children,
}: FloatingPanelProps) {
  const ref = useRef<HTMLDivElement>(null);
  useDismiss(ref, onClose, isOpen && dismissable);

  if (!isOpen) return null;

  return (
    <Card ref={ref} className={cn("overflow-hidden", className)}>
      <CardHeader className="p-4">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h2 className="font-semibold text-lg text-neutral-900">{title}</h2>
            {description && <p className="mt-1 text-neutral-500 text-sm">{description}</p>}
          </div>
          <IconButton
            aria-label={closeLabel}
            size="xs"
            onPress={onClose}
            className="-mt-1 -mr-1 text-neutral-400"
          >
            <X className="size-4" />
          </IconButton>
        </div>
        {headerContent}
      </CardHeader>
      <CardContent className="flex-1 overflow-y-auto p-0">{children}</CardContent>
    </Card>
  );
}
```

> Note: `CardHeader` renders `font-medium text-sm` by default; the `h2` here overrides to `text-lg` to match path-traversal's source-of-truth header. `size="xs"` is a valid `Button` size.

- [ ] **Step 4: Export from the barrel**

In `frontend/packages/ui/src/index.ts`, add:
```ts
export { FloatingPanel, type FloatingPanelProps } from "./components/floating-panel/floating-panel";
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd frontend/packages/ui && pnpm test floating-panel`
Expected: PASS (5 tests).

- [ ] **Step 6: Add a Storybook story**

`frontend/packages/ui/src/components/floating-panel/floating-panel.stories.tsx`:
```tsx
import type { Meta, StoryObj } from "@storybook/react-vite";

import { FloatingPanel } from "./floating-panel";

const meta: Meta<typeof FloatingPanel> = {
  title: "Components/FloatingPanel",
  component: FloatingPanel,
};
export default meta;

type Story = StoryObj<typeof FloatingPanel>;

export const Default: Story = {
  args: {
    title: "Path Traversal",
    description: "Find paths between two objects in the graph.",
    className: "w-80",
    children: <div className="p-4 text-sm">Panel body</div>,
  },
};
```

- [ ] **Step 7: Run the full ui test suite**

Run: `cd frontend/packages/ui && pnpm test`
Expected: all tests PASS. NOTE: `pnpm build` currently fails on a **pre-existing** `tsconfig` `TS5101` (`baseUrl` deprecation) already present on `develop` — not introduced by this work and not gating, because the app consumes `@infrahub/ui` from source (no built artifact required). Fixing that deprecation is out of scope here.

- [ ] **Step 8: Commit**

```bash
git add frontend/packages/ui/src/components/floating-panel/ frontend/packages/ui/src/index.ts
git commit -m "feat(ui): add FloatingPanel primitive"
```

---

## Task 6: Subpath exports (consistency)

**Files:**
- Modify: `frontend/packages/ui/package.json`

- [ ] **Step 1: Add subpath exports** mirroring the existing `./card` / `./modal` entries.

In `frontend/packages/ui/package.json` `"exports"`, add:
```json
    "./icon-button": "./src/components/icon-button/icon-button.tsx",
    "./toolbar": "./src/components/toolbar/toolbar.tsx",
    "./floating-panel": "./src/components/floating-panel/floating-panel.tsx",
    "./use-dismiss": "./src/hooks/use-dismiss.ts",
```

- [ ] **Step 2: Verify the barrel still resolves**

Run: `cd frontend/packages/ui && pnpm test`
Expected: all tests PASS — the new subpath exports resolve (tests import via the barrel). `pnpm build` is **not** used as a gate: it fails on the pre-existing `TS5101` deprecation noted in Task 5 Step 7.

- [ ] **Step 3: Commit**

```bash
git add frontend/packages/ui/package.json
git commit -m "chore(ui): add subpath exports for new primitives"
```

---

# UNIT B — path-traversal adoption (main repo)

## Task 7: Regression test for `bottom-toolbar.tsx` (before refactor)

**Files:**
- Create: `frontend/app/src/entities/path-traversal/ui/bottom-toolbar.test.tsx`

- [ ] **Step 1: Write the regression test against CURRENT behavior**

This test must pass against the existing component AND after the refactor. The current buttons get their accessible name from the wrapping `Tooltip`'s `message`; assert via `getByRole("button", { name })`. Mock `@xyflow/react` (the component calls `useReactFlow` and renders `Panel`).

`frontend/app/src/entities/path-traversal/ui/bottom-toolbar.test.tsx`:
```tsx
import { describe, expect, test, vi } from "vitest";
import { render } from "../../../../tests/components/render";

import { BottomToolbar } from "./bottom-toolbar";

vi.mock("@xyflow/react", () => ({
  Panel: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div className={className}>{children}</div>
  ),
  useReactFlow: () => ({ zoomIn: vi.fn(), zoomOut: vi.fn(), fitView: vi.fn() }),
}));

function setup(overrides = {}) {
  const props = {
    onParametersClick: vi.fn(),
    isParametersOpen: false,
    edgeStyle: "bezier" as const,
    onEdgeStyleChange: vi.fn(),
    onLayout: vi.fn(),
    onExport: vi.fn(),
    ...overrides,
  };
  return { props, component: render(<BottomToolbar {...props} />) };
}

describe("BottomToolbar", () => {
  test("renders the zoom and layout controls by accessible name", async () => {
    // GIVEN / WHEN
    const { component } = setup();

    // THEN
    await expect.element(component.getByRole("button", { name: "Zoom out" })).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Zoom in" })).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Fit to screen" })).toBeVisible();
  });

  test("toggles parameters when the parameters button is pressed", async () => {
    // GIVEN
    const { props, component } = setup();

    // WHEN
    await component.getByRole("button", { name: "Show parameters" }).click();

    // THEN
    expect(props.onParametersClick).toHaveBeenCalledTimes(1);
  });

  test("flips the edge style when toggled", async () => {
    // GIVEN
    const { props, component } = setup({ edgeStyle: "bezier" });

    // WHEN
    await component.getByRole("button", { name: /Switch to step edges/ }).click();

    // THEN
    expect(props.onEdgeStyleChange).toHaveBeenCalledWith("smoothstep");
  });
});
```

> The current `BottomToolbar` already sets accessible names via `Tooltip message=...`. If a query fails because the name comes only from the tooltip and not the button, that's the signal to add `aria-label` during the refactor (Step 4) — which is desirable anyway.

- [ ] **Step 2: Run the test**

Run: `cd frontend/app && pnpm test bottom-toolbar`
Expected: PASS (or reveals which buttons lack accessible names — note them for Step 4).

- [ ] **Step 3: Commit**

```bash
git add frontend/app/src/entities/path-traversal/ui/bottom-toolbar.test.tsx
git commit -m "test(path-traversal): cover BottomToolbar behavior before refactor"
```

---

## Task 8: Refactor `bottom-toolbar.tsx` to use the primitives

**Files:**
- Modify: `frontend/app/src/entities/path-traversal/ui/bottom-toolbar.tsx`
- Delete: `frontend/app/src/entities/path-traversal/ui/use-dismiss.ts`

- [ ] **Step 1: Update imports**

Replace:
```tsx
import { Button } from "@infrahub/ui";
```
with:
```tsx
import { Button, IconButton, Toolbar, useDismiss } from "@infrahub/ui";
```
Remove the local import:
```tsx
import { useDismiss } from "./use-dismiss";
```

- [ ] **Step 2: Replace the `Panel` container's visual classes with `Toolbar`**

Keep the ReactFlow `Panel` as the positioner; move the visual classes onto `Toolbar`:
```tsx
    <Panel position="bottom-center">
      <Toolbar aria-label="Graph controls" className="mb-4">
        {/* ...buttons... */}
      </Toolbar>
    </Panel>
```
(The `rounded-lg bg-white px-3 py-2 shadow-lg flex items-center gap-2` classes now come from `Toolbar`; keep `mb-4` for the bottom offset.)

- [ ] **Step 3: Replace square icon `Button`s with `IconButton`** and add `aria-label`

For each `<Button variant="ghost" size="sm" shape="square" ...>` that contains only an icon, convert to:
```tsx
      <Tooltip message="Zoom out">
        <IconButton aria-label="Zoom out" onPress={() => zoomOut()} className="text-gray-600">
          <Icon icon="mdi:minus" className="text-lg" />
        </IconButton>
      </Tooltip>
```
Apply to: Zoom out, Fit to screen, Zoom in, Auto-layout horizontal, Auto-layout vertical, parameters toggle, reload, export trigger. **Keep the edge-style button as a plain `Button`** (it has a text label, not icon-only). For the active states keep the existing conditional `className` (`bg-indigo-500 text-white data-hovered:bg-indigo-600`).

- [ ] **Step 4: Replace divider `<div>`s with `Toolbar.Divider`**

Replace each `<div className="mx-2 h-6 w-px bg-gray-200" />` with `<Toolbar.Divider className="mx-2" />`.

- [ ] **Step 5: Delete the local hook**

```bash
git rm frontend/app/src/entities/path-traversal/ui/use-dismiss.ts
```
(`useDismiss` now comes from `@infrahub/ui`; the `useDismiss(exportMenuRef, closeExportMenu, exportMenuOpen)` call is unchanged.)

- [ ] **Step 6: Run the regression test + typecheck**

Run: `cd frontend/app && pnpm test bottom-toolbar && pnpm exec tsc --noEmit`
Expected: PASS, no type errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/app/src/entities/path-traversal/ui/bottom-toolbar.tsx
git commit -m "refactor(path-traversal): adopt Toolbar/IconButton/useDismiss primitives"
```

---

## Task 9: Refactor `path-traversal-page.tsx` panel to `FloatingPanel`

**Files:**
- Modify: `frontend/app/src/entities/path-traversal/ui/path-traversal-page.tsx`

- [ ] **Step 1: Update imports**

Add `FloatingPanel` and `Button` from `@infrahub/ui`; remove the `Content` import if it becomes unused (verify other `Content.*` usages first — `Content` may still be used elsewhere in the file).
```tsx
import { Button, FloatingPanel } from "@infrahub/ui";
```

- [ ] **Step 2: Replace the `Content.Card` block with `FloatingPanel`**

Replace the entire `{parametersOpen && (<Content.Card ...> ... </Content.Card>)}` block (the header with title/description/close + the mode-toggle row + the sidebar body) with:
```tsx
      {parametersOpen && (
        <FloatingPanel
          title={meta.title}
          description={meta.description}
          onClose={toggleParameters}
          className="absolute top-4 right-4 bottom-4 z-10 flex w-80 flex-col shadow-xl"
          headerContent={
            <div className="mt-2 flex gap-1">
              {MODES.map((m) => (
                <Button
                  key={m}
                  variant="ghost"
                  size="xs"
                  onPress={() => setMode(m)}
                  className={`flex-1 font-medium text-xs ${
                    mode === m ? MODE_META[m].activeClass : "text-gray-500"
                  }`}
                >
                  {MODE_LABELS[m]}
                </Button>
              ))}
            </div>
          }
        >
          {mode === "path" ? <PathModeSidebar /> : <DependenciesModeSidebar />}
        </FloatingPanel>
      )}
```
The close button + header layout now come from `FloatingPanel`; the mode toggle moves into `headerContent`; the sidebar becomes the scrollable body. Remove the now-unused `Icon`/`Tooltip` imports if they are no longer referenced in this file.

- [ ] **Step 3: Typecheck + build**

Run: `cd frontend/app && pnpm exec tsc --noEmit`
Expected: no type errors. Fix any unused-import lint via `pnpm biome:fix`.

- [ ] **Step 4: Manual visual parity check (source of truth)**

Run: `cd frontend/app && pnpm dev`, open the path-traversal page. Verify the panel matches the previous look (top-right floating card, header, close button, mode tabs, scrollable results) and the bottom toolbar is unchanged. The parameters panel should NOT close on outside click (we left `dismissable` off to preserve current behavior).

- [ ] **Step 5: Commit**

```bash
git add frontend/app/src/entities/path-traversal/ui/path-traversal-page.tsx
git commit -m "refactor(path-traversal): adopt FloatingPanel for the parameters panel"
```

---

## Task 10: Verify the main-repo unit (CI gate for the app PR)

- [ ] **Step 1: Run the app checks**

Run: `cd frontend/app && pnpm biome:fix && pnpm test && pnpm build`
Expected: format/lint clean, tests pass, build succeeds.

- [ ] **Step 2: Run the ui package checks**

Run: `cd frontend/packages/ui && pnpm test && pnpm build`
Expected: pass.

> Unit A + B form a self-contained, mergeable main-repo PR. The submodule work (Unit C) is a separate PR; Task 12 bumps the pointer afterward.

---

# UNIT C — schema-visualizer adoption (SEPARATE submodule repo)

> These tasks land as a **separate PR in the `opsmill/infrahub-schema-visualizer` repo**. Work inside `frontend/packages/schema-visualizer` and commit there (it is its own git repo). The submodule already has a working vitest harness — no Task-1 equivalent needed.

## Task 11: Add `@infrahub/ui` dependency + Tailwind scan

**Files:**
- Modify: `frontend/packages/schema-visualizer/package.json`
- Modify: `frontend/packages/schema-visualizer/src/webview.css`

- [ ] **Step 1: Add the dependency**

In `frontend/packages/schema-visualizer/package.json` `"dependencies"`, add (mirror how the app links it):
```json
    "@infrahub/ui": "file:../ui",
```

- [ ] **Step 2: Make Tailwind scan the ui source** so the IIFE bundle generates the primitives' utility classes.

In `frontend/packages/schema-visualizer/src/webview.css`, add near the existing `@import "tailwindcss"`:
```css
@source "../../ui/src/**/*.{ts,tsx}";
```
(Adjust the relative path so it resolves from `webview.css` to `packages/ui/src`. Verify the path against the file's actual location.)

- [ ] **Step 3: Install + build the webview bundle**

Run: `cd frontend/packages/schema-visualizer && pnpm install && pnpm build`
Expected: build succeeds; `@infrahub/ui` source (react-aria, lucide, tailwind-variants) bundles into the IIFE. If Vite complains about un-optimized deps, add them to `optimizeDeps.include` in `vite.config.webview.ts`.

- [ ] **Step 4: Commit (in the submodule repo)**

```bash
cd frontend/packages/schema-visualizer
git add package.json src/webview.css pnpm-lock.yaml
git commit -m "build: depend on @infrahub/ui and scan it for Tailwind classes"
```

---

## Task 12: Adopt primitives in the submodule toolbar + panels

**Files:**
- Modify: `frontend/packages/schema-visualizer/src/components/toolbar/bottom-toolbar.tsx`
- Modify: `frontend/packages/schema-visualizer/src/components/panels/legend-panel.tsx`
- Modify: `frontend/packages/schema-visualizer/src/components/panels/node-details-panel.tsx`
- Modify: `frontend/packages/schema-visualizer/src/components/panels/filter-panel.tsx`
- Delete: `frontend/packages/schema-visualizer/src/hooks/use-dismiss.ts`
- Create: `frontend/packages/schema-visualizer/src/components/toolbar/bottom-toolbar.test.tsx`

- [ ] **Step 1: Write a regression test for the toolbar (current behavior)**

Mirror the path-traversal test, mocking `@xyflow/react`. Today the submodule buttons use `title` (not `aria-label`); query by `getByTitle` first, then switch to `getByRole({name})` after the refactor adds labels.
```tsx
import { describe, expect, test, vi } from "vitest";
import { render } from "vitest-browser-react";

import { BottomToolbar } from "./bottom-toolbar";

vi.mock("@xyflow/react", () => ({
  Panel: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  useReactFlow: () => ({ zoomIn: vi.fn(), zoomOut: vi.fn(), fitView: vi.fn() }),
}));

describe("BottomToolbar (schema-visualizer)", () => {
  test("renders zoom controls", async () => {
    const component = render(<BottomToolbar /* required props */ />);
    await expect.element(component.getByRole("button", { name: "Zoom in" })).toBeVisible();
  });
});
```
(Fill in the real required props from the current component signature.)

- [ ] **Step 2: Run it**

Run: `cd frontend/packages/schema-visualizer && pnpm test bottom-toolbar`
Expected: PASS against current behavior (adjust queries to `getByTitle` if names aren't set yet).

- [ ] **Step 3: Refactor the toolbar** — same pattern as path-traversal Task 8: wrap in `Toolbar`, swap raw `<button h-8 w-8 ...>` for `IconButton aria-label=...`, convert `onClick`→`onPress`, dividers → `Toolbar.Divider`, import `useDismiss` from `@infrahub/ui` for the export menu.

- [ ] **Step 4: Refactor the panels** — replace each hand-rolled `bg-white rounded-lg shadow-lg border ...` container that has a header + close button (`legend-panel`, `node-details-panel`, `filter-panel`) with `<FloatingPanel title=... onClose=...>`. Keep each panel's ReactFlow `<Panel position=...>` wrapper for positioning where present (e.g. legend's `top-right`). **Leave `stats-panel.tsx` as-is** (no existing close affordance — do not invent one).

- [ ] **Step 5: Delete the local hook**

```bash
cd frontend/packages/schema-visualizer
git rm src/hooks/use-dismiss.ts
```
Update any remaining importers to use `@infrahub/ui`'s `useDismiss`.

- [ ] **Step 6: Run tests + build + verify styled in the webview**

Run: `cd frontend/packages/schema-visualizer && pnpm test && pnpm build`
Expected: all tests pass (incl. existing `schema-node.test.tsx`), build succeeds. Load the built webview and confirm the toolbar/panels render **styled** (this validates the Task 11 `@source` line).

- [ ] **Step 7: Commit (in the submodule repo) + open the submodule PR**

```bash
cd frontend/packages/schema-visualizer
git add -A
git commit -m "refactor: adopt @infrahub/ui Toolbar/IconButton/FloatingPanel/useDismiss"
```
Open a PR in `opsmill/infrahub-schema-visualizer`.

---

# UNIT D — main repo: submodule pointer bump

## Task 13: Bump the submodule pointer (after the submodule PR merges)

**Files:**
- Modify: submodule pointer at `frontend/packages/schema-visualizer`

- [ ] **Step 1: Update the submodule to the merged commit**

```bash
cd frontend/packages/schema-visualizer && git fetch origin && git checkout <merged-commit-or-tag>
cd /Users/paul/Projects/infrahub
git add frontend/packages/schema-visualizer
```

- [ ] **Step 2: Reinstall + verify the app still builds against the new submodule**

Run: `cd frontend/app && pnpm install && pnpm build`
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: bump schema-visualizer to floating-primitives adoption"
```

---

## Self-review notes

- **Spec coverage:** IconButton ✅ (T3), Toolbar+Divider ✅ (T4), FloatingPanel built on Card ✅ (T5), useDismiss shared ✅ (T2), path-traversal adoption ✅ (T7–T9), submodule adoption with `@infrahub/ui` dep ✅ (T11–T12), cross-repo 2-PR + pointer bump ✅ (T10/T13). Test harness ✅ (T1).
- **Out of scope (intentional):** SegmentedControl (mode toggle), Menu/Popover (export dropdown), GraphNodeShell/graph items, stats-panel close affordance, backfilling tests for existing Button/Card.
- **Naming consistency:** `useDismiss(ref, onDismiss, active)`, `IconButton` requires `aria-label`, `Toolbar.Divider`, `FloatingPanel` props (`title`/`description`/`onClose`/`isOpen`/`dismissable`/`className`/`headerContent`/`closeLabel`) are used identically across all tasks.
- **Risk watch:** (1) submodule IIFE styling — Task 11 Step 2 `@source` line is the linchpin; Task 12 Step 6 verifies it. (2) path-traversal visual parity — Task 9 Step 4 manual check. (3) `pnpm-lock.yaml` changes in two repos.
