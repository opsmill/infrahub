# Commits tab pending badge: directions

Prototype: `/_proto/commits-tab-pending-badge` (inside the app layout). Pick a direction with
`?dj.variant=<id>` and a scenario with the panel's **Scenario** knob (`dj.k.scenario`): "all" shows
every scenario's tab bar at real size; a single scenario shows the tab bar and the top of the
Commits tab. All directions are at revision 1. Screenshots of each overview, light and dark, are
in `shots/`.

The Commits tab content (freshness line, the rebase sentence, the warning notice, the count line
and the commit rows) uses the wording of
[opsmill/infrahub#11189](https://github.com/opsmill/infrahub/pull/11189) and is the same in every
direction except `inside`.

No direction is recommended here.

## Today (`today`)

Axis: the current item-count look. Baseline, copied from PR #11189 without changes: the grey
`rounded-full font-medium text-subtle` `Badge` with the raw number, a spinner while loading,
nothing when there is no count. The screen reader name is "Commits 3 pending import" or
"Commits 2 not on this branch". No tooltip, no number formatting, no `tabular-nums`, because the
baseline has none.

- Bets on: the count being read correctly once people learn that this tab counts something else.
- Costs: it looks the same as "Queries 0" and "Tasks 3", so people read it as the number of
  commits in the tab. Nothing tells "import" from "rebase" without opening the tab.
- Best for: comparison only. It is the problem the brief describes.
- Zero (scenarios 2 and 4): shows a grey "0" next to a list of commits, which is the reading the
  user reported as confusing.
- 1,284 (scenario 5): shows "1284" without a separator, and the pill is wider than in other
  scenarios.
- No count (scenarios 6 and 9): plain "Commits".
- Overflow (scenario 11): the count is the first thing cut off.

## Attention pill (`pill`)

Axis: colour and an icon on the count. Only when the count is above 0: a small pill on the
warning tokens (`bg-warning-surface`, `border-warning-border`, `text-warning`) with a download
icon for "pending import" and a branch icon for "not on this branch", the number formatted with
`formatNumberDisplay` and `tabular-nums`. Tooltip on hover and on keyboard focus with the full
sentence, for example "2 commits not on this branch. Rebase the branch to use them." The link's
accessible name is "Commits, 2 commits not on this branch".

- Bets on: colour plus an icon being enough to stop people reading the number as an item count,
  while keeping the number visible at a glance.
- Costs: the first amber element in the tab bar, and the only tab with an icon on its count.
  The two icons are small (12px) and need the tooltip to be learned. The pill is wider than the
  spinner it replaces, so the tab grows when the first load ends.
- Best for: people who check the tab bar to know how far behind the branch is.
- Zero (2 and 4): no pill, plain "Commits".
- 1,284 (5): "1,284" in the pill; the widest state, and at 1440px it is the part of the tab bar
  that overflows first.
- No count (6 and 9): plain "Commits". The rewritten-history warning (6) is visible only inside
  the tab.
- Overflow (11): the pill sits past the visible edge; only the label "Commit…" shows.

## Dot (`dot`)

Axis: presence, not quantity. No number in the tab bar. A static amber dot (`bg-warning`, no
animation) after the label when the count is above 0. The tooltip and the accessible name carry
the number and the meaning; the number is in the count line inside the tab. One knob on this
direction only: dot size (5 to 10px, default 7).

- Bets on: the tab bar only needing to say "something is waiting here"; the details belong to the
  tab.
- Costs: the dot does not tell "import" from "rebase", and gives no idea of how many commits.
  Both need a hover, a focus or a click.
- Best for: people who open the tab anyway when something is waiting, and want a quiet tab bar.
- Zero (2 and 4): no dot.
- 1,284 (5): the same dot as for 1 commit; the number is only in the tooltip and the tab.
- No count (6 and 9): no dot. The rewritten-history case gets no signal in the tab bar.
- Overflow (11): the dot sits past the visible edge, like the pill.

## Words (`words`)

Axis: words over a number. The label carries the state in amber text after a muted dot
separator: "Commits · 3 to import", "Commits · 2 behind", "Commits · 1,284 behind". Nothing
extra at 0. Same tooltip and accessible name as the pill.

- Bets on: words not being read as an item count, and the meaning ("to import" or "behind")
  being readable without hovering.
- Costs: the widest tab in every state with a count, so it pushes the tab bar into overflow
  sooner. "Behind" is shorter than "not on this branch" but is a new word in the product; the
  tab content says "not on this branch".
- Best for: people who do not hover, and need the meaning without learning an icon.
- Zero (2 and 4): plain "Commits".
- 1,284 (5): "Commits · 1,284 behind"; at 1440px the words are cut by the edge of the tab bar.
- No count (6 and 9): plain "Commits".
- Overflow (11): the words are fully scrolled away; when the tab is active it scrolls into view
  ("Commits · 2 behind").

## Inside only (`inside`)

Axis: location. The tab bar always shows plain "Commits": no badge, no spinner. The signal moves
into the Commits tab: a status strip on the warning tokens at the top of the tab, with the icon,
the count and the action ("1,284 commits not on this branch. Rebase the branch to use them."). The
strip replaces the neutral count line of PR #11189, so the count appears once. In the overview,
each row shows a one-line preview of that strip under the tab bar.

- Bets on: the tab bar not being the right place for this signal at all, which is the riskiest
  assumption in the brief.
- Costs: nothing in the tab bar tells people that the branch is missing commits; they find out
  only when they open the tab. It also gives no help when the tab is scrolled out of view.
- Best for: people who already go to the Commits tab to check the commit in use.
- Zero (2 and 4): no strip.
- 1,284 (5): the strip says "1,284 commits not on this branch" in full.
- No count (6 and 9): no strip. For scenario 6 the existing rewritten-history warning stays in
  the tab, so the tab still shows a warning.
- Overflow (11): no difference in the tab bar, because the tab bar shows nothing.

## Not decided by any direction

- None of the directions shows that tabs are scrolled out of view. In scenario 11, and in
  scenario 5 at 1440px, the signal on Commits is cut off in every direction that puts it in the
  tab bar (see `01-system.md`, Missing).
- The rewritten-history case (scenario 6) has no count, so no tab-bar direction shows a signal
  for it.
- Spinner width: in `pill`, `dot` and `words` the tab changes width when the first load ends.
- Converged or cut: none. `dot` and `pill` both use amber, but differ on whether the number and
  the meaning are in the tab bar.
