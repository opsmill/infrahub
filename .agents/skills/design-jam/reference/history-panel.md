# History panel and notes

Read this before copying `design-history-panel.tsx` into a prototype route, and before
changing it or `notes-store.ts`.

Pass the panel `frame` so it fills the app's content area, not the whole window: a screen
reviewed without the real sidebar and header is reviewed at the wrong width. Once the
design PR exists, pass its URL as `prUrl`, which turns on the *Design PR* section.

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
- **Drag without lag.** Portal the dock to `document.body`: inside a transformed or zoomed
  parent, `position: fixed` is relative to that parent and the dock drifts away from the
  pointer. Compute the translate from the pointer's position and the point where the dock
  was grabbed, not from the distance moved, so the grabbed point stays under the pointer.
  While dragging, the dock follows the pointer with no transition and lifts by
  `scale(1.02)`; deepen the shadow by fading in a second layer,
  never by animating `box-shadow`. Do not store the position in React state, because a
  render per `pointermove` drops frames: write `transform` to the element once per frame
  with `requestAnimationFrame`, and keep only the dragging flag in state. On release, use
  FLIP: move the dock to the new corner at once, measure it, translate it back to where it
  was let go, and animate the translate to zero with `cubic-bezier(0.32, 0.72, 0, 1)` over
  180 to 320 ms depending on distance. Grabbing it while it settles starts from where it
  is. With `prefers-reduced-motion`, change corners without movement.
- **Hide completely** with one key or one button, so handoff screenshots do not show it.
- **One header and four sections.** The header holds the run name, the grip and Hide.
  Each section has an uppercase label and its own actions in its first row:
  - **Prototype**: the direction picker and Knobs.
  - **Revision**: the scrubber and note, Latest and Compare.
  - **Notes**: actions that stay in this browser. A status line says nobody else sees the
    notes and whose name they carry, then Add note, Copy all notes, Copy rev and Clear all.
  - **Design PR**: actions that reach the PR. Without `prUrl` it is greyed out and says
    there is no PR yet. With it: *Copy gh command* and *Open PR*.

  Only one button is primary: *Copy gh command* when `prUrl` is set, *Copy all notes*
  before.

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
element they meant.

A pin in the design pane is anchored to that element: the note stores where on the element
the click landed, as fractions of its box, and the pin is placed from the element's
position. A `ResizeObserver` and a `MutationObserver` on the design re-place the pins when
the screen changes height or its content changes, so a pin stays on its element. When the
element no longer exists, the pin falls back to its pixel position in the pane. Never place
pins as fractions of the pane height: the pin moves as soon as the screen grows. Notes are scoped to `<slug>:<variant>:rev<N>`, so a note on rev 2 does
not show up as open on rev 4.

While the tool is armed, an overlay covers the window and takes the pointer:

- It must not use `pointer-events: none`: clicking a button to annotate it would press it.
- It listens on `pointerdown`, not `click`, because menus and selects open on
  `pointerdown`. It calls `preventDefault`, then turns off its own hit testing for the one
  `elementFromPoint` call that finds the element underneath.
- It covers the whole window, portaled to `document.body` with `position: fixed; inset: 0`,
  because a fixed element inside a transformed or scrolling parent is clipped to it.
  Feedback is often about the app around the prototype. A pin outside the design pane is
  stored relative to the window, with a selector rooted at `body`. The overlay sits below the dock, so pressing *Add note* again cancels.

## Where notes are kept

Previews run under one shared admin account, so the instance cannot tell who wrote a note.
Notes stay in each reviewer's browser (`notes-store.ts`, `local` backend) until the
reviewer posts them to the design PR. The PR comment is the shared copy: GitHub records the
author, keeps it through preview redeploys and notifies the owner.

Keep the two kinds of action apart in the panel, so a reviewer always knows whether an
action leaves their browser.

Local only, in the *Notes* section:

- **Name**: the panel asks for the reviewer's name once, remembers it in that browser, and
  adds it to every note and copied block.
- **Copy all notes**: copies every note, posted or not, to paste into `/design-jam` or by
  hand into a PR comment.
- **Copy rev**: the same, for the current revision only.
- **Clear all**: deletes every note on every direction and revision in this browser. It
  asks for a second press, because unposted notes exist nowhere else.

Design PR, in the *Design PR* section, only when `prUrl` is set:

- **Copy gh command**: copies a `gh pr comment <prUrl> --body-file -` command with this
  reviewer's new notes in a heredoc. The reviewer runs it in a terminal (bash or zsh), and
  GitHub records their own account as the author. A browser cannot run `gh`. Posted notes
  are marked `sent` and stay on screen, so the next post carries only new ones.
- **Open PR**: opens the PR, for reviewers without `gh`, who paste *Copy all notes* by hand.
The block format is the same for both: a `<!-- design-jam:<slug> -->` marker on the first
line, the reviewer's name when set, then the notes grouped by scope, each with the element's
text and CSS path, and per group a link that reopens that direction, revision and knob
values.

Reviewers see each other's notes on the PR, not as pins in the prototype. Do not enable the
`infrahub` backend or the `DesignJamNote` schema to change that: both stay off behind
`SHARED_NOTES` until reviewers have their own accounts on the preview.

Do not add a button that sends notes straight to the agent. The owner saying "gather" and
reading the notes first is the triage step.
