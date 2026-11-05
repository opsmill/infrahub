# Improvements: instance badge design jam

Findings from the compressed run of 2026-11-05 (phases 0 to 5 in one session on the implementation
branch, no design branch and no design PR). Nothing is applied here; each line is a proposed edit.

## This skill

- `reference/design-history-panel.tsx`: `pnpm biome:fix` strips the leading space in the
  `` `${dragging ? " djh-dock--dragging" : ""}` `` template, which concatenates two class names.
  Proposed edit: build the class list with an array and `.filter(Boolean).join(" ")` in the
  reference file, so a copy survives the formatter.
- `reference/design-history-panel.tsx`: Biome's `a11y/noLabelWithoutControl` fires on the knob
  `<label>`. Proposed edit: wire the label to its control with `htmlFor`, or ship the
  `biome-ignore` line in the reference file.
- `SKILL.md`, phase 2: the fake shell cannot drive `SidebarProvider`, `Sidebar` and
  `SidebarTrigger` from a knob, because they read and write `localStorage.sidebar_state` and
  would change the real app's state. Proposed edit: say that a direction which fakes the shell
  copies `Sidebar`'s classes and `data-state` onto a `Card` and keeps the header, content and
  footer primitives.
- `SKILL.md`, start of every invocation: the full process (design branch, design PR with preview,
  feedback rounds over days) is sized for a screen. Proposed edit: add a `--compressed` mode for a
  component-sized change: phases 0 to 5 in one session on the implementation branch, prototype
  deleted before the PR, `.design/<slug>/` kept.
- `SKILL.md`, phase 2: the prototype route sits behind `ConfigProvider`, which blocks every route
  until `GET /api/config` succeeds, so the route needs a running backend whose
  `cors_allow_origins` includes the dev server's origin. Proposed edit: state it, and point at a
  screenshot script that mocks the endpoint (`shots.py` in this run's scratchpad did).

## A skill it invokes

- `emil-prototype` tells the run to copy its own picker (`PICKER.md`); the design jam owns the
  history panel instead. Recorded only: the jam's panel wins, and the run skipped `PICKER.md`.
- `emil-prototype` asks for `emil-design-foundations`, `emil-ui-polish` and
  `emil-touch-and-accessibility` on every run; the jam's phase 4 runs the last two itself. The
  prototype builder loaded them once; no conflict, but the double instruction costs a read.

## Internal docs

- `frontend/app/AGENTS.md` or `dev/guides/frontend/writing-unit-tests.md`: `pnpm test -- <files>`
  does not filter in this repo (pnpm forwards `--` and vitest runs the whole suite); use
  `pnpm exec vitest run <files>`. Three agents in this run hit it.
- `dev/knowledge/frontend/shared-components.md`, "Page title" row: the hook now registers the page
  title in an atom and a single `DocumentTitle` owner writes `document.title`; updated in this
  branch.
- `dev/guidelines/frontend/styling.md`: the `Tooltip nonInteractiveTrigger` on a non-interactive
  element makes React Aria warn that a `Focusable` child needs an interactive role; the pattern is
  accepted (`date-display.tsx` uses it). Proposed edit: one line saying so, so a reviewer does not
  flag it again.

## `@infrahub/ui`

- `Badge` lives in `frontend/app/src/shared/components/ui/badge.tsx`, not in `@infrahub/ui`, and has
  no `indigo` variant (added in this branch) and no color prop. See the `Missing` list in
  `01-system.md`.
- `Combobox` items could not carry a swatch; an additive `icon` on `ComboboxItem` was added in this
  branch.
