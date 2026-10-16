---
paths:
  - "frontend/app/src/**/*.ts"
  - "frontend/app/src/**/*.tsx"
---

# Frontend components, styling and forms

Applies to React code in `frontend/app/src/`. Biome, betterer and knip already gate formatting, import order, unused code and dead exports.

## React

- Do not add `useMemo`, `useCallback`, `memo()` or `React.memo`: React Compiler memoizes automatically.
- Do not use `forwardRef`; in React 19 `ref` is a regular prop.
- Do not copy props or query data into `useState` through a `useEffect`, or derive a value in an effect. Derive it during render, or use form `defaultValues`.
- An effect that runs a step which must succeed (a fetch, a redirect) needs a dependency that changes after a failure, such as `dataUpdatedAt`; otherwise it never retries, because queries run with `retry: false`.
- Import React as `import React from "react"` and call `React.useState`, not named imports.

## Reuse before building

- Do not build a picker, combobox, kind selector, card, modal, button or input that duplicates `@infrahub/ui` or `shared/components/`; wrap or extend one that fits 80% or more.
  - A styled bordered `<section>` is a `Card`, a focus-trapped dialog is a `Modal`, a styled `<button>` is a `Button`.
  - A kind and object combobox wraps `PeerInput` or `PeerField`; a kind select is `NodeKindSelect`, `NodeKindField` or `KindMultiSelect`.
- Copy to the clipboard with `useCopyToClipboard`, not `navigator.clipboard` and a hand-made "Copied!" state.
- Use a `.field.tsx` component only inside a `<Form>`; outside one, use the primitive in `shared/components/inputs/`.

## Page and component structure

- Give each piece of state one owner. Pages own URL sync (`useFilters`, `nuqs`); forms own their fields (`useForm`), call `onSubmit`, and never write the URL. Do not mirror URL state into Jotai or form values into `useState`.
- Keep state that a URL should share (filters, selection, mode) in the URL, not in `useState`.
- Move pure helpers (formatters, mappers, aggregations, colour or icon resolvers) out of `.tsx` files into `utils.ts` or `domain/rules`, with a Vitest test.
- Soft size budgets: pages about 250 lines, forms 300, pickers 200, primitives 150. Split a file over budget that mixes concerns.
- Render several states with early returns in the order `isPending`, `error`, `isSuccess`, default, not with nested ternaries.
- Pass the open state of a react-aria overlay to `isOpen`; do not mount it conditionally (`{open && <Modal isOpen>}`), which skips the exit animation.
- A tab badge does not use `count ?? 0`, which hides errors, and loads like its sibling tabs.

## Styling

- Use `Row` and `Col` from `@/shared/components/container`, not `<div className="flex ...">`.
- Do not use inline `style={{}}`, CSS modules or arbitrary colours (`bg-[#1e40af]`).
- Build conditional classes with `classNames()`, and with CVA for two or more variants, not with concatenation or template literals.
- Use a semantic theme token (`bg-surface`, `text-foreground-muted`) where one exists, not a raw palette class. Do not put readable text in the faintest tier, which fails WCAG AA, or theme tokens on a surface with a fixed colour scheme.

## Forms

- Form fields use the `{ source, value }` shape: empty defaults are `DEFAULT_FORM_FIELD_VALUE`, and changes go through `updateFormFieldValue`, `updateAttributeFieldValue` or `updateRelationshipFieldValue`.
- Style focus rings with `focus-visible` or `focusVisibleStyle`, not `focus:`. Do not use `autoFocus` in long forms.

## Not violations

- A missing `useMemo`, `useCallback` or `memo`, or an inline function or object passed as a prop.
- `export function Component()` in route shims, and default exports in `.field.tsx` files.
- A mount gate on `isAuthenticated` instead of `enabled: isAuthenticated`.
- Queries that do not retry on failure.

Full reference: `dev/guidelines/frontend/component-patterns.md`, `page-architecture.md`, `styling.md`, `object-forms.md`; `dev/knowledge/frontend/react.md`, `shared-components.md`.
