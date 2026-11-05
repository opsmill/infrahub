# Review: instance badge and bar (direction header-left, rev 1)

Compressed jam: the four passes were run by the prototype builder on the running prototype
(skills `emil-design-foundations`, `emil-surfaces`, `emil-ui-polish`,
`emil-touch-and-accessibility`) and by hand on the screenshots. Findings and their resolution:

## Tidy

- Badge sits on the header's `gap-2` rhythm as the first item, same `py-0.5` height as the
  branch selector's text; no extra margin. Fixed in the prototype.
- Bar is `shrink-0` and full width above the `gap-0.5` row, so the row keeps its rounded corners.
  Fixed.
- Login: badge and logo share the column's `gap-6`; the badge is centered. Fixed.

## Critique

- The tinted pill is quiet. Accepted: the bar carries the color across the full width, and the
  tab title carries the label; a solid badge would compete with primary actions all day.
- A 32-character label truncates to about 24 characters. Accepted: the tooltip holds the full
  label and the limit keeps the tab title readable.
- With a label but no color, the gray pill could be mistaken for a tag. Accepted: the spec makes
  the fields independent; documentation recommends setting both.

## Readiness

- Dark theme: Badge variants and bar tokens are defined for both themes; checked in the dark
  screenshots. Marketing and SEO checks skipped (not a marketing page).
- Reduced motion: nothing animates.
- Keyboard: the badge is not interactive; the tooltip uses `nonInteractiveTrigger`, the same
  pattern as `date-display.tsx`. React Aria warns that a `Focusable` child should have an
  interactive role; accepted as the existing pattern, recorded for `06-improvements.md`.
- Screen readers: the badge text is plain text inside the header; the bar is decorative and gets
  `aria-hidden`; the login badge precedes the logo in reading order, which states the instance
  before the login heading.

## By hand

- Tab order: the badge adds no tab stop. Verified in the prototype.
- No sideways scroll at 1440 and at 1024 px; the breadcrumb `ScrollArea` absorbs the width.
- Every state renders: nothing set, label only, color only, both, collapsed sidebar, long branch,
  five-level breadcrumb, light and dark.

The gate is clean.
