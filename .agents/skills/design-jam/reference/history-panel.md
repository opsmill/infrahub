# History panel and notes

Read this before copying `design-history-panel.tsx` into a prototype route, and before
changing it or `notes-store.ts`. It says what the panel and the notes must do, and why.

The panel is built in phase 2 and extended in phase 3. Pass it `frame` so the shell fills
the app's content area rather than the whole window: a screen reviewed without the real
sidebar and top bar is reviewed at a width it will never have. Once the draft design PR
exists, at the end of phase 2, pass its URL as `prUrl`; that is what turns the panel's
primary action into *Post to PR*.

What it must do, and why each one is non-negotiable:

- **Open on the latest revision when the URL says nothing.** People reopen old links. A
  bare link must show the current design, or someone reviews last week's work believing
  it's today's.
- **Say so, loudly, when you are not on the latest.** An amber pill centred at the top of
  the **viewport** — fixed to the window, not to the panel's frame, so it clears the app's
  own sidebar and header. It reads "Revision 2 of 5 — not the latest" with one button back,
  and it carries an icon as well as the colour, because colour alone is invisible to some
  readers and ignorable by everyone else. The layer around it is inert; only the pill takes
  clicks, so nothing behind it becomes unreachable. The most expensive failure this tool
  can produce is a reviewer approving a superseded revision. In compare mode the pill is
  not shown — the side headers already name each revision, looking at an old one is the
  point, and a pill over those headers hides the very labels that say which is which. The
  warning moves into the header as an amber `not latest` chip, same colour, same meaning.
- **Scrub, don't hunt.** A slider across the revisions with ‹ › steps and arrow keys, the
  revision's one-line note always visible next to it. Going back in time has to be one
  drag, or nobody does it and the history may as well not exist.
- **Compare two revisions as two complete apps, not two panes.** Compare mode loads each
  revision in its own iframe (`dj.embed=1`, which renders the design and nothing else) and
  splits the whole viewport between them. Two panes inside the content area could only
  ever compare the content area; a change to the sidebar, the header, a global banner —
  anything outside the route — would be invisible. Two documents compare everything, at the
  real width, with the real chrome. Pins are made in single view; compare is for looking.
  Each side is labelled — rev, `latest`, the note, `current` / `compared` — because two
  near-identical screens are unreadable without knowing which is which.
- **Float over the design, inside a fixed shell.** The panel owns the viewport — the design
  scrolls inside its own pane, so there is never page-level scroll — and the controls sit
  in a click-through dock laid on top of that pane, rounded and inset from the edges. The
  design is the thing being judged, so it gets the whole frame and the panel reads as an
  instrument resting on it. Never buy clearance with `padding-bottom` on the design; that
  changes the thing being reviewed. If the bar covers something, hide it.
- **Collapse to one circle.** Hidden, the whole panel becomes a 44px round button carrying
  the unsent-note count. Small enough to forget, visible enough to find, and it keeps the
  escape hatch one click away in both directions.
- **Live in a corner, and move between them.** Drag the grip strip (or the collapsed
  circle) and the dock snaps to whichever of the four corners the pointer ends nearest;
  pressing the grip cycles them for keyboard users. Corners, not free placement: a
  free-floating panel ends up half off-screen or over the one thing you wanted to look at,
  and "which corner" is a single value that survives a reload. Top corners flip the column
  so the knobs drawer opens toward the middle of the screen, never off its edge.
- **The drag follows the hand; the release settles.** While held, no transition at all —
  the dock tracks the pointer 1:1 and lifts 2%. The position never goes through React
  state: a state update per `pointermove` re-renders the whole panel for every event, and
  events arrive faster than that render finishes, which reads as a low frame rate. Write
  `transform` straight to the element, coalesced to one write per frame with
  `requestAnimationFrame`, and keep only the on/off class in state. (Lift: `scale(1.02)`, shadow deepened by fading a
  second layer in, never by animating `box-shadow`). On release it is a FLIP: React moves
  the dock to the new corner instantly (fixed offsets are layout properties and are never
  animated), the effect measures where it landed, translates it back to where the hand let
  go, and transitions that translate to zero — `cubic-bezier(0.32, 0.72, 0, 1)`, 180–320ms
  scaled to the distance. Transform only, so it runs on the compositor; ease-out because a
  released object leaves the hand fast and brakes into place, not the other way round.
  Interruptible: grabbing mid-settle retargets from wherever the dock is. Under
  `prefers-reduced-motion` the corner changes with no travel at all.
- **Hide itself.** One key, one button. Screenshots for the handoff doc must not have the
  tool in them.
- **A header and three sections, each owning its own actions.** A fixed-width corner
  panel. The header carries the run name and the only two panel-level actions — move
  (grip) and hide. Below it, three sections under uppercase micro-labels, separated by
  hairline rules, each with its actions in its own head row so a button is always next to
  the thing it acts on: **Prototype** (the direction, plus Knobs — knobs tune this
  prototype); **Revision** (scrubber and note, plus Latest and Compare — both are about
  revisions); **Feedback** (a plain-words status line saying where notes live and whose
  name they will carry, then Add note and the one primary action — *Post to PR* once
  `prUrl` is set, *Copy all notes* before that). Owner-only tools — Copy all, Copy rev —
  sit behind a ⋯ toggle, so a reviewer sees two buttons, not four.
  There is no "View" or "misc" section: a section that collects leftovers is a section
  nobody can predict the contents of. A full-width bar spanning the viewport competes with
  the design for the eye; a corner panel at a fixed width is read as a tool and leaves the
  design its frame.

Keys: `←` `→` step revisions, `L` latest, `C` compare, `K` knobs, `A` annotate, `H` hide,
`Esc` disarm.

## Iterating inside the prototype

Most iteration should never reach you. Three things in the panel, in the order they save
the most time:

**Knobs.** Values worth tuning go on controls in the panel — a width, a gutter, a
truncation threshold, a density mode. The user drags, the design updates, no agent turn
happens at all. Values live in the URL, so a link carries the exact configuration someone
liked.

Be sparing. Exposing a knob is itself a design decision: every knob says "we haven't
decided this yet", and a panel with twenty of them says the design has no point of view.
Expose a value when the right answer is genuinely found by feel, not when you couldn't be
bothered to choose.

**Knobs belong to the direction that reads them.** A split-pane's divider position means
nothing in a stacked layout, so it must not appear when the stacked variant is selected —
a control that visibly does nothing reads as a broken prototype, not as an inapplicable
option. Declare a knob on the `Variant` when only that direction uses it, and at the panel
level only when every direction reads it. The drawer separates the two with a seam and a
`<direction> only` label, and the URL carries only the knobs the recipient will actually
see.

The render function receives **only the active subset**, never the whole value map. A
revision that reaches for another direction's knob then gets `undefined` and breaks
loudly — the alternative is a slider that moves while nothing on screen changes, which is
the bug this rule exists to prevent.

**Annotations.** The user arms the pin tool, clicks the thing that's wrong, and types what
should change. The note stores the element's text and a CSS path alongside the comment.
This is the highest-value part: "the second column header, the one next to the branch name"
costs a sentence to write, a sentence to misread, and a round trip to correct. A pin costs
a click, and it is unambiguous.

Notes are scoped to `<slug>:<variant>:rev<N>`. Feedback on rev 2 is feedback on rev 2, and
must not reappear on rev 4 as though it were still open.

While the pin tool is armed, a real overlay element covers the design and swallows the
pointer. Two things make that necessary, and both are easy to get wrong:

- A pass-through overlay is not an overlay. If it sets `pointer-events: none`, clicking a
  button to annotate it presses the button — and the most important things to annotate are
  the interactive ones.
- Listening for `click` is too late. Menus, popovers and selects open on `pointerdown`, so
  the overlay listens there, calls `preventDefault`, and only then disables its own
  hit-testing for the single call to `elementFromPoint` that identifies what is underneath.
- The overlay covers the **whole viewport**, not the design pane. It is portaled to
  `document.body` and fixed at `inset: 0`, because a fixed element inside a transformed or
  scrolling ancestor is clipped to that ancestor. Feedback is often about the chrome around
  the prototype, and a layer that stops at the pane edge says "comment only in here". A pin
  inside the pane is stored relative to the pane; a pin on the chrome is stored relative to
  the viewport, with a selector rooted at `body`. The overlay sits below the dock, so *Add
  note* can still be pressed again to cancel.

**Where notes live: each reviewer's browser, then the design PR.** Previews are used
through one shared admin account, so nothing on the instance can say who wrote a note.
Notes therefore stay local to each browser (`reference/notes-store.ts`, `local` backend)
until the reviewer posts them, and the **PR comment is the shared copy**. GitHub gives it
an author, keeps it through any preview redeploy, and notifies the owner.

- **A name, once.** The panel asks the reviewer's name the first time and remembers it in
  that browser. Every note and every posted block carries it. It stands in for accounts;
  without it the owner gets a pile of feedback from "admin".
- **Post to PR** — the primary action once `prUrl` is set. It copies this reviewer's new
  notes, every direction and revision, as markdown, and opens the PR's comment box. The
  reviewer pastes and submits; GitHub cannot pre-fill a comment from a link, so that paste
  is the one manual step. Posted notes are marked `sent` in the panel and left on screen,
  so the next post carries only what was added since.
- **What a block carries.** A `<!-- design-jam:<slug> -->` marker on its first line, the
  reviewer's name, and per note the element's text and CSS path, grouped by scope, each
  group with the link that reopens that exact direction, revision and knob values. The pin
  survives as data even though it is not drawn for other reviewers.
- **Copy all notes** — the primary action before the PR exists, and the owner's fallback
  behind ⋯ after: every note on the run, posted or not, to paste into `/design-jam`.
- **Copy rev** — the same for the current revision only.

Reviewers do not see each other's pins in the prototype; they see each other's notes on
the PR. That is the accepted cost of the first version. Do not wire up the `infrahub`
backend or the `DesignJamNote` schema to fix it: both are dormant behind `SHARED_NOTES` in
the store, and they only make sense once reviewers have their own accounts on the preview.

Do not build a "send to the agent" button that triggers work directly. The owner saying
"gather", and reading what came in before acting on it, is the triage step; a button that
skips it turns feedback into a queue nobody reads.
