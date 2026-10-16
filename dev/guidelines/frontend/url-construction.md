# URL and Path Construction

> Part of: `dev/guidelines/frontend/`

Guidelines for constructing URLs and paths in the React TypeScript frontend.

## Build paths with `useConstructPath` during render

`constructPath` resolves the active branch and the time-machine date by reading `window.location` at
call time. That is accurate in an event handler and wrong during render: React Compiler caches a
render-time call whose inputs are all non-reactive once per mount, so a link in a component that
outlives a branch switch — the sidebar, the header, breadcrumbs, a tab bar — keeps pointing at the
branch that was active when it first rendered. Clicking it silently returns the user to the default
branch.

Use the hook in render, the plain function in handlers:

```tsx
// ✅ Render: the hook reads the branch from context, so the path recomputes on a branch switch
function AppSidebarHeader() {
  const constructPath = useConstructPath();
  return <Link to={constructPath("/")}>…</Link>;
}

// ✅ Event handler: reading the URL at call time is accurate
const onSuccess = () => navigate(constructPath("/tasks"));

// ❌ Render: frozen at mount, so the link loses the branch
function AppSidebarHeader() {
  return <Link to={constructPath("/")}>…</Link>;
}
```

**Location:** `frontend/app/src/entities/navigation/ui/hooks/use-construct-path.ts`

Caller overrides are applied after the ambient branch and date, so a link that deliberately targets
another branch still wins:

```tsx
constructPath("/tasks", [{ name: QSP.BRANCH, value: task.branch }]);
```

The detail-page helpers below still call `constructPath` directly and carry the same staleness when
called during render.

## Use `getObjectDetailsUrl` for Object URLs

**Always use `getObjectDetailsUrl` for constructing URLs to object detail pages:**

```typescript
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";

// ✅ Good - handles all object types consistently
const url = getObjectDetailsUrl(objectKind, objectId);
const listUrl = getObjectDetailsUrl(objectKind, undefined, queryParams);

// ❌ Bad - hardcoded paths, doesn't handle IPAM/proposed changes/etc
const url = constructPath(`/objects/${kind}/${id}`);
const url = constructPath(`/proposed-changes/${id}`);
```

**Why?** `getObjectDetailsUrl` automatically handles special routing for:
- IPAM objects (IP prefixes, addresses, namespaces) → `/ipam/*`
- Proposed changes → `/proposed-changes/*`
- Resource manager objects → `/resource-manager/*`
- Generic objects → `/objects/*`

**When to use `constructPath`:** Only for non-object URLs that don't represent data objects:
- Settings pages: `/settings`, `/schema`
- Custom application routes: `/dashboard`, `/reports`
- Static pages: `/about`, `/help`

**Location:** `frontend/app/src/entities/nodes/object/ui/routing/object-urls.ts`

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

## One URL helper per detail-page family

Each detail-page family owns a dedicated URL helper. Inline `/feature/${id}/${tab}` templates duplicated across the tab bar, summary widgets, and deep-link callsites are an antipattern — a single rename of the route segment must not require an N-file find-and-replace.

| Family | Helper | Location |
|---|---|---|
| Generic objects (incl. IPAM, resource manager) | `getObjectDetailsUrl(kind, id, overrideParams?, tabSegment?)` | `frontend/app/src/entities/nodes/object/ui/routing/object-urls.ts` |
| Branches | `getBranchDetailsUrl(branchName, tab?, overrideParams?)` | `frontend/app/src/entities/branches/ui/routing/branch-urls.ts` |
| Proposed changes | `getProposedChangeDetailsUrl(id, tab?, overrideParams?)` | `frontend/app/src/entities/proposed-changes/ui/routing/proposed-change-urls.ts` |

When you add a new detail-page family with tabs:

1. Add `getXxxDetailsUrl(id, tab?, overrideParams?)` in the entity's `ui/routing/<noun>-urls.ts`.
2. Use it from the tab bar AND from every external callsite (search bars, table cells, summary widgets, redirects).
3. Define a small string-literal union for the tab argument and require it on the helper signature:

```ts
// ✅ Typed tab union prevents typos and unknown tabs
export type BranchDetailsTab = "data" | "files" | "artifacts" | "schema";
export function getBranchDetailsUrl(branchName: string, tab?: BranchDetailsTab, …): string

// ❌ Plain string accepts anything and collides with dynamic segments like :relationshipName
export function getObjectDetailsUrl(…, tabSegment?: string): string
```

If the underlying helper takes a generic `string` for legacy reasons (e.g. `getObjectDetailsUrl`'s `tabSegment` argument), pass it through a typed wrapper for each detail-page family rather than letting raw strings flow through.

See [route-architecture.md](route-architecture.md) for the surrounding tab-bar / outlet-context pattern.
