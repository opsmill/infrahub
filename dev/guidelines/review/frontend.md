# Infrahub frontend review

Flag violations of these Infrahub frontend conventions in frontend/app/**. Skip formatting, import order, unused code and dead exports: Biome, betterer and knip gate them.

## React

- Flag `useMemo`, `useCallback`, `memo()`/`React.memo`. React Compiler is enabled and memoizes automatically.
- Flag `forwardRef`. React 19: `ref` is a regular prop.
- Flag `useEffect` that copies props/query data into `useState`, or derives a value. Derive during render, or use form `defaultValues`.
- Flag an effect running a must-succeed step (fetch, redirect) whose deps stay stable after failure; it never retries (`retry: false` app-wide). Add a fetch-identity dep such as `dataUpdatedAt`.
- Flag named React imports (`import { useState } from "react"`). Use `import React from "react"` and `React.useState`.

## Comments

- Flag comments that narrate what the next line does (`// set the title`, `// render the cards`). Only the non-obvious why (rationale, gotcha, invariant) is allowed.

## Reuse before reinventing

- Flag new pickers, comboboxes, kind selectors, cards, modals, buttons or inputs that duplicate `@infrahub/ui` or `shared/components/`. Wrap or extend at 80%+ fit.
  - Styled `<section className="rounded-md border ... shadow">` -> `Card`; custom focus-trapped dialog -> `Modal`; `<button className="bg-...">` -> `Button`; kind+object combobox -> wrap `PeerInput`/`PeerField`; kind select -> `NodeKindSelect`/`NodeKindField`/`KindMultiSelect`.
- Flag direct `navigator.clipboard.*` or a hand-rolled "Copied!" state. Use `useCopyToClipboard`.
- Flag `.field.tsx` components used outside a `<Form>`. Use the underlying `shared/components/inputs/` primitive.

## Data fetching and entity layers

- Flag `gql`/`graphql()` strings or `graphqlClient.query/mutate` in `ui/` or pages. Flow: `api/*-from-api.ts` -> `domain/use-cases/` -> `ui/queries/*.query.ts`.
- Flag a hand-rolled single-node lookup (`resolveUuid`, etc.). Use `useGetObject({ objectId, objectSchema })` with a schema from `useSchema`.
- Flag imports of another entity's `api/` (cross-entity goes via `domain/` or `ui/`), and `domain/` importing `ui/`, React, TanStack, Jotai or browser storage. Review-only; no lint guard.
- Flag `domain/` reading global state (branch, date, schema) or a page size. Inject from `ui/` as params.
- Flag `queryOptions`/`useQuery` in `domain/`. They belong in `ui/queries/`.
- Flag entity vocabulary (schema kinds, states, filter names) or entity-aware code added under `shared/`.
- Flag new entity-root `types.ts`, `constants.ts`, `stores.ts` or `utils/`. Use `domain/model`, `domain/rules`, `ui/`, `api/*.mappers.ts`.
- Flag `@urql/core` imports outside `shared/api/graphql/client.ts`.
- Flag cache invalidation passed at the callsite instead of `onSuccess`/`onSettled` inside the `.mutation.ts` hook (unless the file has an `invalidation-at-callsite` comment).
- Flag a `useMutation` `onError` toast without `context: { processErrorMessage: () => {} }` on the mutate call. The client already toasts; users see two.
- Flag positional query keys (`[...all, "x", id, depth]`). Use one params object: `[...all, "x", { id, depth }]`.

## Branches and backend authority

- Flag default-branch detection by name. `main` is configurable.
  ❌ `branches.find((b) => b.name === "main")` ✅ `branches.find((b) => b.is_default)` / `currentBranch.is_default`
- Flag client constants that mirror server behaviour: `HIDDEN_NAMESPACES`, hardcoded `["Core", "Internal", ...]`, hidden schema kinds, default sorts/pagination/access checks. Use `useGetSchema`/the API.

## Type safety (not lint-enforced here)

- Flag new `any`, postfix `!`, and `as` assertions. Use `unknown` + type guards or narrow first. "Safe by construction" `map.get(k)!` counts.
- Flag `x?.y!`: always a type lie. Narrow with a conditional or early return.
- Flag `useParams() as {...}`. Guaranteed params: `useRequiredParams("id")`. Optional: `useParams<{ id: string }>()`, then narrow.
- In a PR that rewrites a file, flag `!`/`as`/`any` left in the rewritten expressions.

## Routing and URLs

- Flag `?tab=` query params for tabs. Tabs are nested child routes + `<Outlet />`.
- Flag inline object/detail paths (`` `/objects/${kind}/${id}` ``, `` `/branches/${name}/${tab}` ``). Use `getObjectDetailsUrl`, `getBranchDetailsUrl`, `getProposedChangeDetailsUrl`. `constructPath` is for non-object pages only.
- Flag a detail-URL helper whose `tab` param is plain `string`. Require a string-literal union.
- Flag tab bars not wrapped in `<nav aria-label="Tabs">` or not using `LinkTab`. E2E selectors depend on the nav.
- Flag child tab routes re-calling the parent's query. Use `<Outlet context={{...} satisfies Ctx}>` + a typed `use-*-outlet` hook that throws outside the route.
- Flag `<Outlet context>` without `satisfies`, and outlet context interfaces that `extends` a fetch response type.
- Flag route shims with `default` export (must export `Component`) or real logic (>~10 lines).
- Flag a detail-page subtree missing the `path: "*"` -> `<Navigate to="." replace />` fallback.
- Flag the same entity captured under different param names across routes (`:task` vs `:taskId`).
- Flag wrappers of `Link`/`LinkTab` taking `href`/`path` instead of `to`.
- Flag a provider backed by an authenticated query that mounts for logged-out users. Gate the mount on `isAuthenticated`; `RequireAuth` is not a gate (anonymous access renders it).

## Page and component structure

- Flag state with two owners: page and child `useState` for one field, URL state copied into Jotai, form values mirrored into `useState`, `searchParams` read in two places. Pages own URL sync (`useFilters`/`nuqs`); forms own fields (`useForm`) and call `onSubmit`, never write the URL.
- Flag URL-shareable state (filters, selection, mode) kept in `useState`.
- Flag pure helpers (formatters, mappers, aggregations, color/icon resolvers) inside `.tsx` files. Move to `utils.ts`/`domain/rules` with a Vitest test.
- Flag pages >~250 lines, forms >~300, pickers >~200, primitives >~150 mixing concerns (soft budgets).
- Flag nested ternaries for multi-state rendering. Use early returns (order: `isPending`, `error`, `isSuccess`, default).
- Flag react-aria overlays rendered conditionally (`{open && <Modal isOpen>}`). Pass the boolean to `isOpen` so exit animations run.
- Flag a tab badge using `count ?? 0` (masks errors) or a loading policy differing from sibling tabs.

## Styling

- Flag `<div className="flex ...">` / `flex flex-col`. Use `Row`/`Col` from `@/shared/components/container`.
- Flag inline `style={{}}`, CSS modules, and arbitrary colors (`bg-[#1e40af]`).
- Flag conditional class strings built by concatenation/template literals. Use `classNames()`. Use CVA for 2+ variants.
- Flag raw palette classes where a semantic theme token exists (`bg-surface`, `text-foreground-muted`); readable text demoted to the faintest tier (below WCAG AA); theme tokens on fixed-scheme surfaces.

## Forms

- Flag form fields not using the `{ source, value }` shape: empty defaults must be `DEFAULT_FORM_FIELD_VALUE`, changes must go through `updateFormFieldValue`/`updateAttributeFieldValue`/`updateRelationshipFieldValue`.
- Flag `focus:` styles for rings (use `focus-visible`/`focusVisibleStyle`) and `autoFocus` in long forms.

## Naming and files

- Flag data hooks without a CRUD verb (`useEffectivePreferences` -> `useGetEffectivePreferences`).
- Flag domain types suffixed `*Response`/`*Output`/`*Data`/`*Outcome`. Use `{Verb}{Noun}Params`/`{Verb}{Noun}Result`.
- Flag non-kebab-case files (except `shared/hooks/useCamelCase.ts`), `__tests__/` dirs, `index.ts` barrels, `.types.ts` files, `.query.ts`/`.mutation.ts` under `api/`, and `api/` files not ending `-from-api.ts`, `-query.ts` or `.mappers.ts`.
- Flag default exports except `.field.tsx` files.

## Do NOT flag

- Missing `useMemo`/`useCallback`/`memo` or "unstable" inline functions/objects (React Compiler).
- `import React from "react"` + `React.useX`; `ref` as a plain prop.
- `export function Component()` in route shims; default exports in `.field.tsx`.
- `// invalidation-at-callsite` comments and callsite `onSuccess` in those files; `processErrorMessage: () => {}`.
- A mount gate on `isAuthenticated` instead of `enabled: isAuthenticated`.
- Queries not retrying on failure (`retry: false` is deliberate).
- `shared/components/form/` importing entities; `shared/api/` importing `authentication`/`nodes/filters`.
- Pre-existing TS errors in untouched code (betterer ratchets them), or existing migration debt the PR did not add.

Sources: frontend/app/AGENTS.md, frontend/app/biome.jsonc, dev/guidelines/frontend/{component-patterns,page-architecture,route-architecture,naming-conventions,typescript,styling,object-forms,url-construction}.md, dev/knowledge/frontend/{react,shared-components,entities-structure,branches}.md
