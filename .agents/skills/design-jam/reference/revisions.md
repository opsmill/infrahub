# Variants and revisions

Read this in phases 2 and 3, before building or copying a revision.

The prototype keeps every direction and every revision reachable, so two of them can be
opened side by side:

- `dj.variant` selects a direction from phase 2.
- `dj.rev` selects a revision of the chosen direction. It starts at 1 when a direction is
  picked and goes up with every round the user approves.

All URL parameters the panel owns start with `dj.`, and knobs use `dj.k.<key>`. The
prototype shares the app's URL, so a bare `variant` or `rev` could collide with a
parameter the page already reads. Parameters outside `dj.` are left as they are.

Each revision is its own file, `rev-01.tsx`, `rev-02.tsx` and so on, copied from the
previous one and then edited. Never extract shared code from an old revision: if `rev-02`
imports something `rev-04` changes, rev 2 no longer shows what was reviewed. The
duplication is deliberate, and the files are deleted after implementation. Old revisions
do change if design tokens change, which is why the handoff screenshots are taken while
each revision is current.

Copy `design-history-panel.tsx` into the prototype route rather than writing a
different panel, run `pnpm biome:fix` on the copy, and read
[`history-panel.md`](history-panel.md) first. It covers the panel,
knobs and pinned notes.
