# Directions: instance badge and bar

Prototype route: `/_proto/instance-badge` (dev server on port 8081, `dj.variant=<id>&dj.rev=1`).
Shared knobs: `label`, `color`, `screen` (app, login), `sidebar` (expanded, collapsed), `theme`,
`barHeight` (1 to 6 px). Worst case on every direction: a 32-character label, a long branch name, a
five-level breadcrumb.

## header-left — Quiet pill, first in the header

- **Bets on**: the first thing the eye meets at the top-left of the content column is the instance,
  before the time selector and the branch. The tinted pill reads as a status, not a control, and
  the bar repeats the color across the full width so the sidebar is covered too.
- **Costs**: the header's left edge is the densest place on every page; a 32-character label
  truncates to roughly 20 characters at `max-w-48`, so the tooltip carries the rest. A tinted pill
  is the quietest option, and may be too quiet for "red means production".
- **Suits**: teams who want the indicator present all day without competing with the branch
  selector.

## header-right — Status group, solid

- **Bets on**: the badge belongs with the other instance-level status indicators (task status,
  repository sync) on the right, and a solid fill makes the color impossible to miss.
- **Costs**: the right side is where the eye goes least; a solid fill next to the breadcrumb
  competes with every call to action on the page, and seven solid fills need seven contrast checks
  in both themes. On narrow windows the badge and the breadcrumb fight over the same space.
- **Suits**: teams whose main fear is acting on production by mistake and who accept a loud header.

## banner-strip — The bar carries the label

- **Bets on**: one element does both jobs. A 16 to 28 px strip across the top of the page shows
  the label in the instance color, like the environment banners of other admin tools, and the
  header stays exactly as it is today.
- **Costs**: it spends vertical space on every page, including above the sidebar; the label is
  small uppercase text far from where users work; and it departs from the spec, which asks for a
  badge inside the header. With a color but no label it degrades to the thin bar, so the two
  states look like two features.
- **Suits**: teams who already use top banners for environments and want the convention kept.

## sidebar-brand — Under the logo

- **Bets on**: the instance is part of the brand, so the label sits under the Infrahub logo where
  the eye lands when it looks for "where am I". The header is untouched, and a collapsed sidebar
  keeps a colored dot with a tooltip.
- **Costs**: the sidebar header is 32 px high and collapses; the badge adds height or hides behind
  a dot, which is the weakest form of the indicator. Login has no sidebar, so the login placement is
  a separate design. It also departs from the spec's "badge in the header".
- **Suits**: teams who read the sidebar first and never collapse it.
