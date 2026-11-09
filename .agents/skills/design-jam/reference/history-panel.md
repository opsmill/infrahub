# History panel and notes

Read this before copying `design-history-panel.tsx` into a prototype route, and before
changing it or `notes-store.ts`.

Pass the panel `frame` so it fills the app's content area, not the whole window: a screen
reviewed without the real sidebar and header is reviewed at the wrong width. Once the
design PR exists, pass its URL as `prUrl`, which turns the main action into *Post to PR*.

## What the panel must do

- **Open on the latest revision** when the URL names none. People reopen old links, and a
  bare link must show the current design.
- **Warn when the revision is not the latest.** Show an amber pill, centred at the top of
  the window (not of the panel's frame), reading "Revision 2 of 5, not the latest" with a
  button back. Give it an icon as well as the colour. Only the pill takes clicks; the layer
  around it lets them through. A reviewer approving an old revision is the worst mistake
  this tool can allow. In compare mode, show an amber `not latest` chip in the side header
  instead, so the pill does not cover the labels.
- **Scrub through revisions** with a slider, ‹ › buttons and the arrow keys. Always show the
  revision's one-line note beside it.
- **Compare two revisions as two full pages.** Load each in its own iframe with
  `dj.embed=1`, which renders only the design, and split the window between them. This
  also shows changes to the sidebar, header or banners. Label each side with the revision,
  `latest`, its note, and `current` or `compared`. Pins are added in single view only.
- **Float over the design.** The panel owns the window and the design scrolls in its own
  pane, so the page never scrolls. The controls sit in a rounded dock over the pane that
  lets clicks through. Never add `padding-bottom` to the design to make room: that changes
  what is being reviewed. If the dock covers something, hide the dock.
- **Collapse to a 44px circle** that shows the number of unsent notes.
- **Snap to a corner.** Dragging the grip (or the circle) moves the dock to the nearest of
  the four corners; pressing the grip cycles corners for keyboard users. The corner
  survives a reload. In the top corners the column flips, so the knobs drawer opens toward
  the middle of the screen.
- **Drag without lag.** While dragging, the dock follows the pointer 1:1 with no
  transition and lifts by `scale(1.02)`; deepen the shadow by fading in a second layer,
  never by animating `box-shadow`. Do not store the position in React state, because a
  render per `pointermove` drops frames: write `transform` to the element once per frame
  with `requestAnimationFrame`, and keep only the dragging flag in state. On release, use
  FLIP: move the dock to the new corner at once, measure it, translate it back to where it
  was let go, and animate the translate to zero with `cubic-bezier(0.32, 0.72, 0, 1)` over
  180 to 320 ms depending on distance. Grabbing it while it settles starts from where it
  is. With `prefers-reduced-motion`, change corners without movement.
- **Hide completely** with one key or one button, so handoff screenshots do not show it.
- **One header and three sections.** The header holds the run name, the grip and Hide.
  Each section has an uppercase label and its own actions in its first row:
  - **Prototype**: the direction picker and Knobs.
  - **Revision**: the scrubber and note, Latest and Compare.
  - **Feedback**: a status line saying where notes are kept and whose name they carry,
    Add note, and the main action (*Post to PR* once `prUrl` is set, *Copy all notes*
    before). Copy all and Copy rev are for the owner and sit behind a ⋯ button.

  Do not add a "View" or "Misc" section, and do not use a full-width bar.

Keys: `←` `→` step revisions, `L` latest, `C` compare, `K` knobs, `A` annotate, `H` hide,
`Esc` disarm.

## Knobs

A knob puts a value on a control (a width, a gutter, a truncation threshold, a density) so
the user tunes it by dragging, with no agent turn. Values are in the URL, so a link carries
the exact settings. Add a knob only when the right value is found by feel: each one says
"not decided yet".

Declare a knob on the `Variant` that reads it, and at panel level only when every
direction reads it. A split-pane divider must not show in the stacked direction, because a
control that does nothing looks broken. The drawer separates the two groups with a
`<direction> only` label, and the URL carries only the knobs on screen. The render
function receives only the active knobs, so a revision that reads another direction's knob
gets `undefined` and fails visibly instead of showing a slider that changes nothing.

## Pinned notes

The user arms the pin tool, clicks the element that is wrong and types the change. The note
stores the comment, the element's text and its CSS path, so nobody has to describe which
element they meant. Notes are scoped to `<slug>:<variant>:rev<N>`, so a note on rev 2 does
not show up as open on rev 4.

While the tool is armed, an overlay covers the window and takes the pointer:

- It must not use `pointer-events: none`: clicking a button to annotate it would press it.
- It listens on `pointerdown`, not `click`, because menus and selects open on
  `pointerdown`. It calls `preventDefault`, then turns off its own hit testing for the one
  `elementFromPoint` call that finds the element underneath.
- It covers the whole window, portaled to `document.body` with `position: fixed; inset: 0`,
  because a fixed element inside a transformed or scrolling parent is clipped to it.
  Feedback is often about the app around the prototype. A pin in the design pane is stored
  relative to the pane; a pin outside it is stored relative to the window, with a selector
  rooted at `body`. The overlay sits below the dock, so pressing *Add note* again cancels.

## Where notes are kept

Previews run under one shared admin account, so the instance cannot tell who wrote a note.
Notes stay in each reviewer's browser (`notes-store.ts`, `local` backend) until the
reviewer posts them to the design PR. The PR comment is the shared copy: GitHub records the
author, keeps it through preview redeploys and notifies the owner.

- **Name**: the panel asks for the reviewer's name once, remembers it in that browser, and
  adds it to every note and posted block.
- **Post to PR**: copies this reviewer's new notes, across all directions and revisions, as
  Markdown, and opens the PR comment box. The reviewer pastes and submits; GitHub cannot
  pre-fill a comment from a link. Posted notes are marked `sent` and stay on screen, so the
  next post carries only new ones.
- **Block format**: a `<!-- design-jam:<slug> -->` marker on the first line, the reviewer's
  name, then the notes grouped by scope, each with the element's text and CSS path, and per
  group a link that reopens that direction, revision and knob values.
- **Copy all notes**: the main action before the PR exists, then an owner action behind ⋯.
  It copies every note, posted or not, to paste into `/design-jam`.
- **Copy rev**: the same, for the current revision only.

Reviewers see each other's notes on the PR, not as pins in the prototype. Do not enable the
`infrahub` backend or the `DesignJamNote` schema to change that: both stay off behind
`SHARED_NOTES` until reviewers have their own accounts on the preview.

Do not add a button that sends notes straight to the agent. The owner saying "gather" and
reading the notes first is the triage step.
