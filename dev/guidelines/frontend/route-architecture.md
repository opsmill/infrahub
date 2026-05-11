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

The `satisfies` clause keeps producer and consumer in lockstep without widening the inferred type. **Always include `satisfies <Context>` on the producer side** — without it, a typo or missing field on the producer compiles silently and breaks consumers at runtime.

The runtime `throw` prevents silent corruption when the hook is mistakenly used outside the parent route.

### Don't extend the fetch response type

Define the outlet context interface explicitly with the exact fields the parent passes. Do **not** `extends FetchResponse` — coupling the route context to the network response shape silently leaks every new query field to every child consumer:

```tsx
// ❌ Bad — every new field added to the query becomes route-context state
export interface FeatureOutletContext extends GetFeatureResponse {
  extraThing: string;
}

// ✅ Good — explicitly enumerate, optionally pull individual field types
export interface FeatureOutletContext {
  data: GetFeatureResponse["data"];
  metadata: GetFeatureResponse["metadata"];
  extraThing: string;
}
```

References:

- `frontend/app/src/entities/nodes/object/ui/object-details/use-object-details-outlet.ts`
- `frontend/app/src/entities/proposed-changes/ui/use-proposed-change-outlet.ts`
- `frontend/app/src/entities/branches/ui/use-branch-details-outlet.ts`

When the children only need URL params (no parent fetch), skip the outlet context and let each child read params directly via `useRequiredParams`. **However**, if a sibling tab already exists with an outlet hook, prefer extending that hook rather than mixing patterns within the same detail-page family — symmetric children are easier to navigate.

## Reading route params

Use `useRequiredParams` from `@/shared/hooks/use-required-params.ts` for params the route guarantees:

```tsx
const { branchName } = useRequiredParams("branchName");
// ✅ string, throws clearly if missing
```

Not `useParams() as { branchName: string }` — that's a compile-time lie that crashes downstream when the param is missing.

When a param is genuinely optional (e.g., a button rendered both inside and outside a relationship route), use the `useParams<T>()` typed generic — never `as` casts:

```tsx
// ✅ Optional params via the typed generic
const { objectKind, objectId } = useParams<{ objectKind: string; objectId: string }>();
// objectKind / objectId are inferred as string | undefined — narrow before use

// ❌ The type lie pattern
const { objectKind, objectId } = useParams() as { objectKind?: string; objectId?: string };
```

If a child component reads a param to do work, prefer **passing the value as a prop from a parent that already has it** instead of re-reading params in the child. The parent has more context (it can decide whether the param is guaranteed) and the child becomes routing-agnostic and easier to test.

## Route param naming consistency

When two different routes capture the same logical entity, use the **same param name** in both routes. Example:

```tsx
// ✅ Both routes name the captured id "taskId"
{ path: "/tasks/:taskId", lazy: () => import("@/pages/tasks/task-details") },
{ path: "/proposed-changes/:proposedChangeId/tasks/:taskId", … },
{ path: "/objects/:objectKind/:objectId/tasks/:taskId", … },

// ❌ One route uses :task, others use :taskId
//    Forces components like TaskItemDetails to read both params and fall back:
//      const { task, taskId } = useParams();
//      const id = task ?? taskId;
```

Every shared component that consumes the param then reads a single name. Inconsistent param names produce dual-read fallbacks that drift over time and silently break when one route is renamed.

## URL helpers per detail family

Every detail page family owns a helper that centralizes its URL construction:

| Family | Helper | Location |
|---|---|---|
| Generic objects | `getObjectDetailsUrl(kind, id, overrideParams?, tabSegment?)` | `frontend/app/src/entities/nodes/utils.ts` |
| Branches | `getBranchDetailsUrl(branchName, tab?, overrideParams?)` | `frontend/app/src/entities/branches/utils.ts` |
| Proposed changes | `getProposedChangeDetailsUrl(id, tab?, overrideParams?)` | `frontend/app/src/entities/proposed-changes/utils.ts` |
| Resource manager | (use `getObjectDetailsUrl`) | — |

When you add a new detail family with tabs, add a `getXxxDetailsUrl(id, tab?)` helper in the entity's `utils.ts` and use it from the tab bar **and** from any callsite that links into a tab (search bars, summary widgets, deep links). Inline `/feature/${id}/${tab}` strings are antipatterns — see [URL Construction](url-construction.md).

The `tab` argument **must** be a string-literal union (e.g. `BranchDetailsTab = "data" | "files" | "artifacts" | "schema"`), never plain `string`. Plain `string` collides with dynamic path segments like `:relationshipName` and silently routes a typo to a 404-redirect.

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

## Wrapper component prop names mirror the underlying primitive

When you wrap a primitive (`LinkTab`, `Link`, `Button`) in a feature-specific component, **use the same prop name as the primitive**. In this codebase the navigation primitives wrap react-router's `NavLink` / `Link`, so the navigation prop is **`to`** — never `href`, `path`, or `link`:

```tsx
// LinkTab and every wrapper above it use `to`, matching react-router's NavLink/Link
interface ProposedChangeTabProps {
  to: string; // ✅ matches LinkTab → NavLink
  label: string;
}

<LinkTab to={getBranchDetailsUrl(branchName, "data")}>Data</LinkTab>
<ProposedChangeTab to={getProposedChangeDetailsUrl(id, "data")} label="Data" />
```

Reserve `href` for the rendered DOM attribute on `<a>` (which react-router sets automatically). Diverging prop names — e.g. a wrapper that takes `href` and forwards to a primitive that takes `to` — force every caller to remember which name applies and break greppability (`rg "to={"` would miss the wrapper).

## Tab badge counts during loading

A tab that displays a count from a query has three visual states: loading, loaded-with-count, error/no-data. Pick **one** rendering policy and apply it across the family:

```tsx
// ✅ Either render nothing when undefined (the recommended default)
{!isPending && <Badge>{count}</Badge>}

// ❌ Don't mix `?? 0` (renders 0 on error) with siblings that render nothing
{!isPending && <Badge>{count ?? 0}</Badge>}
```

The `?? 0` form silently masks query failures as "zero" and makes it look like a successful empty result. If the design genuinely needs a "0 when error" rendering, document why and apply it to *all* sibling tabs.

## Symmetric handling of structurally identical fields

When two fields on the same parent object share the same backend nullability (e.g. `source_branch` and `destination_branch` on `ProposedChange`), handle them symmetrically. Either both gate the entire layout, or neither does:

```tsx
// ✅ Symmetric — one guard, one error UI for both fields
if (!pc.source_branch?.value || !pc.destination_branch?.value) {
  return <NoDataFound message="Proposed change is missing a source or destination branch." />;
}

// ❌ Asymmetric — guards source, then renders broken `/branches/undefined` link for destination
if (!pc.source_branch?.value) return <NoDataFound … />;
<Link to={`/branches/${pc.destination_branch?.value}`}>…</Link>
```

Comments justifying asymmetry ("destination_branch is conventionally always present") rot — the actual nullability is what runs.

## Verifying cleanup after a deletion or rewrite

When you delete a consumer (a tab cell, a switch statement, a whole legacy component), other exports may become orphaned. TypeScript happily compiles dead exports — only static analysis catches them. After any migration that deletes consumers, run:

```bash
cd frontend/app && pnpm knip
```

Knip surfaces:

- Unused files (e.g. a primitive that only the deleted component imported)
- Unused exports (e.g. QSP-value constants that only the deleted switch statements referenced)
- Unused dependencies and types

The path-based tab routing migration left `Pill`, `TASK_TAB`, and `DIFF_TABS` orphaned because Phase 5 deleted their only consumer (`shared/components/tabs.tsx` plus various QSP-driven switches). The per-phase verification ran `pnpm test`, `pnpm exec tsc`, and `pnpm biome:fix` — none of which catches dead exports. CI's knip step found them a release later.

Add `pnpm knip` to your verification commands any time a PR deletes a component, switches a switch-on-QSP to nested routes, or otherwise removes the last importer of a helper. Fix in the same PR — orphaned exports compound and become harder to delete with confidence as time passes.

## Anti-patterns observed in past PRs

| Anti-pattern | Replacement |
|---|---|
| `?tab=foo` URL state for tab navigation | Nested child routes + `LinkTab` + `<Outlet />` |
| Tab bar without `<nav aria-label="Tabs">` | Always wrap; E2E selectors and screen readers depend on it |
| Children re-calling the same parent query | `<Outlet context>` + typed hook with runtime guard |
| `useParams() as { foo: string }` for guaranteed params | `useRequiredParams("foo")` |
| `useParams() as { foo?: string }` for genuinely optional params | `useParams<{ foo: string }>()` typed generic |
| Inline `/branches/${branchName}/${tab}` template duplicated across files | Dedicated `getBranchDetailsUrl(branch, tab?)` helper |
| Tab helper taking `tabSegment: string` instead of a literal union | `tab?: "data" \| "files" \| ...` so callers can't typo |
| Detail page subtree without `path: "*"` fallback | Always redirect unknown sub-paths to the index |
| `default` export from a child route shim | `Component` named export — react-router `lazy()` requires it |
| Outlet context `extends FetchResponse` | Explicitly enumerate fields the parent actually passes |
| Producer `<Outlet context={...}>` without `satisfies` | Always `satisfies <ContextType>` |
| Different param names for the same entity across routes (`:task` vs `:taskId`) | Pick one canonical name and use it in every route |
| Wrapper component renames a primitive's prop (`href` → forwards to NavLink's `to`) | Mirror the primitive's prop name (`to`) in every wrapper |
| Tab count `<Badge>{count ?? 0}</Badge>` while siblings use `<Badge>{count}</Badge>` | Consistent loading/error policy across all tabs in the family |
| Asymmetric null guards on twin fields (e.g. source vs destination branch) | Same guard treatment for structurally identical fields |
| Boy-scout: leaving `!` non-null assertions in a file you rewrote in the same PR | Audit and fix on rewrite — see [typescript.md](typescript.md) |
| Deleting a component without running `pnpm knip` to catch orphaned exports | Run `pnpm knip` whenever a PR removes a consumer; fix dead exports in the same PR |

## See also

- [TypeScript Coding Standards](typescript.md) — `useRequiredParams` rule, banned `?.x!` pattern
- [URL and Path Construction](url-construction.md) — helper-per-family rule
- [Page Architecture](page-architecture.md) — state ownership rules
- [Component Patterns](component-patterns.md) — reuse-first checklist
- `dev/knowledge/frontend/shared-components.md` — `LinkTab`, `useRequiredParams` inventory entries
