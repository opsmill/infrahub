# Phase 2: Explore

Read this when phase 2 starts. The rules in `SKILL.md` still apply.

Invoke `emil-prototype` if it is installed, otherwise the public `prototype`. Build 3 or 4 directions that differ in structure: information
architecture, order of steps, or where the work happens. If they differ only in spacing
and colour, they are one direction.

- Put the prototype on one route in the running app, with a URL you can paste into Slack.
  If the app has no good place for it, create one and record that in `01-system.md`.
- Decide where it mounts and record it in `01-system.md`. If every direction changes only
  the content area, mount inside the app layout and pass the panel `frame`. If any
  direction changes the shell (navigation, header, a global banner), mount at a top-level
  route without layout and have each revision render its own shell.
- Read [`revisions.md`](revisions.md), then add the history panel, driving `dj.variant`. Every direction is `dj.rev=1` in this phase.
- Build from `@infrahub/ui`; justify anything new in `01-system.md` first.
- Mark every prototype-only file, and every line added to shared config, with a
  `PROTOTYPE design-jam <slug>` comment when you create it. Teardown searches for it.
- Use worst-case data in every direction.
- Put any value you would otherwise be asked to change (a width, a threshold, a column
  count) on a knob. Keep knobs few: each one says "not decided yet".

Write `02-directions.md`: one section per direction, saying what it bets on, what it costs
and who it suits. Do not recommend one yet.

Before the checkpoint, open the draft design PR (see
[`design-pr.md`](design-pr.md)), pass its URL to the panel as
`prUrl`, then commit and push. The PR's preview is the first link other reviewers can open.

At the checkpoint the user picks a direction, or parts of several.

## Conditional skills

Use these only when their condition holds:

- `emil-animations`, or the public `animate` when it is not installed, in this phase or in
  phase 3, when motion carries meaning: something enters, changes state or follows a drag.
  Hover colours do not count.
- `emil-get-creative` (paid), when nothing in Infrahub or in common products is like the
  thing. Lists, detail views, diffs and forms never qualify. Skip it when it is not
  installed, and say so.
