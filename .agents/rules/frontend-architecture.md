---
paths:
  - "frontend/app/src/**/*.ts"
  - "frontend/app/src/**/*.tsx"
---

# Frontend data, routing, types and naming

Applies to TypeScript in `frontend/app/src/`.

## Data fetching and entity layers

- Keep `gql`/`graphql()` strings and `graphqlClient.query`/`mutate` out of `ui/` and pages. The flow is `api/*-from-api.ts` → `domain/use-cases/` → `ui/queries/*.query.ts`.
- Look up a single node with `useGetObject({ objectId, objectSchema })` and a schema from `useSchema`, not a hand-written lookup.
- Do not import another entity's `api/`; go through its `domain/` or `ui/`. `domain/` does not import `ui/`, React, TanStack, Jotai or browser storage, and does not read global state (branch, date, schema) or a page size: `ui/` passes them in as parameters.
- Put `queryOptions` and `useQuery` in `ui/queries/`, never in `domain/`.
- Do not add entity vocabulary (schema kinds, states, filter names) or entity-aware code under `shared/`.
- Do not add an entity-root `types.ts`, `constants.ts`, `stores.ts` or `utils/`; use `domain/model`, `domain/rules`, `ui/` or `api/*.mappers.ts`.
- Import `@urql/core` only in `shared/api/graphql/client.ts`.
- Invalidate caches in `onSuccess`/`onSettled` inside the `.mutation.ts` hook, not at the call site, unless the file carries an `invalidation-at-callsite` comment.
- A `useMutation` `onError` toast needs `context: { processErrorMessage: () => {} }` on the mutate call; the client already shows a toast, so users would see two.
- Query keys take one parameters object (`[...all, "x", { id, depth }]`), not positional values.

## Branches and backend authority

- Detect the default branch with `is_default`, never by name: the default branch name is configurable per deployment.
- Do not mirror server behaviour in client constants: hidden namespaces, hard-coded `["Core", "Internal", ...]`, hidden schema kinds, default sorts, pagination or access checks. Read them from `useGetSchema` or the API.

## Type safety

- Do not add `any`, postfix `!` or `as` assertions, including a "safe by construction" `map.get(k)!`. Use `unknown` with a type guard, or narrow first. `x?.y!` is always wrong.
- Read route parameters with `useRequiredParams("id")` when they are guaranteed, or `useParams<{ id: string }>()` and narrow; never `useParams() as {...}`.
- When a change rewrites a file, do not keep `!`, `as` or `any` in the rewritten expressions.

## Routing and URLs

- Build tabs as nested child routes with `<Outlet />`, not a `?tab=` query parameter. Wrap a tab bar in `<nav aria-label="Tabs">` with `LinkTab`; e2e selectors depend on it.
- Build object and detail paths with `getObjectDetailsUrl`, `getBranchDetailsUrl` and `getProposedChangeDetailsUrl`, not inline template strings. `constructPath` is for other pages. A detail-URL helper types its `tab` parameter as a string-literal union.
- A child tab route reads the parent's data through `<Outlet context={{...} satisfies Ctx}>` and a typed `use-*-outlet` hook that throws outside the route; it does not call the parent's query again. The outlet context interface does not `extends` a fetch response type.

## Naming and files

- Data hooks start with a CRUD verb (`useGetEffectivePreferences`, not `useEffectivePreferences`).
- Domain types are named `{Verb}{Noun}Params` and `{Verb}{Noun}Result`, not `*Response`, `*Output`, `*Data` or `*Outcome`.
- Files are kebab-case (except `shared/hooks/useCamelCase.ts`). No `__tests__/` folders, `index.ts` barrels or `.types.ts` files. `api/` files end in `-from-api.ts`, `-query.ts` or `.mappers.ts`, and hold no `.query.ts` or `.mutation.ts`.
- No default exports, except in `.field.tsx` files.

## Not violations

- `// invalidation-at-callsite` and a call-site `onSuccess` in that file; `processErrorMessage: () => {}`.
- `shared/components/form/` importing entities; `shared/api/` importing `authentication` or `nodes/filters`.
- TypeScript errors in untouched code (betterer ratchets them), and migration debt the change did not add.

Full reference: `dev/knowledge/frontend/entities-structure.md`, `branches.md`; `dev/guidelines/frontend/route-architecture.md`, `typescript.md`, `naming-conventions.md`, `url-construction.md`.
