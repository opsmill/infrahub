# Route Architecture

> Part of: `dev/guidelines/frontend/`

Rules for structuring detail pages with nested routes, tab bars, and parent-loaded data. These exist because the path-based tab routing migration (PR for branch `ple-infp-554-qsp`) shipped four similar migrations whose patterns drifted (some tab bars had `<nav aria-label="Tabs">`, some didn't; some children re-fetched parent data, some used outlet context; ~16 untyped `useParams() as { … }` casts proliferated).

## Detail-page route shape

A detail page that has tabs uses **path-based child routes**, never `?tab=` query strings.

```
/<feature>/:id
├── /                  → index (default tab content)
├── /<tab-name>        → child route per tab
├── /<dynamic-tab>     → :paramName for schema-driven tabs
└── /*                 → <Navigate to="." replace /> fallback
```

The parent route is a layout that renders header + tab bar + `<Outlet />`. Each tab is a separate lazy-loaded child route (`Component` named export, react-router `lazy()` convention).

References in the codebase:

- `frontend/app/src/app/router.tsx` — route definitions for `/profile`, `/branches/:branchName`, `/proposed-changes/:proposedChangeId`, `/objects/:objectKind/:objectId`
- `frontend/app/src/pages/<feature>/details.tsx` — parent layouts
- `frontend/app/src/pages/<feature>/<feature>-details/*.tsx` — child route shims

## Tab bar shape

Every tab bar uses the same skeleton:

```tsx
import { Row } from "@/shared/components/container";
import { LinkTab } from "@/shared/components/ui/link";

export function FeatureTabs() {
  return (
    <nav aria-label="Tabs">
      <Row className="border-gray-200 border-b">
        <LinkTab href="/feature/index">Index</LinkTab>
        <LinkTab href="/feature/data">Data</LinkTab>
      </Row>
    </nav>
  );
}
```

Required:

- **`<nav aria-label="Tabs">` wrapper.** Both for accessibility and because E2E tests use `page.getByRole("navigation", { name: "Tabs" })` / `page.getByLabel("Tabs")`. Missing the wrapper silently breaks tests on a future selector tightening.
- **`LinkTab` from `@/shared/components/ui/link.tsx`.** Owns the active-state styling (uses `useMatch({ path: href, end: true })` internally), focus ring, and optional `scrollIntoViewOnActive` for dynamic tabs.
- **Absolute hrefs** built via a dedicated URL helper (see [URL helpers per detail family](#url-helpers-per-detail-family)).

## Sharing parent-loaded data with children

When the parent route loads data the children need, do **not** re-call the same query in each child shim — even though TanStack Query will cache-hit, you still pay the hook invocation cost on every render and end up with dead `if (!data) return null` guards.

Use `<Outlet context>` + a typed hook with a runtime guard:

```tsx
// entities/<feature>/ui/use-feature-outlet.ts
import { useOutletContext } from "react-router";

export interface FeatureOutletContext {
  data: FeatureData;
  /* whatever the parent loads */
}

export function useFeatureOutlet(): FeatureOutletContext {
  const context = useOutletContext<FeatureOutletContext | null>();
  if (!context) {
    throw new Error(
      "useFeatureOutlet must be used inside the feature parent route's <Outlet>"
    );
  }
  return context;
}
```

```tsx
// pages/<feature>/details.tsx
<Outlet context={{ data, ... } satisfies FeatureOutletContext} />
```

The `satisfies` clause keeps producer and consumer in lockstep without widening the inferred type.

The runtime `throw` prevents silent corruption when the hook is mistakenly used outside the parent route.

References:

- `frontend/app/src/entities/nodes/object/ui/object-details/use-object-details-outlet.ts`
- `frontend/app/src/entities/proposed-changes/ui/use-proposed-change-outlet.ts`

When the children only need URL params (no parent fetch), skip the outlet context and let each child read params directly via `useRequiredParams`.

## Reading route params

Use `useRequiredParams` from `@/shared/hooks/use-required-params.ts` for params the route guarantees:

```tsx
const { branchName } = useRequiredParams("branchName");
// ✅ string, throws clearly if missing
```

Not `useParams() as { branchName: string }` — that's a compile-time lie that crashes downstream when the param is missing.

When a param is genuinely optional (e.g., a button rendered both inside and outside a relationship route), use plain `useParams()` and treat the result as `string | undefined`:

```tsx
const { relationshipName } = useParams();
// relationshipName is string | undefined — handle both branches
```

## URL helpers per detail family

Every detail page family owns a helper that centralizes its URL construction:

| Family | Helper | Location |
|---|---|---|
| Generic objects | `getObjectDetailsUrl(kind, id, overrideParams?, tabSegment?)` | `frontend/app/src/entities/nodes/utils.ts` |
| Branches | `getBranchDetailsUrl(branchName, tab?, overrideParams?)` | `frontend/app/src/entities/branches/utils.ts` |
| Proposed changes | (use `getObjectDetailsUrl` with `PROPOSED_CHANGE_OBJECT` kind) | — |
| Resource manager | (use `getObjectDetailsUrl`) | — |

When you add a new detail family with tabs, add a `getXxxDetailsUrl(id, tab?)` helper in the entity's `utils.ts` and use it from the tab bar **and** from any callsite that links into a tab (search bars, summary widgets, deep links). Inline `/feature/${id}/${tab}` strings are antipatterns — see [URL Construction](url-construction.md).

## Child route shims

Each child route is a thin shim file under `pages/<feature>/<feature>-details/`. The shim:

1. Reads outlet context (or required params).
2. Renders the actual content component (lives in `entities/`).
3. Exports `Component` (react-router `lazy()` convention — not `default`).

```tsx
// pages/feature/feature-details/data-tab.tsx
import { useFeatureOutlet } from "@/entities/feature/ui/use-feature-outlet";
import { DataView } from "@/entities/feature/ui/data-view";

export function Component() {
  const { data } = useFeatureOutlet();
  return <DataView data={data} />;
}
```

Keep shims under ~10 lines. Real logic lives in the rendered component, not the shim.

## Wildcard fallback for unknown sub-paths

Every detail-page subtree must end with a wildcard child that redirects to the index:

```tsx
{
  // Redirect /<feature>/:id/<unknown> back to the index tab.
  // `.` resolves to the parent matched route.
  path: "*",
  element: <Navigate to="." replace />,
},
```

Without this, navigating to a typo'd or stale URL renders the parent shell with an empty `<Outlet />` — a regression vs the QSP-based pages that fell back to a default tab.

## Loading and error gating

The parent layout owns loading/error states for its data fetch. Children mount only after the parent has resolved:

```tsx
function ParentLayout() {
  const { data, isPending, error } = useFeatureQuery();

  if (isPending) return <LoadingIndicator />;
  if (error || !data) return <ErrorState />;

  return (
    <Card>
      <Header data={data} />
      <FeatureTabs />
      <Outlet context={{ data } satisfies FeatureOutletContext} />
    </Card>
  );
}
```

Children consequently can rely on `data` being defined and skip defensive `if (!data) return null` checks. The outlet hook's runtime guard catches genuine misuse (component mounted outside the parent).

## Anti-patterns observed in past PRs

| Anti-pattern | Replacement |
|---|---|
| `?tab=foo` URL state for tab navigation | Nested child routes + `LinkTab` + `<Outlet />` |
| Tab bar without `<nav aria-label="Tabs">` | Always wrap; E2E selectors and screen readers depend on it |
| Children re-calling the same parent query | `<Outlet context>` + typed hook with runtime guard |
| `useParams() as { foo: string }` for guaranteed params | `useRequiredParams("foo")` |
| Inline `/branches/${branchName}/${tab}` template duplicated across files | Dedicated `getBranchDetailsUrl(branch, tab?)` helper |
| Detail page subtree without `path: "*"` fallback | Always redirect unknown sub-paths to the index |
| `default` export from a child route shim | `Component` named export — react-router `lazy()` requires it |

## See also

- [TypeScript Coding Standards](typescript.md) — `useRequiredParams` rule, banned `?.x!` pattern
- [URL and Path Construction](url-construction.md) — helper-per-family rule
- [Page Architecture](page-architecture.md) — state ownership rules
- [Component Patterns](component-patterns.md) — reuse-first checklist
- `dev/knowledge/frontend/shared-components.md` — `LinkTab`, `useRequiredParams` inventory entries
