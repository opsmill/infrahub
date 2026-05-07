# URL and Path Construction

> Part of: `dev/guidelines/frontend/`

Guidelines for constructing URLs and paths in the React TypeScript frontend.

## Use `getObjectDetailsUrl` for Object URLs

**Always use `getObjectDetailsUrl` for constructing URLs to object detail pages:**

```typescript
import { getObjectDetailsUrl } from "@/entities/nodes/utils";

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

**Location:** `frontend/app/src/entities/nodes/utils.ts`

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
| Generic objects (incl. IPAM, proposed changes, resource manager) | `getObjectDetailsUrl(kind, id, overrideParams?, tabSegment?)` | `frontend/app/src/entities/nodes/utils.ts` |
| Branches | `getBranchDetailsUrl(branchName, tab?, overrideParams?)` | `frontend/app/src/entities/branches/utils.ts` |

When you add a new detail-page family with tabs:

1. Add `getXxxDetailsUrl(id, tab?, overrideParams?)` in the entity's `utils.ts`.
2. Use it from the tab bar AND from every external callsite (search bars, table cells, summary widgets, redirects).
3. Define a small union type for the tab segment (e.g. `BranchDetailsTab = "data" | "files" | "artifacts" | "schema"`) so callers can't pass an unknown tab.

See [route-architecture.md](route-architecture.md) for the surrounding tab-bar / outlet-context pattern.
