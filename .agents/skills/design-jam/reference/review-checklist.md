# Review checklist

Read this in phase 4. The *Usability* list runs in both reviews. *Tidy*, *Critique* and
*Readiness* run in the reduced review only: they come from this skill's rules and the
frontend docs, not from the paid review skills. Check each item on the running prototype,
with worst-case data, and write each failure in `04-review.md`.

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

## Usability

Each check names the [Laws of UX](https://lawsofux.com/) it comes from. Write a failure
with the law's name, so the reason can be looked up.

- **Familiar**: the screen works like the other Infrahub views (same filters, row
  actions and menus), uses terms network engineers know, and puts help next to the field
  or action that needs it. *Jakob's Law, Mental Model, Paradox of the Active User.*
- **Few choices**: one main action per row or screen, the others in a menu; long option
  lists, such as schema kinds, have a search. *Hick's Law, Choice Overload.*
- **Easy to reach**: frequent actions are large, close to what they act on, and first in
  their menu. *Fitts's Law, Serial Position Effect.*
- **Grouping**: related items share space, a container or a line, and items that look the
  same mean the same thing on every screen. *Law of Proximity, Law of Common Region, Law of
  Uniform Connectedness, Law of Similarity.*
- **Emphasis**: only what needs action stands out (a conflict, a failed task), next to the
  element it is about. *Von Restorff Effect, Selective Attention.*
- **Little to remember**: long lists are grouped or filtered, values to compare are side
  by side, and rare details are folded away. *Miller's Law, Chunking, Working Memory,
  Cognitive Load.*
- **Infrahub does the work**: the screen shows a state rather than making the user work it
  out, and inputs accept common formats. *Tesler's Law, Postel's Law.*
- **Feedback**: every action responds within 400 ms, even with a loading state; a flow ends
  with its result and the next step; unfinished work (drafts, failed tasks) stays visible.
  *Doherty Threshold, Peak-End Rule, Zeigarnik Effect.*

When judging, test the worst-case data before the looks, because a polished screen hides
usability problems (*Aesthetic-Usability Effect*), and design first for the few actions
used most (*Pareto Principle*).

## Readiness

- Every state from phase 3 renders: loading, empty, error, permission denied and too much
  data.
- Every interactive element can be reached and used with the keyboard, and has an
  accessible name.
- Nothing in the final revision depends on mock behaviour that `05-implement.md` cannot
  list under *Replace*.
- Every knob has a chosen value in `03-decisions.md`.
