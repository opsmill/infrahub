---
paths:
  - "frontend/app/src/**/*.ts"
  - "frontend/app/src/**/*.tsx"
---

# Frontend conventions

Applies when writing or changing frontend code under `frontend/app/src/`. These are the conventions reviewers raise most often; the fuller reference lives in `dev/guidelines/frontend/` and `dev/knowledge/frontend/`.

## Entity layers: api → domain → ui

Each entity has three layers with one-way imports (`ui/ → domain/ → api/`):

- **`api/`** — transport only: make the network/GraphQL call and return the raw response. No business logic, no React.
- **`domain/`** — pure TypeScript business logic: orchestration, decisions, validation, mapping. A domain async function does `call api → check for errors → validate → map to domain types`, and *answers the business question* (e.g. `hasGlobalPermission()`), not just "fetch data". Extract reusable pure logic into a `domain/` rule module so it is unit-testable on its own — don't bury it in a component.
- **`ui/`** — React + TanStack Query wiring only. `queryOptions`/`useQuery`/`useMutation` live in `ui/queries/`; keep business logic out of `useQuery`'s `select` (call a domain function instead).

Full detail: `dev/knowledge/frontend/entities-structure.md`.

## React Query

- Build query keys from the entity's key factory (`{noun}.query-keys.ts` → `{noun}QueryKeys`); never hardcode a key array.
- Cache invalidation lives inside the `useMutation` hook (`onSuccess`/`onSettled`), not at the call site.
- Do not set Apollo `fetchPolicy` at a call site — the default is `no-cache` and TanStack Query is the only server-state cache.

See `dev/guidelines/frontend/naming-conventions.md` and `dev/knowledge/frontend/entities-structure.md`.

## React (compiler enabled)

Do **not** use `useMemo`, `useCallback`, or `memo()` — React Compiler memoizes automatically (`dev/knowledge/frontend/react.md`). Derive state during render instead of syncing it with effects.

## Types

- No `any`, no `!` (non-null assertion), no `as` — narrow with a guard or early return.
- Prefer generated types/enums (e.g. `DateFormat` from the generated GraphQL types) over `string`; model nullability to the backend reality rather than making everything optional.
- Return `null` for an intentional empty value, `undefined` for absent/not-provided.

## Comments

Do not add comments that narrate what the code is doing. Explain a non-obvious *why* only; a comment that restates the code is noise and rots. (Same bar as the backend `code-doc-style` rule.)

## Reuse first

Before building anything generic (a row/layout wrapper, a combobox, a modal variant), check `dev/knowledge/frontend/shared-components.md` and the `@infrahub/ui` design system — compose existing primitives instead of hand-rolling.

## Naming

File and hook names follow `dev/guidelines/frontend/naming-conventions.md`. Hook names match the operation (`useUpsert…` not `useUpdate…` for an upsert) and predicate hooks read as a question (`useHasX`).
