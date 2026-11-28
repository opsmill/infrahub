# History panel and notes

Read this before copying `design-history-panel.tsx` into a prototype route, and before
changing it, `design-annotations.tsx` or `notes-store.ts`. This file lists what the panel
must do. How it does it is in the comments of those files; read them before changing the
code, because most of them record a bug that the current code avoids.

Pass the panel `frame` so it fills the app's content area, not the whole window: a screen
reviewed without the real sidebar and header is reviewed at the wrong width. Once the
design PR exists, pass its URL as `prUrl`, which turns on the *Design PR* section.

## What the panel must do

- **Open on the latest revision** when the URL names none, because people reopen old links.
- **Warn when the revision is not the latest**, with an amber pill at the top of the window
  and a button back. A reviewer approving an old revision is the worst mistake this tool
  can allow. In compare mode, show an amber `not latest` chip in each side header instead.
- **Scrub through revisions** with a slider, ‹ › buttons and the arrow keys, always showing
  the revision's one-line note.
- **Compare two revisions as two full pages**, each in its own iframe with `dj.embed=1`, so
  changes to the sidebar, header or banners show too. Pins are added in single view only.
- **Float over the design** without changing it: never add padding to the design to make
  room for the panel. If the panel covers something, hide it.
- **Collapse to a 44px circle** that shows the number of unsent notes, and **hide
  completely** with one key, so handoff screenshots do not show it.
- **Snap to a corner** when dragged, and stay under the pointer while dragging. Pressing
  the grip cycles corners for keyboard users. The corner survives a reload.
- **One header and four sections.** The header holds the run name, the grip and Hide.
  - **Prototype**: the direction picker and Knobs.
  - **Revision**: the scrubber and note, Latest and Compare.
  - **Notes**: actions that stay in this browser.
  - **Design PR**: actions that reach the PR, greyed out until `prUrl` is set.

  Only one button is primary: *Copy gh command* when `prUrl` is set, *Copy all notes*
  before. Do not add other sections or a full-width bar.
- **Be the only control on the prototype.** Directions, revisions, datasets and screen
  states are switched from the panel (the picker or a knob), never from a bar or toggle
  drawn on the screen, even when a skill such as `break-ui` or `emil-prototype` asks for
  one: a second control covers the design and shows up in screenshots.

Keys: `←` `→` step revisions, `L` latest, `C` compare, `K` knobs, `A` annotate, `H` hide,
`Esc` disarm.

## Knobs

A knob puts a value on a control (a width, a gutter, a truncation threshold) so the user
tunes it by dragging, with no agent turn. Values are in the URL, so a link carries the
exact settings. Add a knob only when the right value is found by feel: each one says "not
decided yet". Declare a knob on the `Variant` that reads it, and at panel level only when
every direction reads it.

## Pinned notes

The user arms the pin tool, clicks the element that is wrong and types the change. The note
stores the comment, the element's text and its CSS path, and is scoped to
`<slug>:<variant>:rev<N>`, so a note on rev 2 does not show up as open on rev 4.

- A pin stays on the element it was dropped on when the screen changes height or content.
  Never place pins as fractions of the pane height: they move as soon as the screen grows.
- The pin tool covers the whole window, because feedback is often about the app around the
  prototype, and it must not press the element being pointed at.

## Where notes are kept

Previews run under one shared admin account, so the instance cannot tell who wrote a note.
Notes stay in each reviewer's browser until the reviewer posts them to the design PR. The
PR comment is the shared copy: GitHub records the author, keeps it through preview
redeploys and notifies the owner.

Local only, in the *Notes* section:

- **Name**: asked once, remembered in that browser, added to every note and copied block.
- **Copy all notes**: every note, posted or not, to paste into `/design-jam` or by hand
  into a PR comment. **Copy rev**: the same, for the current revision only.
- **Clear all**: deletes every note on every direction and revision in this browser, after
  a second press, because unposted notes exist nowhere else.

Design PR, in the *Design PR* section, only when `prUrl` is set:

- **Copy gh command**: copies a `gh pr comment <prUrl> --body-file -` command with the
  reviewer's new notes. The reviewer runs it in a terminal (bash or zsh), so GitHub records
  their own account as the author. Posted notes are marked `sent`, so the next post carries
  only new ones.
- **Open PR**: for reviewers without `gh`, who paste *Copy all notes* by hand.

Both use the same block: a `<!-- design-jam:<slug> -->` marker on the first line, the
reviewer's name when set, then the notes grouped by scope, each with the element's text and
CSS path, and per group a link that reopens that direction, revision and knob values.

Do not turn on the `infrahub` backend or the `DesignJamNote` schema: both stay off behind
`SHARED_NOTES` until reviewers have their own accounts on the preview. Do not add a button
that sends notes straight to the agent: the owner saying "gather" and reading the notes
first is the triage step.
