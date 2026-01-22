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
