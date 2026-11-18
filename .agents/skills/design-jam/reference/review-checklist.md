# Reduced review checklist

Read this in phase 4 when preflight reports the reduced review. These lists come from this
skill's rules and the frontend docs, not from the paid review skills. Check each item on
the running prototype, with worst-case data, and write each failure in `04-review.md`.

## Tidy

- Repeated items (cards in a row, rows in a list) have the same padding, edges and
  baselines.
- Spacing comes from the layout components and theme tokens in
  [`dev/guidelines/frontend/styling.md`](../../../../dev/guidelines/frontend/styling.md),
  not from arbitrary values.
- Colours are theme tokens, and both themes are checked, as
  [`dev/knowledge/frontend/theming.md`](../../../../dev/knowledge/frontend/theming.md)
  describes. Readable text meets WCAG AA (4.5:1), including secondary text such as labels,
  badges and hints.
- Identical sibling controls use identical tokens and variants.
- Components come from `@infrahub/ui` where it has one
  ([`dev/knowledge/frontend/design-system.md`](../../../../dev/knowledge/frontend/design-system.md)),
  and every exception is listed in `01-system.md`.

## Critique

- The most important thing on the screen is the first thing seen, and the main action is
  the only primary button.
- Long values (schema kind names, node names, branch names) truncate or wrap without
  breaking the layout, and the full value can still be read.
- Labels and messages use Infrahub terms ("node", "branch", "schema"), and every error
  message says what happened and what to do next.
- Inactive controls are dimmed rather than disabled, as
  [`dev/guidelines/frontend/component-patterns.md`](../../../../dev/guidelines/frontend/component-patterns.md)
  describes, unless the decision in `03-decisions.md` says otherwise.
- Every decision in `03-decisions.md` is visible in the final revision.

## Readiness

- Every state from phase 3 renders: loading, empty, error, permission denied and too much
  data.
- Every interactive element can be reached and used with the keyboard, and has an
  accessible name.
- Nothing in the final revision depends on mock behaviour that `05-implement.md` cannot
  list under *Replace*.
- Every knob has a chosen value in `03-decisions.md`.
