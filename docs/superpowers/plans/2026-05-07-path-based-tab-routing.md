# Path-Based Tab Routing Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate four QSP-based tab pages (User profile, Branch details, Proposed change details, Object details) to path-based child routes, matching the pattern already used by IPAM and role-management. After this work, tab content is lazy-loaded per route, browser back/forward navigates between tabs, and the `tab` / `branch_tab` QSP keys are gone.

**Architecture:** Each former QSP-based page becomes a parent route with nested child routes. The parent renders the tab bar (`LinkTab` from `@/shared/components/ui/link`) plus a React Router `<Outlet />`. Child routes render the actual tab content and are registered with `lazy: () => import(...)` for per-tab code splitting. Active tab state is derived from the URL via `NavLink`'s `isActive` callback (built into `LinkTab`), eliminating `useQueryState(QSP.TAB)` reads inside tab components. URL helpers (`constructPath`, `getObjectDetailsUrl`) lose tab-related QSP wiring; callers append the tab as a path segment instead.

**Tech Stack:** React 19, react-router 7, TypeScript 5.9, Vite 8, Tailwind 4, Vitest 4 (unit), Playwright 1.56 (E2E). Existing path-based references: `entities/role-manager/ui/role-management-tabs.tsx`, `entities/ipam/ipam-details-tabs.tsx`.

**Scope note:** This plan covers five phases (Foundation + four pages + Cleanup). Each page phase is independent and ends with a working app + green tests, so the work can be merged phase-by-phase if desired. Run all `pnpm` commands from `frontend/app/`.

---

## File Structure Overview

### New files

- `frontend/app/src/shared/components/ui/link-tab.test.tsx` — unit tests for the extended `LinkTab` (active state, badge, icon, scroll-into-view).
- `frontend/app/src/entities/user-profile/ui/profile-tabs.tsx` — Profile tab bar (3 tabs).
- `frontend/app/src/pages/profile/layout.tsx` — Profile parent route with tab bar + `<Outlet />`.
- `frontend/app/src/pages/profile/profile-tab.tsx` — index route, wraps `TabProfile`.
- `frontend/app/src/pages/profile/tokens-tab.tsx` — `/profile/tokens` child route.
- `frontend/app/src/pages/profile/password-tab.tsx` — `/profile/password` child route.
- `frontend/app/src/entities/branches/ui/branch-tabs.tsx` — Branch tab bar (5 tabs).
- `frontend/app/src/pages/branches/branch-details/details-tab.tsx` — index route, renders `BranchDetails`.
- `frontend/app/src/pages/branches/branch-details/data-tab.tsx` — `/branches/:branchName/data`.
- `frontend/app/src/pages/branches/branch-details/files-tab.tsx` — `/branches/:branchName/files`.
- `frontend/app/src/pages/branches/branch-details/artifacts-tab.tsx` — `/branches/:branchName/artifacts`.
- `frontend/app/src/pages/branches/branch-details/schema-tab.tsx` — `/branches/:branchName/schema`.
- `frontend/app/src/pages/proposed-changes/proposed-change-details/overview.tsx` — index route, renders `ProposedChangeDetails`.
- `frontend/app/src/pages/proposed-changes/proposed-change-details/data.tsx` — `data` child route.
- `frontend/app/src/pages/proposed-changes/proposed-change-details/files.tsx` — `files` child route.
- `frontend/app/src/pages/proposed-changes/proposed-change-details/artifacts.tsx` — `artifacts` child route.
- `frontend/app/src/pages/proposed-changes/proposed-change-details/schema.tsx` — `schema` child route.
- `frontend/app/src/pages/proposed-changes/proposed-change-details/checks.tsx` — `checks` child route.
- `frontend/app/src/pages/proposed-changes/proposed-change-details/tasks.tsx` — `tasks` child route (list).
- `frontend/app/src/pages/proposed-changes/proposed-change-details/task-details.tsx` — `tasks/:taskId` child route.
- `frontend/app/src/pages/objects/object-details/details.tsx` — index route, renders the existing details card body.
- `frontend/app/src/pages/objects/object-details/relationship.tsx` — `:relationshipName` child route.
- `frontend/app/src/pages/objects/object-details/tasks.tsx` — `tasks` child route.
- `frontend/app/src/pages/objects/object-details/task-details.tsx` — `tasks/:taskId` child route.
- `frontend/app/src/pages/objects/object-details/repository-objects.tsx` — `repository_objects` child route.

### Modified files

- `frontend/app/src/shared/components/ui/link.tsx` — extend `LinkTab` to accept `isActive` override, scroll-into-view behavior, and content composition (icon/badge slots).
- `frontend/app/src/app/router.tsx` — add nested children for `/profile`, `/branches/:branchName`, `/proposed-changes/:proposedChangeId`, `/objects/:objectKind/:objectId`.
- `frontend/app/src/pages/profile.tsx` — switch to thin auth gate that delegates to nested layout.
- `frontend/app/src/entities/user-profile/ui/user-profile.tsx` — split into header layout (used by parent route) and tab content components.
- `frontend/app/src/pages/branches/details.tsx` — convert to layout component rendering header + tab bar + `<Outlet />`.
- `frontend/app/src/pages/proposed-changes/details.tsx` — drop content switch, render `<Outlet />` after `ProposedChangeTabs`.
- `frontend/app/src/entities/proposed-changes/ui/tabs/proposed-change-tab.tsx` — replace `useQueryState` + `constructPath` QSP composition with `to={path}` + `LinkTab` active.
- `frontend/app/src/entities/proposed-changes/ui/tabs/{overview,data,files,artifacts,schema,checks,tasks}-tab.tsx` — pass child route paths instead of `tabId` strings.
- `frontend/app/src/entities/proposed-changes/ui/diff-summary/proposed-change-diff-summary.tsx` — append `/data` segment instead of `tab=data`.
- `frontend/app/src/entities/diff/ui/diff-utils.tsx` — same.
- `frontend/app/src/entities/diff/ui/checks/data-conflict.tsx` — same.
- `frontend/app/src/pages/objects/object-details-page.tsx` — wrap content in nested route layout.
- `frontend/app/src/entities/nodes/object/ui/object-details/object-details-body.tsx` — render `<Outlet />` instead of `ObjectDetails`.
- `frontend/app/src/entities/nodes/object/ui/object-details/object-details.tsx` — drop QSP read; component becomes pure detail card.
- `frontend/app/src/entities/nodes/object/ui/object-details/object-details-tabs.tsx` — derive active state from URL, not QSP.
- `frontend/app/src/entities/nodes/object/ui/object-tabs.tsx` — `RelationshipTab` builds path-based URL.
- `frontend/app/src/entities/tasks/ui/task-tab.tsx` — `ObjectTaskTab` builds path-based URL.
- `frontend/app/src/entities/repository/ui/repository-objects-tab.tsx` — same.
- `frontend/app/src/entities/nodes/relationships/ui/object-details-tab-content.tsx` — **delete after migration** (replaced by route components).
- `frontend/app/src/entities/nodes/object-item-details/action-buttons/relationships-buttons.tsx` — read relationship name from `useParams()` instead of `useQueryState(QSP.TAB)`.
- `frontend/app/src/entities/nodes/utils.ts` — `getObjectDetailsUrl` gains optional `tabSegment` parameter that appends `/segment` to the path.
- `frontend/app/src/entities/groups/ui/object-groups-list.tsx` — pass tab segment instead of `QSP.TAB` override.
- `frontend/app/src/entities/generators/ui/generator-run-button.tsx` and `generator-definition-run-button.tsx` — build `/tasks?task_id=...` style path-based URL.
- `frontend/app/src/entities/tasks/ui/task-items.tsx` — same when `relatedNodeId` is set.
- `frontend/app/src/shared/config/qsp.ts` — remove `BRANCH_TAB`, `PROPOSED_CHANGES_TAB`, `TAB`.
- `frontend/app/src/shared/components/tabs.tsx` — **delete** after both consumers migrate.
- `frontend/app/tests/e2e/branches/branch-details.spec.ts` — assert path-based URLs.
- `frontend/app/tests/e2e/proposed-changes/proposed-changes_checks.spec.ts` — assert path-based URLs.
- `frontend/app/tests/e2e/profile/account-tokens.spec.ts` — visit `/profile/tokens` instead of `/profile?tab=tokens`.
- `dev/guidelines/frontend/url-construction.md` — note that tab navigation uses path segments.

---

## Phase 0 — Foundation

### Task 0.1: Verify route assumptions

**Files:** none — research only.

- [ ] **Step 1: Confirm legacy `Tabs` consumers are limited to two files**

Run from repo root:

```bash
grep -rn "from \"@/shared/components/tabs\"" frontend/app/src
```

Expected output (exactly):

```
frontend/app/src/pages/branches/details.tsx:9:import { Tabs } from "@/shared/components/tabs";
frontend/app/src/entities/user-profile/ui/user-profile.tsx:7:import { Tabs } from "@/shared/components/tabs";
```

If anything else appears, add it to the migration list before proceeding.

- [ ] **Step 2: Confirm no schema relationship is named `tasks` or `repository_objects`**

These names will become reserved static path segments under `/objects/:objectKind/:objectId/`. Static route matches win over dynamic ones, so a relationship named `tasks` would become inaccessible.

```bash
grep -rn '"name": *"tasks"\|name: *"tasks"\|"tasks"' backend/infrahub/core/schema_models.py 2>/dev/null | grep -i relation || true
grep -rn '"repository_objects"' backend/infrahub 2>/dev/null || true
```

The names already exist as constants (`TASK_TAB = "tasks"`, `REPOSITORY_OBJECTS_TAB = "repository_objects"`) and the QSP flow already collides with them, so this is a verification step — no code change. If a real-world schema relationship collides, file a follow-up; do not block this migration.

- [ ] **Step 3: Confirm branch names don't contain `/`**

The current `/branches/*` wildcard route would mask the issue. The new `/branches/:branchName/<tab>` requires `:branchName` to be a single segment.

```bash
grep -rn "name.*regex\|valid_branch_name\|VALID_BRANCH_NAME" backend/infrahub/core 2>/dev/null
```

Document the finding in the commit message of Task 2.1. Default assumption: branch names are single-segment slugs. If the regex permits slashes, use `encodeURIComponent` in `branch-tabs.tsx` link construction (Task 2.3) — leave a comment on that line.

No commit for Task 0.1.

---

### Task 0.2: Extend `LinkTab` to compose icon + badge + scroll-into-view

**Files:**

- Modify: `frontend/app/src/shared/components/ui/link.tsx`
- Test: `frontend/app/src/shared/components/ui/link-tab.test.tsx`

The current `LinkTab` only renders a styled `NavLink`. Today, three patterns coexist:

- IPAM `LinkTab href={...}>{icon}{label}{badge}</LinkTab>` — composition via children.
- Object/role `ObjectDetailsTab isActive={...} to={...}` — manual active prop, smooth scroll.
- Proposed-change `ProposedChangeTab` — `isActive` derived from QSP.

After the migration, all tab consumers can use one component: `LinkTab` driven by `NavLink` `end` matching, with optional scroll-into-view when active. Icon and badge are passed as children (already the IPAM pattern).

- [ ] **Step 1: Write the failing test**

Create `frontend/app/src/shared/components/ui/link-tab.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router";

import { LinkTab } from "@/shared/components/ui/link";

function renderAt(path: string, ui: React.ReactElement) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/parent/*" element={ui} />
      </Routes>
    </MemoryRouter>
  );
}

describe("LinkTab", () => {
  test("renders children and href", () => {
    renderAt("/parent", <LinkTab href="/parent/data">Data</LinkTab>);
    const link = screen.getByRole("link", { name: "Data" });
    expect(link).toHaveAttribute("href", "/parent/data");
  });

  test("applies active border when URL matches", () => {
    renderAt("/parent/data", <LinkTab href="/parent/data">Data</LinkTab>);
    expect(screen.getByRole("link", { name: "Data" }).className).toMatch(
      /border-custom-blue-600/
    );
  });

  test("does not apply active border when URL does not match", () => {
    renderAt("/parent/files", <LinkTab href="/parent/data">Data</LinkTab>);
    expect(screen.getByRole("link", { name: "Data" }).className).not.toMatch(
      /border-custom-blue-600/
    );
  });

  test("end matching is exact — child paths do not activate the parent tab", () => {
    renderAt("/parent/data/123", <LinkTab href="/parent/data">Data</LinkTab>);
    expect(screen.getByRole("link", { name: "Data" }).className).not.toMatch(
      /border-custom-blue-600/
    );
  });
});
```

- [ ] **Step 2: Run the test to confirm it passes against the existing implementation**

```bash
cd frontend/app && pnpm test src/shared/components/ui/link-tab.test.tsx --run
```

Expected: 4/4 passing. The existing `LinkTab` already supports these cases. If any test fails, fix the test, not the component.

- [ ] **Step 3: Add `scrollIntoViewOnActive` prop**

`ObjectDetailsTab` (the wrapper used by object-details/role-management) currently wraps a plain `Link` and triggers `node?.scrollIntoView({ behavior: "smooth" })` when active. After the migration, all tab consumers use `LinkTab` directly, so the smooth-scroll-on-mount behavior moves into `LinkTab` itself — gated behind a prop so it stays opt-in.

Edit `frontend/app/src/shared/components/ui/link.tsx`. Replace the existing `LinkTab` export with:

```tsx
import { useEffect, useRef } from "react";
import { type LinkProps, NavLink, type NavLinkProps, Link as RouterLink } from "react-router";

import { classNames } from "@/shared/utils/common";

export const Link = (props: LinkProps) => {
  const { children, className, ...propsToPass } = props;

  return (
    <RouterLink
      {...propsToPass}
      className={classNames(
        "cursor-pointer rounded-md underline decoration-dotted hover:decoration-solid",
        className
      )}
    >
      {children}
    </RouterLink>
  );
};

interface LinkTabProps extends Omit<NavLinkProps, "to"> {
  href: string;
  scrollIntoViewOnActive?: boolean;
}

export function LinkTab({ href, className, scrollIntoViewOnActive, ...props }: LinkTabProps) {
  const ref = useRef<HTMLAnchorElement>(null);

  return (
    <NavLink
      ref={ref}
      to={href}
      end
      className={({ isActive }) => {
        if (isActive && scrollIntoViewOnActive) {
          ref.current?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
        }
        return classNames(
          "transition-all focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-custom-blue-600/25",
          "inline-flex h-11 scroll-m-10 items-center gap-2 truncate border-transparent border-b-2 px-3 py-2 text-sm font-medium",
          isActive
            ? "border-custom-blue-600 text-custom-blue-600"
            : "text-gray-500 hover:border-gray-300 hover:text-gray-700",
          typeof className === "function" ? undefined : className
        );
      }}
      {...props}
    />
  );
}
```

Notes on the diff:
- Adds `scrollIntoViewOnActive` opt-in.
- Brings forward color styling (`text-custom-blue-600`, hover gray) that lived in the deprecated `ObjectDetailsTab` wrapper.
- Keeps `end` matching for exact-path active state.

- [ ] **Step 4: Add a test for scroll-into-view behavior**

Append to `link-tab.test.tsx`:

```tsx
test("scrolls into view when active and scrollIntoViewOnActive is true", () => {
  const scrollIntoView = vi.fn();
  Element.prototype.scrollIntoView = scrollIntoView;
  renderAt(
    "/parent/data",
    <LinkTab href="/parent/data" scrollIntoViewOnActive>
      Data
    </LinkTab>
  );
  expect(scrollIntoView).toHaveBeenCalledWith(
    expect.objectContaining({ behavior: "smooth" })
  );
});

test("does not scroll when inactive", () => {
  const scrollIntoView = vi.fn();
  Element.prototype.scrollIntoView = scrollIntoView;
  renderAt(
    "/parent/files",
    <LinkTab href="/parent/data" scrollIntoViewOnActive>
      Data
    </LinkTab>
  );
  expect(scrollIntoView).not.toHaveBeenCalled();
});
```

Add `import { vi } from "vitest"` at the top alongside the existing imports.

- [ ] **Step 5: Run all `LinkTab` tests**

```bash
cd frontend/app && pnpm test src/shared/components/ui/link-tab.test.tsx --run
```

Expected: 6/6 passing.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/src/shared/components/ui/link.tsx frontend/app/src/shared/components/ui/link-tab.test.tsx
git commit -m "feat(frontend): extend LinkTab with scroll-into-view + composable styling"
```

---

## Phase 1 — User Profile (3 static tabs)

This is the simplest migration: 3 static tabs, no badges, no external link consumers (no other code links into `/profile?tab=...`).

### Task 1.1: Add `/profile` child routes

**Files:** Modify `frontend/app/src/app/router.tsx`.

- [ ] **Step 1: Replace the `/profile` route block**

In `frontend/app/src/app/router.tsx`, locate (line ~115):

```tsx
{
  path: "/profile",
  lazy: () => import("@/pages/profile"),
},
```

Replace with:

```tsx
{
  path: "/profile",
  lazy: () => import("@/pages/profile"),
  children: [
    {
      index: true,
      lazy: () => import("@/pages/profile/profile-tab"),
    },
    {
      path: "tokens",
      lazy: () => import("@/pages/profile/tokens-tab"),
    },
    {
      path: "password",
      lazy: () => import("@/pages/profile/password-tab"),
    },
  ],
},
```

- [ ] **Step 2: Commit (after Task 1.4)**

(no commit yet — wait until parent + children + tab bar exist together)

---

### Task 1.2: Create the profile parent layout

**Files:**

- Modify: `frontend/app/src/pages/profile.tsx`
- Modify: `frontend/app/src/entities/user-profile/ui/user-profile.tsx`
- Create: `frontend/app/src/entities/user-profile/ui/profile-tabs.tsx`

The current `pages/profile.tsx` is a thin auth gate that returns `<UserProfilePage />`. Currently `UserProfilePage` (in `entities/user-profile/ui/user-profile.tsx`) renders the header, tab bar, and tab content via a switch. After this task: `pages/profile.tsx` still gates auth; `UserProfilePage` renders header + tab bar + `<Outlet />`; tab content moves to dedicated child route files (Task 1.3).

- [ ] **Step 1: Create `profile-tabs.tsx`**

Create `frontend/app/src/entities/user-profile/ui/profile-tabs.tsx`:

```tsx
import { Row } from "@/shared/components/container";
import { LinkTab } from "@/shared/components/ui/link";

export function ProfileTabs() {
  return (
    <Row className="border-gray-200 border-b">
      <LinkTab href="/profile">Profile</LinkTab>
      <LinkTab href="/profile/tokens">Tokens</LinkTab>
      <LinkTab href="/profile/password">Password</LinkTab>
    </Row>
  );
}
```

- [ ] **Step 2: Rewrite `user-profile.tsx`**

Replace the entire contents of `frontend/app/src/entities/user-profile/ui/user-profile.tsx` with:

```tsx
import { Outlet } from "react-router";

import { Avatar } from "@/shared/components/display/avatar";
import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { useTitle } from "@/shared/hooks/useTitle";

import { useGetAccountProfile } from "@/entities/user-profile/ui/queries/get-account-profile.query";
import { ProfileTabs } from "@/entities/user-profile/ui/profile-tabs";

export function UserProfilePage() {
  const { data: account, isPending, error } = useGetAccountProfile();
  useTitle(account?.display_label ?? "Profile");

  if (error) {
    return <ErrorScreen />;
  }

  if (isPending) {
    return <LoadingIndicator className="h-full" />;
  }

  return (
    <Content.Card>
      <Content.CardTitle
        title={
          <div className="flex items-center gap-2">
            <Avatar name={account.name?.value} />

            <div className="ml-2">
              <h3>{account.display_label}</h3>

              <p className="text-gray-500 text-sm">{account.description?.value ?? "-"}</p>
            </div>
          </div>
        }
      />

      <ProfileTabs />

      <Outlet />
    </Content.Card>
  );
}
```

(Removes: `useQueryState`, `Tabs`, `QSP`, `PROFILE_TABS` constant, `renderContent` switch, `TabProfile`/`TabTokens`/`TabUpdatePassword` imports.)

- [ ] **Step 3: Verify no other file imports the removed exports**

```bash
grep -rn "PROFILE_TABS\|renderContent" frontend/app/src
```

Expected: no output. (`PROFILE_TABS` was local to the file; `renderContent` was a local arrow function.)

`pages/profile.tsx` doesn't change — it still calls `<UserProfilePage />`, which now renders `<Outlet />`.

---

### Task 1.3: Create child route components

**Files:**

- Create: `frontend/app/src/pages/profile/profile-tab.tsx`
- Create: `frontend/app/src/pages/profile/tokens-tab.tsx`
- Create: `frontend/app/src/pages/profile/password-tab.tsx`

Each is a thin route shim that re-exports the existing tab content under the conventional `Component` named export expected by react-router lazy routes.

- [ ] **Step 1: Create `profile-tab.tsx`**

```tsx
import TabProfile from "@/entities/user-profile/ui/tab-profile";

export function Component() {
  return <TabProfile />;
}
```

- [ ] **Step 2: Create `tokens-tab.tsx`**

```tsx
import TabTokens from "@/entities/user-profile/ui/tab-tokens";

export function Component() {
  return <TabTokens />;
}
```

- [ ] **Step 3: Create `password-tab.tsx`**

```tsx
import TabUpdatePassword from "@/entities/user-profile/ui/tab-update-password";

export function Component() {
  return <TabUpdatePassword />;
}
```

---

### Task 1.4: Update profile E2E test and verify

**Files:** Modify `frontend/app/tests/e2e/profile/account-tokens.spec.ts`.

- [ ] **Step 1: Replace the QSP-based goto with the path-based URL**

In `frontend/app/tests/e2e/profile/account-tokens.spec.ts`:

Change the describe block name and goto on lines 6 and 9:

```ts
test.describe("/profile/tokens", () => {
  test.describe("when not logged in as admin account", () => {
    test("should not access profile tokens", async ({ page }) => {
      await page.goto("/profile/tokens");
      await expect(page.getByText("Open Proposed changes", { exact: true })).toBeVisible();
    });
  });
```

- [ ] **Step 2: Run the profile E2E test**

```bash
cd frontend/app && pnpm test:e2e tests/e2e/profile/account-tokens.spec.ts
```

Expected: passing. If the unauthenticated path redirects, verify it redirects from `/profile/tokens` to login.

- [ ] **Step 3: Manual smoke test**

```bash
cd frontend/app && pnpm dev
```

Open `http://localhost:8080/profile`, click each tab. Verify URL becomes `/profile`, `/profile/tokens`, `/profile/password` and the content updates. Use browser back/forward to confirm history navigation.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/src/app/router.tsx \
        frontend/app/src/entities/user-profile/ui/user-profile.tsx \
        frontend/app/src/entities/user-profile/ui/profile-tabs.tsx \
        frontend/app/src/pages/profile/profile-tab.tsx \
        frontend/app/src/pages/profile/tokens-tab.tsx \
        frontend/app/src/pages/profile/password-tab.tsx \
        frontend/app/tests/e2e/profile/account-tokens.spec.ts
git commit -m "feat(frontend): migrate /profile tabs to path-based routes"
```

---

## Phase 2 — Branch Details (5 static tabs)

### Task 2.1: Add `/branches/:branchName` child routes

**Files:** Modify `frontend/app/src/app/router.tsx`.

The current branch route uses a wildcard (`path: "*"`) inside the `/branches` parent. Verification in Phase 0 confirmed branch names are slug-like (no `/`), so we can switch to `:branchName` and add child segments.

- [ ] **Step 1: Replace the `/branches` block**

Locate (line ~52):

```tsx
{
  path: "/branches",
  children: [
    {
      index: true,
      lazy: () => import("@/pages/branches"),
    },
    {
      path: "*",
      lazy: () => import("@/pages/branches/details"),
    },
  ],
},
```

Replace with:

```tsx
{
  path: "/branches",
  children: [
    {
      index: true,
      lazy: () => import("@/pages/branches"),
    },
    {
      path: ":branchName",
      lazy: () => import("@/pages/branches/details"),
      children: [
        {
          index: true,
          lazy: () => import("@/pages/branches/branch-details/details-tab"),
        },
        {
          path: "data",
          lazy: () => import("@/pages/branches/branch-details/data-tab"),
        },
        {
          path: "files",
          lazy: () => import("@/pages/branches/branch-details/files-tab"),
        },
        {
          path: "artifacts",
          lazy: () => import("@/pages/branches/branch-details/artifacts-tab"),
        },
        {
          path: "schema",
          lazy: () => import("@/pages/branches/branch-details/schema-tab"),
        },
      ],
    },
  ],
},
```

---

### Task 2.2: Create branch tab bar

**Files:** Create `frontend/app/src/entities/branches/ui/branch-tabs.tsx`.

- [ ] **Step 1: Create the file**

```tsx
import { useParams } from "react-router";

import { Row } from "@/shared/components/container";
import { LinkTab } from "@/shared/components/ui/link";

export function BranchTabs() {
  const { branchName } = useParams() as { branchName: string };
  const base = `/branches/${branchName}`;

  return (
    <Row className="border-gray-200 border-b" aria-label="Tabs">
      <LinkTab href={base}>Details</LinkTab>
      <LinkTab href={`${base}/data`}>Data</LinkTab>
      <LinkTab href={`${base}/files`}>Files</LinkTab>
      <LinkTab href={`${base}/artifacts`}>Artifacts</LinkTab>
      <LinkTab href={`${base}/schema`}>Schema</LinkTab>
    </Row>
  );
}
```

If Phase 0 found that branch names can contain `/`, wrap `branchName` in `encodeURIComponent` here and decode at consumption with `decodeURIComponent` if you build paths from it elsewhere.

---

### Task 2.3: Convert `pages/branches/details.tsx` to a layout

**Files:** Modify `frontend/app/src/pages/branches/details.tsx`.

- [ ] **Step 1: Replace the file contents**

```tsx
import { Spinner } from "@infrahub/ui";
import { useAtomValue } from "jotai";
import { Navigate, Outlet, useParams } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { Row } from "@/shared/components/container";
import Content from "@/shared/components/layout/content";
import { useTitle } from "@/shared/hooks/useTitle";

import { branchesState } from "@/entities/branches/stores";
import { BranchTabs } from "@/entities/branches/ui/branch-tabs";
import { BranchDefaultBadge } from "@/entities/branches/ui/branch-list-item/branch-default-badge";
import { BranchStatusBadge } from "@/entities/branches/ui/branch-list-item/branch-status-badge";
import { NodeMetadataPopover } from "@/entities/nodes/object/ui/object-details/node-metadata-popover";

function BranchDetailsLayout() {
  const { branchName } = useParams() as { branchName: string };
  const branches = useAtomValue(branchesState);
  useTitle(`${branchName} details`);

  if (!branchName) {
    return <Navigate to={constructPath("/branches")} />;
  }

  if (branches.length === 0) {
    return (
      <Content.Card className="flex min-h-[400px] items-center justify-center p-5">
        <Spinner />
      </Content.Card>
    );
  }

  const branch = branches.find((b) => b.name === branchName);

  if (!branch) {
    return <Navigate to={constructPath("/branches")} />;
  }

  return (
    <Content.Card>
      <header className="p-5 pb-2">
        <Row>
          <h1 className="font-bold text-xl">{branch.name}</h1>
          <NodeMetadataPopover objectKind="InfrahubBranch" objectId={branch.id} />
          {branch.is_default ? (
            <BranchDefaultBadge className="text-sm" />
          ) : (
            <BranchStatusBadge status={branch.status} className="text-sm" />
          )}
        </Row>
        {branch.description && <p className="text-sm">{branch.description}</p>}
      </header>

      {!branch.is_default && <BranchTabs />}

      <div className="p-2">
        <Outlet />
      </div>
    </Content.Card>
  );
}

export const Component = BranchDetailsLayout;
```

(Removes: `BranchTab` local component, `BranchContent` switch, `useQueryState`, `DIFF_TABS`, `QSP`, all diff/file/artifact/node-diff imports — those move to per-tab files.)

---

### Task 2.4: Create branch tab content files

**Files:**

- Create: `frontend/app/src/pages/branches/branch-details/details-tab.tsx`
- Create: `frontend/app/src/pages/branches/branch-details/data-tab.tsx`
- Create: `frontend/app/src/pages/branches/branch-details/files-tab.tsx`
- Create: `frontend/app/src/pages/branches/branch-details/artifacts-tab.tsx`
- Create: `frontend/app/src/pages/branches/branch-details/schema-tab.tsx`

- [ ] **Step 1: `details-tab.tsx`**

```tsx
import { useParams } from "react-router";

import { BranchDetails } from "@/entities/branches/ui/branch-details";

export function Component() {
  const { branchName } = useParams() as { branchName: string };
  return <BranchDetails branchName={branchName} />;
}
```

- [ ] **Step 2: `data-tab.tsx`**

```tsx
import { useParams } from "react-router";

import { NodeDiff } from "@/entities/diff/ui/node-diff";

export function Component() {
  const { branchName } = useParams() as { branchName: string };
  return (
    <NodeDiff
      branch={branchName}
      filters={{
        namespace: { excludes: ["Schema"] },
        status: { excludes: ["UNCHANGED"] },
      }}
    />
  );
}
```

- [ ] **Step 3: `files-tab.tsx`**

```tsx
import { useParams } from "react-router";

import { FilesDiff } from "@/entities/diff/ui/file-diff/files-diff";

export function Component() {
  const { branchName } = useParams() as { branchName: string };
  return <FilesDiff branchName={branchName} />;
}
```

- [ ] **Step 4: `artifacts-tab.tsx`**

```tsx
import { useParams } from "react-router";

import { ArtifactsDiff } from "@/entities/diff/ui/artifact-diff/artifacts-diff";

export function Component() {
  const { branchName } = useParams() as { branchName: string };
  return <ArtifactsDiff branchName={branchName} />;
}
```

- [ ] **Step 5: `schema-tab.tsx`**

```tsx
import { useParams } from "react-router";

import { NodeDiff } from "@/entities/diff/ui/node-diff";

export function Component() {
  const { branchName } = useParams() as { branchName: string };
  return (
    <NodeDiff
      branch={branchName}
      filters={{
        namespace: { includes: ["Schema"], excludes: ["Profile"] },
        status: { excludes: ["UNCHANGED"] },
      }}
    />
  );
}
```

---

### Task 2.5: Update branch E2E test and verify

**Files:** Modify `frontend/app/tests/e2e/branches/branch-details.spec.ts`.

- [ ] **Step 1: Replace the tab navigation assertions**

In the `should navigate between tabs` test (lines ~76–100), replace the body with:

```ts
test("should navigate between tabs", async ({ page }) => {
  await page.goto(`/branches/${BRANCH_NAME}`);

  const tabsNav = page.getByRole("navigation", { name: "Tabs" });

  await tabsNav.getByText("Data").click();
  await expect(page).toHaveURL(new RegExp(`/branches/${BRANCH_NAME}/data`));

  await tabsNav.getByText("Files").click();
  await expect(page).toHaveURL(new RegExp(`/branches/${BRANCH_NAME}/files`));

  await tabsNav.getByText("Artifacts").click();
  await expect(page).toHaveURL(new RegExp(`/branches/${BRANCH_NAME}/artifacts`));

  await tabsNav.getByText("Schema").click();
  await expect(page).toHaveURL(new RegExp(`/branches/${BRANCH_NAME}/schema`));

  await tabsNav.getByText("Details").click();
  await expect(page).toHaveURL(new RegExp(`/branches/${BRANCH_NAME}$`));
});
```

- [ ] **Step 2: Run the branch E2E test**

```bash
cd frontend/app && pnpm test:e2e tests/e2e/branches/branch-details.spec.ts
```

Expected: passing.

- [ ] **Step 3: Manual smoke test**

```bash
cd frontend/app && pnpm dev
```

Open `http://localhost:8080/branches/atl1-delete-upstream`, click each tab, confirm URLs and content. Use back/forward to verify history.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/src/app/router.tsx \
        frontend/app/src/pages/branches/details.tsx \
        frontend/app/src/pages/branches/branch-details \
        frontend/app/src/entities/branches/ui/branch-tabs.tsx \
        frontend/app/tests/e2e/branches/branch-details.spec.ts
git commit -m "feat(frontend): migrate /branches/:branchName tabs to path-based routes"
```

---

## Phase 3 — Proposed Change Details (7 tabs with counts)

### Task 3.1: Add nested children for `/proposed-changes/:proposedChangeId`

**Files:** Modify `frontend/app/src/app/router.tsx`.

- [ ] **Step 1: Replace the `:proposedChangeId` route block**

Locate (line ~129):

```tsx
{
  path: ":proposedChangeId",
  lazy: () => import("@/pages/proposed-changes/details"),
},
```

Replace with:

```tsx
{
  path: ":proposedChangeId",
  lazy: () => import("@/pages/proposed-changes/details"),
  children: [
    {
      index: true,
      lazy: () => import("@/pages/proposed-changes/proposed-change-details/overview"),
    },
    {
      path: "data",
      lazy: () => import("@/pages/proposed-changes/proposed-change-details/data"),
    },
    {
      path: "files",
      lazy: () => import("@/pages/proposed-changes/proposed-change-details/files"),
    },
    {
      path: "artifacts",
      lazy: () => import("@/pages/proposed-changes/proposed-change-details/artifacts"),
    },
    {
      path: "schema",
      lazy: () => import("@/pages/proposed-changes/proposed-change-details/schema"),
    },
    {
      path: "checks",
      lazy: () => import("@/pages/proposed-changes/proposed-change-details/checks"),
    },
    {
      path: "tasks",
      children: [
        {
          index: true,
          lazy: () => import("@/pages/proposed-changes/proposed-change-details/tasks"),
        },
        {
          path: ":taskId",
          lazy: () => import("@/pages/proposed-changes/proposed-change-details/task-details"),
        },
      ],
    },
  ],
},
```

---

### Task 3.2: Update `pages/proposed-changes/details.tsx` to render `<Outlet />`

**Files:** Modify `frontend/app/src/pages/proposed-changes/details.tsx`.

- [ ] **Step 1: Replace the file contents**

```tsx
import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import { Link, Outlet, useParams } from "react-router";

import { queryClient } from "@/shared/api/rest/client";
import { constructPath } from "@/shared/api/rest/fetch";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Badge } from "@/shared/components/ui/badge";
import { PROPOSED_CHANGES_OBJECT } from "@/shared/config/constants";
import { useTitle } from "@/shared/hooks/useTitle";

import { ObjectHelpButton } from "@/entities/nodes/object/ui/object-help-button";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import type { ProposedChangeDetail } from "@/entities/proposed-changes/domain/proposed-change.types";
import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";
import { useGetProposedChangeDetails } from "@/entities/proposed-changes/ui/queries/get-proposed-change-details.query";
import { ProposedChangeTabs } from "@/entities/proposed-changes/ui/tabs/proposed-change-tabs";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export function Component() {
  const { proposedChangeId } = useParams() as { proposedChangeId: string };
  const { schema } = useSchema(PROPOSED_CHANGES_OBJECT, { throwIfNotFound: true });
  const [, setProposedChange] = useAtom(proposedChangedState);

  const { isPending, error, data } = useGetProposedChangeDetails({ proposedChangeId });
  useTitle(
    `${data?.proposedChangeData ? `${getNodeLabel(data.proposedChangeData)} - ` : ""}Proposed change - Infrahub`
  );

  if (isPending) {
    return <LoadingIndicator className="h-full" />;
  }

  const { proposedChangeData, metadata } = data ?? {};

  if (error || !proposedChangeData) {
    return (
      <Content.Card>
        <Content.CardTitle
          title="Proposed changes"
          reload={() => {
            queryClient.invalidateQueries({
              predicate: (query) => query.queryKey.includes(proposedChangeId),
            });
          }}
          isReloadLoading={isPending}
          end={
            <ObjectHelpButton
              documentationUrl={schema.documentation}
              kind={PROPOSED_CHANGES_OBJECT}
              className="ml-auto"
            />
          }
        />

        {error ? (
          <ErrorScreen message={error.message} />
        ) : (
          <NoDataFound message="No proposed changes found." />
        )}
      </Content.Card>
    );
  }

  setProposedChange(proposedChangeData as ProposedChangeDetail);

  return (
    <Content.Card>
      <Content.CardTitle
        title={getNodeLabel(proposedChangeData)}
        description={
          <div className="inline-flex items-center gap-1 text-xs">
            <Link
              to={getObjectDetailsUrl(metadata?.created_by?.__typename!, metadata?.created_by?.id)}
              className="font-semibold text-custom-blue-green"
            >
              {metadata?.created_by ? getNodeLabel(metadata.created_by) : ""}
            </Link>
            wants to merge
            <Link to={constructPath(`/branches/${proposedChangeData.source_branch?.value}`)}>
              <Badge variant="blue">
                <Icon icon="mdi:layers-triple" className="mr-1" />
                {proposedChangeData.source_branch?.value}
              </Badge>
            </Link>
            into
            <Link to={constructPath(`/branches/${proposedChangeData.destination_branch?.value}`)}>
              <Badge variant="green" className="items-center">
                <Icon icon="mdi:layers-triple" className="mr-1" />
                {proposedChangeData.destination_branch?.value}
              </Badge>
            </Link>
          </div>
        }
        reload={() => {
          queryClient.invalidateQueries({
            predicate: (query) => query.queryKey.includes(proposedChangeId),
          });
        }}
        isReloadLoading={isPending}
        end={
          <ObjectHelpButton
            documentationUrl={schema?.documentation}
            kind={PROPOSED_CHANGES_OBJECT}
            className="ml-auto"
          />
        }
      />

      <ProposedChangeTabs
        sourceBranch={proposedChangeData.source_branch?.value!}
        proposedChangeId={proposedChangeId}
      />

      <Outlet />
    </Content.Card>
  );
}
```

(Removes: `ProposedChangeDetailsContent` function + its `switch (qspTab)`, `useQueryState`, `DIFF_TABS`/`TASK_TAB` imports, `QSP` import, `Checks/FilesDiff/ArtifactsDiff/NodeDiff/TaskItems/TaskItemDetails/ProposedChangeDetails` imports — those move to per-tab files.)

---

### Task 3.3: Convert `ProposedChangeTab` to path-based

**Files:** Modify `frontend/app/src/entities/proposed-changes/ui/tabs/proposed-change-tab.tsx`.

The current `ProposedChangeTab` accepts a `tabId` (QSP value) and uses `useQueryState(QSP.PROPOSED_CHANGES_TAB)` to determine active state. The replacement accepts a `to` path and uses `LinkTab`.

- [ ] **Step 1: Replace the file contents**

```tsx
import { Spinner } from "@infrahub/ui";

import { LinkTab } from "@/shared/components/ui/link";

export interface ProposedChangeTabProps {
  to: string;
  label: string;
  count?: number;
  isCountLoading?: boolean;
}

export function ProposedChangeTab({ to, label, count, isCountLoading }: ProposedChangeTabProps) {
  return (
    <LinkTab href={to}>
      {label}
      {isCountLoading && <Spinner className="mx-1" />}
      {!isCountLoading && count !== undefined && (
        <div className="rounded-md bg-gray-100 px-2 py-0.5 text-xs">{count}</div>
      )}
    </LinkTab>
  );
}
```

(Removes: `useQueryState`, `useLocation`, `constructPath`, `QSP`, `ObjectDetailsTab` imports, `tabId`/`isActive` logic.)

---

### Task 3.4: Update each tab component

**Files:**

- Modify: `frontend/app/src/entities/proposed-changes/ui/tabs/{overview,data,files,artifacts,schema,checks,tasks}-tab.tsx`

Each tab needs the parent `proposedChangeId` to construct its `to` URL, since the path-based child routes live under `/proposed-changes/:proposedChangeId/`. The parent `ProposedChangeTabs` already passes `proposedChangeId` to those that need it; pass it to the rest as well.

- [ ] **Step 1: Update `overview-tab.tsx`**

```tsx
import { ProposedChangeTab } from "@/entities/proposed-changes/ui/tabs/proposed-change-tab";

export interface OverviewTabProps {
  proposedChangeId: string;
}

export function OverviewTab({ proposedChangeId }: OverviewTabProps) {
  return <ProposedChangeTab to={`/proposed-changes/${proposedChangeId}`} label="Overview" />;
}
```

- [ ] **Step 2: Update `data-tab.tsx`**

```tsx
import { useGetDiffSummary } from "@/entities/diff/ui/queries/get-diff-summary.query";
import { ProposedChangeTab } from "@/entities/proposed-changes/ui/tabs/proposed-change-tab";

export interface DataTabProps {
  sourceBranch: string;
  proposedChangeId: string;
}

export function DataTab({ sourceBranch, proposedChangeId }: DataTabProps) {
  const { isPending, data, error } = useGetDiffSummary({
    branch: sourceBranch,
    proposedChangeId,
    filters: {
      namespace: { excludes: ["Schema"] },
      status: { excludes: ["UNCHANGED"] },
    },
  });

  const count = !error && data ? data.num_added + data.num_updated + data.num_removed : undefined;

  return (
    <ProposedChangeTab
      to={`/proposed-changes/${proposedChangeId}/data`}
      label="Data"
      count={count}
      isCountLoading={isPending}
    />
  );
}
```

- [ ] **Step 3: Update `files-tab.tsx`**

```tsx
import { useGetFilesDiff } from "@/entities/diff/ui/queries/get-files-diff.query";
import { ProposedChangeTab } from "@/entities/proposed-changes/ui/tabs/proposed-change-tab";

export interface FilesTabProps {
  sourceBranch: string;
  proposedChangeId: string;
}

export function FilesTab({ sourceBranch, proposedChangeId }: FilesTabProps) {
  const { isPending, data, error } = useGetFilesDiff({ branchName: sourceBranch });

  const count =
    !error && data ? data.reduce((acc, repo) => acc + (repo.files?.length ?? 0), 0) : undefined;

  return (
    <ProposedChangeTab
      to={`/proposed-changes/${proposedChangeId}/files`}
      label="Files"
      count={count}
      isCountLoading={isPending}
    />
  );
}
```

- [ ] **Step 4: Update `artifacts-tab.tsx`**

```tsx
import { useGetArtifactsDiff } from "@/entities/diff/ui/queries/get-artifacts-diff.query";
import { ProposedChangeTab } from "@/entities/proposed-changes/ui/tabs/proposed-change-tab";

export interface ArtifactsTabProps {
  sourceBranch: string;
  proposedChangeId: string;
}

export function ArtifactsTab({ sourceBranch, proposedChangeId }: ArtifactsTabProps) {
  const { isPending, data, error } = useGetArtifactsDiff({ branch: sourceBranch });

  const count =
    !error && data ? data.filter((artifact) => artifact.action !== "unchanged").length : undefined;

  return (
    <ProposedChangeTab
      to={`/proposed-changes/${proposedChangeId}/artifacts`}
      label="Artifacts"
      count={count}
      isCountLoading={isPending}
    />
  );
}
```

- [ ] **Step 5: Update `schema-tab.tsx`**

```tsx
import { useGetDiffSummary } from "@/entities/diff/ui/queries/get-diff-summary.query";
import { ProposedChangeTab } from "@/entities/proposed-changes/ui/tabs/proposed-change-tab";

export interface SchemaTabProps {
  sourceBranch: string;
  proposedChangeId: string;
}

export function SchemaTab({ sourceBranch, proposedChangeId }: SchemaTabProps) {
  const { isPending, data, error } = useGetDiffSummary({
    branch: sourceBranch,
    proposedChangeId,
    filters: {
      namespace: { includes: ["Schema"], excludes: ["Profile"] },
      status: { excludes: ["UNCHANGED"] },
    },
  });

  const count = !error && data ? data.num_added + data.num_updated + data.num_removed : undefined;

  return (
    <ProposedChangeTab
      to={`/proposed-changes/${proposedChangeId}/schema`}
      label="Schema"
      count={count}
      isCountLoading={isPending}
    />
  );
}
```

- [ ] **Step 6: Update `checks-tab.tsx`**

```tsx
import { useGetValidatorsQuery } from "@/entities/diff/ui/queries/get-validators.query";
import { ProposedChangeTab } from "@/entities/proposed-changes/ui/tabs/proposed-change-tab";

export interface ChecksTabProps {
  proposedChangeId: string;
}

export function ChecksTab({ proposedChangeId }: ChecksTabProps) {
  const { isPending, data: validators, error } = useGetValidatorsQuery({ proposedChangeId });

  const count = !error && validators ? validators.length : undefined;

  return (
    <ProposedChangeTab
      to={`/proposed-changes/${proposedChangeId}/checks`}
      label="Checks"
      count={count}
      isCountLoading={isPending}
    />
  );
}
```

- [ ] **Step 7: Update `tasks-tab.tsx`**

```tsx
import { ProposedChangeTab } from "@/entities/proposed-changes/ui/tabs/proposed-change-tab";
import { useGetTaskCount } from "@/entities/tasks/ui/queries/get-task-count.query";

export interface TasksTabProps {
  proposedChangeId: string;
}

export function TasksTab({ proposedChangeId }: TasksTabProps) {
  const { isPending, data: count } = useGetTaskCount({ relatedNodeIds: [proposedChangeId] });

  return (
    <ProposedChangeTab
      to={`/proposed-changes/${proposedChangeId}/tasks`}
      label="Tasks"
      count={count}
      isCountLoading={isPending}
    />
  );
}
```

- [ ] **Step 8: Update `proposed-change-tabs.tsx` to pass `proposedChangeId` to all children**

In `frontend/app/src/entities/proposed-changes/ui/tabs/proposed-change-tabs.tsx`, change the children rendering:

```tsx
<OverviewTab proposedChangeId={proposedChangeId} />
<DataTab sourceBranch={sourceBranch} proposedChangeId={proposedChangeId} />
<FilesTab sourceBranch={sourceBranch} proposedChangeId={proposedChangeId} />
<ArtifactsTab sourceBranch={sourceBranch} proposedChangeId={proposedChangeId} />
<SchemaTab sourceBranch={sourceBranch} proposedChangeId={proposedChangeId} />
<ChecksTab proposedChangeId={proposedChangeId} />
<TasksTab proposedChangeId={proposedChangeId} />
```

---

### Task 3.5: Create proposed change tab content files

**Files:**

- Create: `frontend/app/src/pages/proposed-changes/proposed-change-details/overview.tsx`
- Create: `.../data.tsx`, `.../files.tsx`, `.../artifacts.tsx`, `.../schema.tsx`, `.../checks.tsx`, `.../tasks.tsx`, `.../task-details.tsx`

Each pulls `proposedChangeData` from the parent route's loader. Since the existing app uses react-query (not loaders), each child component re-uses the existing `useGetProposedChangeDetails` hook (cached, so it won't refetch) to access `source_branch`.

- [ ] **Step 1: `overview.tsx`**

```tsx
import { useParams } from "react-router";

import { useGetProposedChangeDetails } from "@/entities/proposed-changes/ui/queries/get-proposed-change-details.query";
import { ProposedChangeDetails } from "@/entities/proposed-changes/ui/proposed-change-details";

export function Component() {
  const { proposedChangeId } = useParams() as { proposedChangeId: string };
  const { data } = useGetProposedChangeDetails({ proposedChangeId });
  if (!data) return null;
  return <ProposedChangeDetails {...data} />;
}
```

- [ ] **Step 2: `data.tsx`**

```tsx
import { NodeDiff } from "@/entities/diff/ui/node-diff";

export function Component() {
  return (
    <NodeDiff
      filters={{
        namespace: { excludes: ["Schema"] },
        status: { excludes: ["UNCHANGED"] },
      }}
    />
  );
}
```

- [ ] **Step 3: `files.tsx`**

```tsx
import { useParams } from "react-router";

import { FilesDiff } from "@/entities/diff/ui/file-diff/files-diff";
import { useGetProposedChangeDetails } from "@/entities/proposed-changes/ui/queries/get-proposed-change-details.query";

export function Component() {
  const { proposedChangeId } = useParams() as { proposedChangeId: string };
  const { data } = useGetProposedChangeDetails({ proposedChangeId });
  const branchName = data?.proposedChangeData.source_branch?.value;
  if (!branchName) return null;
  return <FilesDiff branchName={branchName} />;
}
```

- [ ] **Step 4: `artifacts.tsx`**

```tsx
import { useParams } from "react-router";

import { ArtifactsDiff } from "@/entities/diff/ui/artifact-diff/artifacts-diff";
import { useGetProposedChangeDetails } from "@/entities/proposed-changes/ui/queries/get-proposed-change-details.query";

export function Component() {
  const { proposedChangeId } = useParams() as { proposedChangeId: string };
  const { data } = useGetProposedChangeDetails({ proposedChangeId });
  const branchName = data?.proposedChangeData.source_branch?.value;
  if (!branchName) return null;
  return <ArtifactsDiff branchName={branchName} />;
}
```

- [ ] **Step 5: `schema.tsx`**

```tsx
import { NodeDiff } from "@/entities/diff/ui/node-diff";

export function Component() {
  return (
    <NodeDiff
      filters={{
        namespace: { includes: ["Schema"], excludes: ["Profile"] },
        status: { excludes: ["UNCHANGED"] },
      }}
    />
  );
}
```

- [ ] **Step 6: `checks.tsx`**

```tsx
import { Checks } from "@/entities/diff/ui/checks/checks";

export function Component() {
  return <Checks />;
}
```

- [ ] **Step 7: `tasks.tsx`**

```tsx
import { useParams } from "react-router";

import { TaskItems } from "@/entities/tasks/ui/task-items";

export function Component() {
  const { proposedChangeId } = useParams() as { proposedChangeId: string };
  return <TaskItems relatedNodeId={proposedChangeId} />;
}
```

- [ ] **Step 8: `task-details.tsx`**

```tsx
import { Icon } from "@iconify-icon/react";
import { Link, useParams } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { TaskItemDetails } from "@/entities/tasks/ui/task-item-details";

export function Component() {
  const { proposedChangeId } = useParams() as { proposedChangeId: string };

  return (
    <div>
      <div className="flex bg-white text-sm">
        <Link
          to={constructPath(`/proposed-changes/${proposedChangeId}/tasks`)}
          className="flex items-center p-2"
        >
          <Icon icon="mdi:chevron-left" />
          All tasks
        </Link>
      </div>

      <TaskItemDetails />
    </div>
  );
}
```

---

### Task 3.6: Update consumers that link into `?tab=data`

**Files:**

- Modify: `frontend/app/src/entities/proposed-changes/ui/diff-summary/proposed-change-diff-summary.tsx`
- Modify: `frontend/app/src/entities/diff/ui/diff-utils.tsx`
- Modify: `frontend/app/src/entities/diff/ui/checks/data-conflict.tsx`

- [ ] **Step 1: `proposed-change-diff-summary.tsx`**

Replace lines 44–80 with:

```tsx
const proposedChangeDetailsPath = `/proposed-changes/${proposedChangeId}/data`;

return (
  <DiffSummaryTagGroup className={className}>
    <DiffSummaryTag
      variant="added"
      count={data.num_added}
      href={constructPath(proposedChangeDetailsPath, [
        { name: QSP.STATUS, value: DIFF_STATUS.ADDED },
      ])}
    />
    <DiffSummaryTag
      variant="removed"
      count={data.num_removed}
      href={constructPath(proposedChangeDetailsPath, [
        { name: QSP.STATUS, value: DIFF_STATUS.REMOVED },
      ])}
    />
    <DiffSummaryTag
      variant="updated"
      count={data.num_updated}
      href={constructPath(proposedChangeDetailsPath, [
        { name: QSP.STATUS, value: DIFF_STATUS.UPDATED },
      ])}
    />
    <DiffSummaryTag
      variant="conflicts"
      count={data.num_conflicts}
      href={constructPath(proposedChangeDetailsPath, [
        { name: QSP.STATUS, value: DIFF_STATUS.CONFLICT },
      ])}
    />
  </DiffSummaryTagGroup>
);
```

(Drops the `{ name: QSP.PROPOSED_CHANGES_TAB, value: "data" }` entries; the `/data` segment is in the path now.)

- [ ] **Step 2: `diff-utils.tsx`**

Locate line 59. Change from:

```tsx
href={`${pathname}?${QSP.PROPOSED_CHANGES_TAB}=data#${nodeId}`}
```

To:

```tsx
href={`${pathname.replace(/\/data$/, "")}/data#${nodeId}`}
```

Wait — this depends on `pathname`. The `getThreadTitle` is called from a comments view inside the proposed-change page. It uses `window.location.pathname` (line 43: `typeof window !== "undefined" ? window.location.pathname : ""`). Replace lines 43–60 with:

```tsx
const pathname = typeof window !== "undefined" ? window.location.pathname : "";
const proposedChangePath = pathname.match(/^(\/proposed-changes\/[^/]+)/)?.[1] ?? pathname;

if (thread?.object_path?.value) {
  const nodeId = extractNodeId(thread.object_path.value);
  const nodeProperty = extractNodeProperty(thread.object_path.value);

  if (!nodeId) {
    return null;
  }

  return (
    <div className="flex items-center gap-2 text-sm">
      <Badge variant={"gray-outline"}>Object</Badge>

      <LinkButton
        href={`${proposedChangePath}/data#${nodeId}`}
        className="flex items-center gap-2 px-1"
        variant={"ghost"}
      >
```

Remove the unused `QSP` import if it becomes unused after the edit.

- [ ] **Step 3: `data-conflict.tsx`**

Replace line 36:

```tsx
const url = `/proposed-changes/${proposedChangesDetails.id}/data#${id}`;
```

Remove the now-unused `QSP` import.

---

### Task 3.7: Update proposed-change E2E test and verify

**Files:** Modify `frontend/app/tests/e2e/proposed-changes/proposed-changes_checks.spec.ts`.

- [ ] **Step 1: Update the URL assertion**

Line 44 — replace:

```ts
await expect(page.url()).toContain("tab=checks");
```

with:

```ts
await expect(page.url()).toContain("/checks");
```

- [ ] **Step 2: Run the proposed-change E2E test**

```bash
cd frontend/app && pnpm test:e2e tests/e2e/proposed-changes/proposed-changes_checks.spec.ts
```

Expected: passing.

- [ ] **Step 3: Manual smoke test**

```bash
cd frontend/app && pnpm dev
```

Open a proposed change. Click each tab — Overview, Data, Files, Artifacts, Schema, Checks, Tasks. Click into a task to confirm `/tasks/:taskId` route. Use the "All tasks" back button. Use browser back/forward.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/src/app/router.tsx \
        frontend/app/src/pages/proposed-changes \
        frontend/app/src/entities/proposed-changes/ui/tabs \
        frontend/app/src/entities/proposed-changes/ui/diff-summary/proposed-change-diff-summary.tsx \
        frontend/app/src/entities/diff/ui/diff-utils.tsx \
        frontend/app/src/entities/diff/ui/checks/data-conflict.tsx \
        frontend/app/tests/e2e/proposed-changes/proposed-changes_checks.spec.ts
git commit -m "feat(frontend): migrate /proposed-changes/:id tabs to path-based routes"
```

---

## Phase 4 — Object Details (dynamic tabs)

This phase migrates `/objects/:objectKind/:objectId` and the IPAM details that share the same body component. Object details are the most complex case because the tab list is derived from the schema (relationship tabs are dynamic).

### Task 4.1: Add nested children for object details

**Files:** Modify `frontend/app/src/app/router.tsx`.

Routes are duplicated between `/objects/:objectKind/:objectId` (lines 98–110) and `/ipam/namespaces/:objectKind/:objectId` (lines 207–211). Both currently route to the same `object-details-page` lazily. Both get the same nested children.

- [ ] **Step 1: Replace the `:objectId` block under `/objects`**

Change lines ~98–109:

```tsx
{
  path: ":objectId",
  children: [
    {
      index: true,
      lazy: () => import("@/pages/objects/object-details-page"),
    },
    {
      path: "convert",
      lazy: () => import("@/pages/objects/object-convert"),
    },
  ],
},
```

To:

```tsx
{
  path: ":objectId",
  lazy: () => import("@/pages/objects/object-details-page"),
  children: [
    {
      index: true,
      lazy: () => import("@/pages/objects/object-details/details"),
    },
    {
      path: "tasks",
      children: [
        {
          index: true,
          lazy: () => import("@/pages/objects/object-details/tasks"),
        },
        {
          path: ":taskId",
          lazy: () => import("@/pages/objects/object-details/task-details"),
        },
      ],
    },
    {
      path: "repository_objects",
      lazy: () => import("@/pages/objects/object-details/repository-objects"),
    },
    {
      path: ":relationshipName",
      lazy: () => import("@/pages/objects/object-details/relationship"),
    },
  ],
},
{
  path: ":objectId/convert",
  lazy: () => import("@/pages/objects/object-convert"),
},
```

(`/objects/:objectKind/:objectId/convert` is hoisted to a sibling so it isn't shadowed by the new `:relationshipName` catch-all.)

- [ ] **Step 2: Mirror the change for `/ipam/namespaces/:objectKind/:objectId`**

Locate (line ~209):

```tsx
{
  path: ":objectId",
  lazy: () => import("@/pages/objects/object-details-page"),
},
```

Replace with the full `:objectId` block from Step 1 (without the `convert` sibling — IPAM namespaces have no convert page).

---

### Task 4.2: Add optional tab segment to `getObjectDetailsUrl`

**Files:** Modify `frontend/app/src/entities/nodes/utils.ts`.

The proposal calls for `getObjectDetailsUrl` to gain an optional tab parameter that appends a path segment. This keeps callers (`object-groups-list.tsx`, etc.) working with one helper.

- [ ] **Step 1: Update the signature**

Replace the file with:

```tsx
import { constructPath, type overrideQueryParams } from "@/shared/api/rest/fetch";

import {
  IP_ADDRESS_GENERIC,
  IP_NAMESPACE_GENERIC,
  IP_PREFIX_GENERIC,
} from "@/entities/ipam/constants";
import { constructPathForIpam } from "@/entities/ipam/utils";
import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/constants";
import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/constants";
import { getSchema } from "@/entities/schema/domain/get-schema";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

export const getObjectDetailsUrl = (
  objectKind: string,
  objectId?: string,
  overrideParams?: overrideQueryParams[],
  tabSegment?: string
) => {
  const tab = tabSegment ? `/${tabSegment}` : "";
  const { schema } = getSchema(objectKind);
  if (!schema) {
    const path = objectId ? `/objects/${objectKind}/${objectId}${tab}` : `/objects/${objectKind}`;
    return constructPath(path, overrideParams);
  }

  if (isOfKind(IP_PREFIX_GENERIC, schema)) {
    const path = objectId ? `/ipam/${objectKind}/${objectId}${tab}` : "/ipam";
    return constructPathForIpam(path, overrideParams);
  }

  if (isOfKind(IP_ADDRESS_GENERIC, schema)) {
    const path = objectId ? `/ipam/${objectKind}/${objectId}${tab}` : "/ipam/ip_addresses";
    return constructPathForIpam(path, overrideParams);
  }

  if (isOfKind(IP_NAMESPACE_GENERIC, schema)) {
    const path = objectId
      ? `/ipam/namespaces/${objectKind}/${objectId}${tab}`
      : "/ipam/namespaces";
    return constructPathForIpam(path, overrideParams);
  }

  if (isOfKind(RESOURCE_GENERIC_KIND, schema)) {
    return constructPathForIpam(`/resource-manager/${objectId ?? ""}`, overrideParams);
  }

  if (isOfKind(PROPOSED_CHANGE_OBJECT, schema)) {
    const path = objectId ? `/proposed-changes/${objectId}${tab}` : "/proposed-changes";
    return constructPathForIpam(path, overrideParams);
  }

  const path = objectId ? `/objects/${objectKind}/${objectId}${tab}` : `/objects/${objectKind}`;
  return constructPath(path, overrideParams);
};
```

(Tab segment is only applied for the object-detail-style branches, not for list pages or resource manager.)

---

### Task 4.3: Convert `ObjectDetailsTabs` to path-based active state

**Files:** Modify `frontend/app/src/entities/nodes/object/ui/object-details/object-details-tabs.tsx`.

- [ ] **Step 1: Replace the file contents**

```tsx
import { ScrollArea } from "@infrahub/ui";

import { Row } from "@/shared/components/container";
import { LinkTab } from "@/shared/components/ui/link";
import { GENERIC_REPOSITORY_KIND, TASK_TARGET } from "@/shared/config/constants";

import { ObjectTaskTab, RelationshipTab } from "@/entities/nodes/object/ui/object-tabs";
import { getRelationshipsVisibleInTab } from "@/entities/nodes/object/utils/get-relationships-visible-in-tab";
import type { NodeObject } from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { RepositoryObjectsTab } from "@/entities/repository/ui/repository-objects-tab";
import type { ModelSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

interface ObjectDetailsTabsProps {
  objectSchema: ModelSchema;
  objectData: NodeObject;
}

export function ObjectDetailsTabs({ objectSchema, objectData }: ObjectDetailsTabsProps) {
  const objectId = objectData.id;
  const objectKind = objectData.__typename;
  const relationshipsTabs = getRelationshipsVisibleInTab(objectSchema.relationships ?? []);
  const isTaskTarget = isOfKind(TASK_TARGET, objectSchema);
  const isRepository = isOfKind(GENERIC_REPOSITORY_KIND, objectSchema);

  return (
    <ScrollArea scrollX scrollY={false} scrollBarClassName="hidden" className="shrink-0">
      <Row className="items-end gap-4 px-4" data-testid="object-details-tabs">
        <LinkTab href={getObjectDetailsUrl(objectKind, objectId)} scrollIntoViewOnActive>
          Details
        </LinkTab>
        {relationshipsTabs.map((tab) => (
          <RelationshipTab
            key={tab.name}
            objectKind={objectKind}
            objectId={objectId}
            relationshipSchema={tab}
          />
        ))}
        {isTaskTarget && <ObjectTaskTab objectKind={objectKind} objectId={objectId} />}
        {isRepository && <RepositoryObjectsTab objectKind={objectKind} objectId={objectId} />}
      </Row>
    </ScrollArea>
  );
}
```

(Drops `useQueryState`, `qspTab`, `QSP`, `ObjectDetailsTab`. Adds `objectKind` to `ObjectTaskTab` and `RepositoryObjectsTab` so they can build URLs.)

---

### Task 4.4: Convert `RelationshipTab`, `ObjectTaskTab`, `RepositoryObjectsTab`

**Files:**

- Modify: `frontend/app/src/entities/nodes/object/ui/object-tabs.tsx`
- Modify: `frontend/app/src/entities/tasks/ui/task-tab.tsx`
- Modify: `frontend/app/src/entities/repository/ui/repository-objects-tab.tsx`

- [ ] **Step 1: `object-tabs.tsx`**

Replace the entire file with:

```tsx
import { Spinner } from "@infrahub/ui";

import { Badge } from "@/shared/components/ui/badge";
import { LinkTab } from "@/shared/components/ui/link";

import { useGetRelationshipCount } from "@/entities/nodes/relationships/ui/queries/get-relationship-count.query";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { useGetTaskCount } from "@/entities/tasks/ui/queries/get-task-count.query";
import type { RelationshipSchema } from "@/entities/schema/types";

export interface RelationshipTabProps {
  objectKind: string;
  objectId: string;
  relationshipSchema: RelationshipSchema;
}

export function RelationshipTab({ objectKind, objectId, relationshipSchema }: RelationshipTabProps) {
  const { isPending, data: relationshipCount } = useGetRelationshipCount({
    objectKind,
    objectId,
    relationshipName: relationshipSchema.name,
  });

  return (
    <LinkTab
      href={getObjectDetailsUrl(objectKind, objectId, undefined, relationshipSchema.name)}
      scrollIntoViewOnActive
    >
      {relationshipSchema.label}
      {isPending && <Spinner />}
      {!isPending && (
        <Badge className="rounded-full font-medium text-gray-80">{relationshipCount}</Badge>
      )}
    </LinkTab>
  );
}

export interface TabWithCountProps {
  objectKind: string;
  objectId: string;
}

export function ObjectTaskTab({ objectKind, objectId }: TabWithCountProps) {
  const { isPending, data: taskCount } = useGetTaskCount({ relatedNodeIds: [objectId] });

  return (
    <LinkTab
      href={getObjectDetailsUrl(objectKind, objectId, undefined, "tasks")}
      scrollIntoViewOnActive
    >
      Tasks
      {isPending ? (
        <Spinner />
      ) : (
        <Badge className="rounded-full font-medium text-gray-80">{taskCount}</Badge>
      )}
    </LinkTab>
  );
}
```

Notes:
- `ObjectDetailsTab` is gone — its only callers were `object-details-tabs.tsx` (Task 4.3), the IPAM `object-details-tab.tsx` (uses LinkTab directly), `role-management-tabs.tsx` (Task 4.7), and `task-tab.tsx`/`repository-objects-tab.tsx` (this task).
- `ObjectTaskTab` now lives in `object-tabs.tsx` rather than `entities/tasks/ui/task-tab.tsx`. Move it deliberately: the old file becomes empty, delete it.

- [ ] **Step 2: Delete `task-tab.tsx`**

```bash
rm frontend/app/src/entities/tasks/ui/task-tab.tsx
```

Update the import in `object-details-tabs.tsx` (Task 4.3 already imports `ObjectTaskTab` from `@/entities/nodes/object/ui/object-tabs`).

- [ ] **Step 3: Update `repository-objects-tab.tsx`**

```tsx
import { Spinner } from "@infrahub/ui";

import { Badge } from "@/shared/components/ui/badge";
import { LinkTab } from "@/shared/components/ui/link";

import { useGetRelationshipCount } from "@/entities/nodes/relationships/ui/queries/get-relationship-count.query";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { REPOSITORY_GROUP, REPOSITORY_OBJECTS_TAB } from "@/entities/repository/constants";

export interface RepositoryObjectsTabProps {
  objectKind: string;
  objectId: string;
}

export function RepositoryObjectsTab({ objectKind, objectId }: RepositoryObjectsTabProps) {
  const { isPending, data: objectsCount } = useGetRelationshipCount({
    objectId,
    objectKind: REPOSITORY_GROUP,
    relationshipName: "members",
    queryFilter: "repository__ids",
  });

  return (
    <LinkTab
      href={getObjectDetailsUrl(objectKind, objectId, undefined, REPOSITORY_OBJECTS_TAB)}
      scrollIntoViewOnActive
    >
      Objects
      {isPending && <Spinner />}
      {!isPending && (
        <Badge className="rounded-full font-medium text-gray-80">{objectsCount ?? 0}</Badge>
      )}
    </LinkTab>
  );
}
```

(Drops `useQueryState`, `useLocation`, `constructPath`, `QSP`, `ObjectDetailsTab`, `TaskTabProps`.)

---

### Task 4.5: Convert `ObjectDetails` to render via `<Outlet />`

**Files:**

- Modify: `frontend/app/src/entities/nodes/object/ui/object-details/object-details-body.tsx`
- Modify: `frontend/app/src/entities/nodes/object/ui/object-details/object-details.tsx`
- Delete: `frontend/app/src/entities/nodes/relationships/ui/object-details-tab-content.tsx`

The current flow: `ObjectDetailsBody` → renders `ObjectDetailsTabs` + `ObjectDetails` (inside a `Card`). `ObjectDetails` reads `qspTab`; if set, it renders `ObjectDetailsTabContent` (which switches on QSP value); if not, it renders the details card. After this task, the `<Card>` wrapper plus `<Outlet />` lives in the body, and `ObjectDetails` becomes the index-route content (just the cards).

- [ ] **Step 1: Rewrite `object-details-body.tsx`**

```tsx
import { Card } from "@infrahub/ui";
import { Outlet } from "react-router";

import { Col } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { ObjectDetailsTabs } from "@/entities/nodes/object/ui/object-details/object-details-tabs";
import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";

interface ObjectDetailsBodyProps {
  objectId: string;
  objectSchema: ModelSchema;
  permission: Permission;
}

export function ObjectDetailsBody({ objectSchema, objectId, permission }: ObjectDetailsBodyProps) {
  const { data: objectData, isPending, error } = useGetObject({ objectSchema, objectId });

  if (isPending) {
    return <LoadingIndicator className="h-full" />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  return (
    <Col className="gap-0 overflow-auto p-1">
      <ObjectDetailsTabs objectSchema={objectSchema} objectData={objectData} />
      <Card className="overflow-auto to-neutral-50">
        <Outlet context={{ objectSchema, objectData, permission }} />
      </Card>
    </Col>
  );
}
```

The `<Outlet context>` allows child routes to consume the loaded data without re-fetching.

- [ ] **Step 2: Rewrite `object-details.tsx`**

```tsx
import { Col } from "@/shared/components/container";
import { FILE_OBJECT_KIND } from "@/shared/config/constants";
import { useTitle } from "@/shared/hooks/useTitle";

import { FilePreviewCard } from "@/entities/nodes/object/ui/object-details/file-preview-card";
import { ObjectActivitiesCard } from "@/entities/nodes/object/ui/object-details/object-activities-card";
import { ObjectDetailsCard } from "@/entities/nodes/object/ui/object-details/object-details-card";
import { ObjectProfilesGroupsCard } from "@/entities/nodes/object/ui/object-details/object-profiles-groups-card";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { NodeFileObject, NodeObjectWithMetadata } from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

interface ObjectDetailsProps {
  objectSchema: ModelSchema;
  objectData: NodeObjectWithMetadata;
  permission: Permission;
}

export function ObjectDetails({ objectSchema, objectData, permission }: ObjectDetailsProps) {
  useTitle(`${getNodeLabel(objectData)} details`);

  return (
    <div className="flex flex-col gap-2 overflow-auto p-2 xl:grid xl:grid-cols-3 xl:items-start">
      <Col className="shrink-0 grow md:col-span-2">
        <ObjectDetailsCard
          objectSchema={objectSchema}
          objectData={objectData}
          permission={permission}
        />

        {isOfKind(FILE_OBJECT_KIND, objectSchema) && (
          <FilePreviewCard objectData={objectData as unknown as NodeFileObject} />
        )}
      </Col>

      <Col>
        <ObjectProfilesGroupsCard
          objectSchema={objectSchema}
          objectData={objectData}
          permission={permission}
        />
        <ObjectActivitiesCard objectKind={objectData.__typename} objectId={objectData.id} />
      </Col>
    </div>
  );
}
```

(Drops `useQueryState`, `QSP`, `ObjectDetailsTabContent`, conditional QSP-based rendering.)

- [ ] **Step 3: Delete `object-details-tab-content.tsx`**

```bash
rm frontend/app/src/entities/nodes/relationships/ui/object-details-tab-content.tsx
```

Verify nothing else imports it:

```bash
grep -rn "object-details-tab-content\|ObjectDetailsTabContent" frontend/app/src
```

Expected: no output.

---

### Task 4.6: Create object detail child route components

**Files:**

- Create: `frontend/app/src/pages/objects/object-details/details.tsx`
- Create: `frontend/app/src/pages/objects/object-details/relationship.tsx`
- Create: `frontend/app/src/pages/objects/object-details/tasks.tsx`
- Create: `frontend/app/src/pages/objects/object-details/task-details.tsx`
- Create: `frontend/app/src/pages/objects/object-details/repository-objects.tsx`

Each child route reads parent context via `useOutletContext()`.

- [ ] **Step 1: Define a typed outlet context hook**

Add a small typed accessor in `frontend/app/src/entities/nodes/object/ui/object-details/use-object-details-outlet.ts`:

```tsx
import { useOutletContext } from "react-router";

import type { NodeObjectWithMetadata } from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";

export interface ObjectDetailsOutletContext {
  objectSchema: ModelSchema;
  objectData: NodeObjectWithMetadata;
  permission: Permission;
}

export const useObjectDetailsOutlet = () => useOutletContext<ObjectDetailsOutletContext>();
```

- [ ] **Step 2: `details.tsx`**

```tsx
import { ObjectDetails } from "@/entities/nodes/object/ui/object-details/object-details";
import { useObjectDetailsOutlet } from "@/entities/nodes/object/ui/object-details/use-object-details-outlet";

export function Component() {
  const { objectSchema, objectData, permission } = useObjectDetailsOutlet();
  return (
    <ObjectDetails
      objectSchema={objectSchema}
      objectData={objectData}
      permission={permission}
    />
  );
}
```

- [ ] **Step 3: `relationship.tsx`**

```tsx
import { useParams } from "react-router";

import { useObjectDetailsOutlet } from "@/entities/nodes/object/ui/object-details/use-object-details-outlet";
import { ObjectRelationshipsManager } from "@/entities/nodes/relationships/ui/object-relationships-manager";

export function Component() {
  const { objectSchema, objectData, permission } = useObjectDetailsOutlet();
  const { relationshipName } = useParams() as { relationshipName: string };

  return (
    <ObjectRelationshipsManager
      parentNodeSchema={objectSchema}
      parentNodeData={objectData}
      relationshipName={relationshipName}
      permission={permission}
    />
  );
}
```

- [ ] **Step 4: `tasks.tsx`**

```tsx
import { useObjectDetailsOutlet } from "@/entities/nodes/object/ui/object-details/use-object-details-outlet";
import { TaskItems } from "@/entities/tasks/ui/task-items";

export function Component() {
  const { objectData } = useObjectDetailsOutlet();
  return <TaskItems relatedNodeId={objectData.id} />;
}
```

- [ ] **Step 5: `task-details.tsx`**

```tsx
import { Icon } from "@iconify-icon/react";
import { Link } from "react-router";

import { useObjectDetailsOutlet } from "@/entities/nodes/object/ui/object-details/use-object-details-outlet";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { TaskItemDetails } from "@/entities/tasks/ui/task-item-details";

export function Component() {
  const { objectData } = useObjectDetailsOutlet();

  return (
    <>
      <div className="flex bg-white text-sm">
        <Link
          to={getObjectDetailsUrl(objectData.__typename, objectData.id, undefined, "tasks")}
          className="flex items-center p-2"
        >
          <Icon icon="mdi:chevron-left" />
          All tasks
        </Link>
      </div>

      <TaskItemDetails />
    </>
  );
}
```

- [ ] **Step 6: `repository-objects.tsx`**

```tsx
import { useObjectDetailsOutlet } from "@/entities/nodes/object/ui/object-details/use-object-details-outlet";
import { RepositoryObjectsManager } from "@/entities/repository/ui/repository-objects-manager";

export function Component() {
  const { objectData } = useObjectDetailsOutlet();
  return <RepositoryObjectsManager parentNodeId={objectData.id} />;
}
```

---

### Task 4.7: Update `RelationshipsButtons` to read relationship from path

**Files:** Modify `frontend/app/src/entities/nodes/object-item-details/action-buttons/relationships-buttons.tsx`.

- [ ] **Step 1: Replace `useQueryState(QSP.TAB)` with `useParams()`**

In `relationships-buttons.tsx`, change line 4 imports:

```tsx
import { useState } from "react";
import { useParams } from "react-router";
```

Remove `import { useQueryState } from "nuqs";` and `import { QSP } from "@/shared/config/qsp";`.

Change line 43:

```tsx
const { relationshipName } = useParams() as { relationshipName?: string };
```

(Replace all uses of `relationshipTab` in the file with `relationshipName`.)

The rest of the file is unchanged because the variable name was the only QSP-touching call.

---

### Task 4.8: Update consumers that link to `?tab=members`, `?tab=tasks`, etc.

**Files:**

- Modify: `frontend/app/src/entities/groups/ui/object-groups-list.tsx`
- Modify: `frontend/app/src/entities/generators/ui/generator-run-button.tsx`
- Modify: `frontend/app/src/entities/generators/ui/generator-definition-run-button.tsx`
- Modify: `frontend/app/src/entities/tasks/ui/task-items.tsx`

- [ ] **Step 1: `object-groups-list.tsx`**

Replace lines 61–65:

```tsx
<Link
  to={getObjectDetailsUrl(group.__typename, group.id, undefined, "members")}
  className="font-light text-sm hover:underline"
>
```

Drop the `import { QSP } from "@/shared/config/qsp"` line if no other reference remains.

- [ ] **Step 2: `generator-run-button.tsx`**

Replace lines 33–36:

```tsx
const url = constructPath(`${window.location.pathname.replace(/\/tasks.*$/, "")}/tasks`, [
  { name: QSP.TASK_ID, value: taskId },
]);
```

Wait — that depends on the current path. The button is rendered on object detail pages. After the migration, the user could already be on `/objects/.../tasks`; we want to navigate to `/objects/.../tasks?task_id=...`. Refactor to read `useParams` for `objectKind` + `objectId` and use `getObjectDetailsUrl`:

```tsx
import { Button, type ButtonProps } from "@infrahub/ui";
import { PlayIcon } from "lucide-react";
import type React from "react";
import { Link, useParams } from "react-router";
import { toast } from "react-toastify";

import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { QSP } from "@/shared/config/qsp";

import { useRunGeneratorMutation } from "@/entities/generators/ui/queries/run-generator.mutation";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { constructPath } from "@/shared/api/rest/fetch";

export interface GeneratorRunButtonProps extends ButtonProps {
  generatorId: string;
  targetNodeIds?: string[];
  children?: React.ReactNode;
}

export function GeneratorRunButton({
  generatorId,
  targetNodeIds,
  children,
  variant = "active",
  ...props
}: GeneratorRunButtonProps) {
  const { isPending, mutate } = useRunGeneratorMutation();
  const { objectKind, objectId } = useParams() as { objectKind?: string; objectId?: string };

  const handleRunGenerator = () => {
    mutate(
      { generatorId, targetNodeIds },
      {
        onSuccess: ({ taskId }) => {
          const baseUrl = objectKind && objectId
            ? getObjectDetailsUrl(objectKind, objectId, undefined, "tasks")
            : constructPath("/tasks");
          const url = constructPath(baseUrl, [{ name: QSP.TASK_ID, value: taskId }]);

          toast(
            <Alert
              type={ALERT_TYPES.SUCCESS}
              message={
                <>
                  Generator started successfully.
                  <br />
                  <Link to={url} className="flex items-center gap-1 underline">
                    View task details
                  </Link>
                </>
              }
            />
          );
        },
      }
    );
  };

  return (
    <Button
      isPending={isPending}
      isDisabled={isPending}
      variant={variant}
      onPress={handleRunGenerator}
      {...props}
    >
      {!isPending && <PlayIcon className="size-4" />}
      {children ?? "Run"}
    </Button>
  );
}
```

Wait — the button might also be rendered outside the object details page. Look up where `GeneratorRunButton` is used (`grep -rn "GeneratorRunButton" frontend/app/src`). If both contexts exist, the `useParams()` fallback to `/tasks` covers them.

- [ ] **Step 3: `generator-definition-run-button.tsx`**

Apply the same pattern: read `useParams()` to get `objectKind` + `objectId`, build URL with `getObjectDetailsUrl(..., "tasks")`. Replace lines 51–54:

```tsx
const baseUrl = objectKind && objectId
  ? getObjectDetailsUrl(objectKind, objectId, undefined, "tasks")
  : constructPath("/tasks");
const url = constructPath(baseUrl, [{ name: QSP.TASK_ID, value: taskId }]);
```

Add `import { useParams } from "react-router";` and `import { getObjectDetailsUrl } from "@/entities/nodes/utils";` and read `objectKind`/`objectId` near the top of the component body.

- [ ] **Step 4: `task-items.tsx`**

Replace lines 104–113:

```tsx
const getUrl = (id: string) => {
  if (!relatedNodeId) {
    return constructPath(`/tasks/${id}`);
  }

  // pathname already ends in /tasks (parent route is the tasks tab); append /:taskId
  return constructPath(`${pathname.replace(/\/$/, "")}/${id}`);
};
```

This works for both proposed-change task lists (`/proposed-changes/:id/tasks`) and object task lists (`/objects/.../tasks`) — both append `/:taskId` to reach their respective `task-details` routes.

Drop the `import { TASK_TAB } from "@/shared/config/constants";` line if `TASK_TAB` isn't used elsewhere in the file.

---

### Task 4.9: Manual smoke test + commit

- [ ] **Step 1: Run the dev server**

```bash
cd frontend/app && pnpm dev
```

Manual checks:
1. Open an object detail page like a Tag or Device. Click the Details tab, a relationship tab (e.g. `members`), the Tasks tab if present.
2. URL should change to `/objects/.../<relationshipName>` and similar.
3. Open a repository — verify Repository Objects tab works at `/objects/.../repository_objects`.
4. Open a task from a list to confirm `/.../tasks/:taskId` works and the "All tasks" back button navigates correctly.
5. Open IPAM namespaces detail (`/ipam/namespaces/...`) and verify the same.
6. Click the "Add relationship" button on a relationship tab — confirm `RelationshipsButtons` reads the relationship from the path.

- [ ] **Step 2: Run all unit tests**

```bash
cd frontend/app && pnpm test --run
```

Expected: passing. Fix any test that referenced the deleted `task-tab.tsx`, `object-details-tab-content.tsx`, or QSP.TAB.

- [ ] **Step 3: Run object-related E2E tests**

```bash
cd frontend/app && pnpm test:e2e tests/e2e/objects
```

Expected: passing. If a test asserts on `?tab=...` URLs, update to assert path-based URLs (mirror Phase 2 patterns).

- [ ] **Step 4: Commit**

```bash
git add frontend/app/src/app/router.tsx \
        frontend/app/src/entities/nodes \
        frontend/app/src/entities/tasks/ui/task-items.tsx \
        frontend/app/src/entities/repository/ui/repository-objects-tab.tsx \
        frontend/app/src/entities/groups/ui/object-groups-list.tsx \
        frontend/app/src/entities/generators \
        frontend/app/src/pages/objects/object-details
git rm frontend/app/src/entities/tasks/ui/task-tab.tsx \
       frontend/app/src/entities/nodes/relationships/ui/object-details-tab-content.tsx
git commit -m "feat(frontend): migrate /objects/:kind/:id tabs to path-based routes"
```

---

## Phase 5 — Cleanup

### Task 5.1: Remove unused QSP entries

**Files:** Modify `frontend/app/src/shared/config/qsp.ts`.

- [ ] **Step 1: Verify no remaining references**

```bash
grep -rn "QSP.TAB\b\|QSP.BRANCH_TAB\|QSP.PROPOSED_CHANGES_TAB" frontend/app/src
```

Expected: no output. If any results appear, finish migrating those callers before continuing.

- [ ] **Step 2: Remove the keys from the QSP config**

In `frontend/app/src/shared/config/qsp.ts`, remove the three lines:

```tsx
BRANCH_TAB: "branch_tab",
PROPOSED_CHANGES_TAB: "tab",
TAB: "tab",
```

Final file:

```tsx
export const QSP = {
  BRANCH: "branch",
  SOURCE_BRANCH: "source_branch",
  KIND: "kind",
  DATETIME: "at",
  FILTER: "filters",
  PAGINATION: "pagination",
  PROPOSED_CHANGES_STATE: "pr_state",
  QUERY: "query",
  TASK_ID: "task_id",
  SEARCH: "search",
  STATUS: "status",
  HIGHLIGHT: "highlight",
} as const;
```

---

### Task 5.2: Delete the legacy `Tabs` component

**Files:** Delete `frontend/app/src/shared/components/tabs.tsx`.

- [ ] **Step 1: Verify no remaining imports**

```bash
grep -rn "from \"@/shared/components/tabs\"" frontend/app/src
```

Expected: no output.

- [ ] **Step 2: Delete the file**

```bash
rm frontend/app/src/shared/components/tabs.tsx
```

---

### Task 5.3: Update URL construction guidelines

**Files:** Modify `dev/guidelines/frontend/url-construction.md`.

- [ ] **Step 1: Add a section on tab navigation**

Append after the "When to use `constructPath`" section:

```markdown
## Tab Navigation Uses Path Segments

Tabs on detail pages are nested child routes, not query string parameters. Build tab URLs as path segments:

```typescript
// ✅ Good - path-based tab navigation
const url = getObjectDetailsUrl(objectKind, objectId, undefined, "members");
// → /objects/CoreTag/abc123/members

// ❌ Bad - QSP-based (legacy pattern, no longer supported)
const url = constructPath(`/objects/${kind}/${id}`, [{ name: "tab", value: "members" }]);
```

`getObjectDetailsUrl(kind, id, overrideParams, tabSegment)` accepts an optional fourth argument that appends `/<tabSegment>` to the path.
```

---

### Task 5.4: Run full test suite + format

- [ ] **Step 1: Format frontend**

```bash
cd frontend/app && pnpm biome:fix
```

- [ ] **Step 2: Run full unit suite**

```bash
cd frontend/app && pnpm test --run
```

Expected: passing.

- [ ] **Step 3: Run full E2E suite (or relevant subset)**

```bash
cd frontend/app && pnpm test:e2e tests/e2e/branches tests/e2e/profile tests/e2e/proposed-changes tests/e2e/objects
```

Expected: passing. Triage any failures that mention `?tab=` or `branch_tab=`.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/src/shared/config/qsp.ts \
        dev/guidelines/frontend/url-construction.md
git rm frontend/app/src/shared/components/tabs.tsx
git commit -m "chore(frontend): drop tab-related QSP keys and legacy Tabs component"
```

---

## Self-Review Notes

- **Spec coverage:** All four target pages (Profile, Branch details, Proposed change, Object details) have phase tasks. URL helpers (`constructPath`, `getObjectDetailsUrl`) are addressed in Tasks 4.2 and 5.3. The shared `LinkTab` extension is Task 0.2. The legacy `Tabs` deletion is Task 5.2. QSP cleanup is Task 5.1.
- **Out of scope confirmation:** IPAM list pages (already path-based), role management (already path-based), and other QSPs (`BRANCH`, `DATETIME`, etc.) are untouched.
- **Risk areas:** (1) `RelationshipsButtons` `useParams()` swap depends on the relationship-tab route segment being named `relationshipName`. (2) `task-items.tsx` URL builder uses regex on `pathname` — verified safe for both `/proposed-changes/:id/tasks` and `/objects/.../tasks`. (3) Object detail nested routes register `tasks` and `repository_objects` as static segments before `:relationshipName`, so a schema relationship with those exact names would be unreachable (Phase 0 Step 2 verifies). (4) Branch routes assume `:branchName` is a single URL segment — Phase 0 Step 3 verifies.

---

## Execution Handoff

**Plan saved to `docs/superpowers/plans/2026-05-07-path-based-tab-routing.md`.**

Two execution options:

1. **Subagent-Driven (recommended for this scope)** — Dispatch a fresh subagent per task, review between tasks. Good fit because the plan has 30+ small tasks with clear file boundaries.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch by phase with checkpoints between each phase.

Phase boundaries are natural commit points; you can also stop after any single phase, since each leaves the app in a working state.
