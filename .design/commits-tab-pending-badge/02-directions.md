# Commits tab pending badge: directions

Prototype: `/_proto/commits-tab-pending-badge` (inside the app layout). Pick a direction with
`?dj.variant=<id>` and a scenario with the panel's **Scenario** knob (`dj.k.scenario`): "all" shows
every scenario of the matrix in `00-brief.md` (groups A to F) with its tab bar at real size; a
single scenario shows the tab bar and the top of the Commits tab. All directions are at
revision 1. Screenshots are in `shots/`: each direction's overview in light and dark, and single
views of B4, B5, B6, D3, E3 and F2 for `pill` and `inside`.

The Commits tab content uses the wording going into
[opsmill/infrahub#11189](https://github.com/opsmill/infrahub/pull/11189): "2 commits behind main",
the "Behind" row badge, "This branch does not sync with Git and is behind main by 2 commits.
Rebase the branch to use them.", the diverged warning for B4, and the PR's empty states and
warnings for the other conditions. It is the same in every direction except `inside` (status
strip) and B5 (see below).

The two kinds of count, never mixed on one tab: **pending import** (A, C, D: an import brings the
commits; on a read-only repository someone must start it) and **behind main** (B: only a rebase
brings them).

**B5 is an option, not a decision.** Every direction except `today` shows B5 as "2 behind main"
plus "1 pending import on main", with the order of actions (main imports the commit, then a
rebase). Showing this needs a backend change: the API counts all 3 as `NOT_ON_BRANCH` today.
`today` shows B5 as the API reports it, "3", and the decision to accept that overlap
(`03-decisions.md`) stands until the user picks.

No direction is recommended here.

## Today (`today`)

Axis: the current item-count look. PR #11189's behaviour, unchanged: the grey count pill with the
raw number under `BEHIND`, "0" under `IN_SYNC`, nothing otherwise, a spinner while loading. The
screen reader name is "Commits 3 pending import" or "Commits 2 behind main". No tooltip, no number
formatting, no `tabular-nums`.

- Bets on: people learning that this tab counts something other than its rows.
- Costs: it looks like "Queries 0" and "Tasks 3", so people read it as the number of commits in
  the tab, and "import" and "rebase" look the same.
- Best for: comparison only.

### How it handles the no-count states and overflow

- Zero (A2, B2, C2, D2): a grey "0" next to a list of commits.
- Warnings without a count (A4, A5, B4, D3), empty states (A6, B6), no answer (E2, E3): plain
  "Commits"; the warning or empty state is only inside the tab.
- B5: "3", with all three rows "Behind".
- Overflow (F1, F2) and 1,284 (A3, B3): "1284" without a separator; in F1 and F2 the count is
  the first thing cut off.

## Attention pill (`pill`)

Axis: colour and an icon. An amber pill on the warning tokens, with a branch icon for "behind
main" and a download icon for "pending import", the number formatted ("1,284") with
`tabular-nums`. Tooltip on hover and keyboard focus, for example "2 commits pending import. Start
the import to use them." (D1) or "2 commits behind main. Rebase the branch to use them." (B1).
Accessible name: "Commits, 2 commits behind main".

- Bets on: colour plus an icon being enough to stop people reading the number as an item count,
  while keeping the number visible at a glance.
- Costs: the first amber element in the tab bar; the 12px icons need the tooltip to be learned;
  the pill is wider than the spinner it replaces.
- Best for: people who check the tab bar to know how far behind the branch is.

### How it handles the no-count states and overflow

- Zero: nothing, plain "Commits".
- Warnings without a count (A4, A5, B4, D3): an icon-only amber pill with a warning triangle and
  no number, because the tab holds a warning the person may need to act on. The tooltip gives a
  short version of the warning, for example "This branch has diverged from main. Rebase the
  branch to use the latest commit of main." Accessible name: "Commits, diverged".
- Empty states (A6, B6) and no answer (E2, E3): nothing; there is nothing to act on from the tab
  bar.
- B5: two pills, branch icon "2" and download icon "1"; the tooltip gives both sentences and
  "After main imports it, rebase the branch to use all 3."
- Overflow (F1, F2): the pill sits past the visible edge; only "Commit…" shows. A3 and B3 are cut
  at 1440px too.

## Dot (`dot`)

Axis: presence, not quantity. No number in the tab bar: a static amber dot (`bg-warning`, no
animation) when commits are waiting, with the number and the meaning in the tooltip, the
accessible name and the count line inside the tab. One knob on this direction only: dot size (5
to 10px, default 7).

- Bets on: the tab bar only needing to say "commits are waiting here".
- Costs: no difference between "pending import" and "behind main", and no idea of how many,
  without a hover, a focus or a click.
- Best for: people who open the tab anyway, and want a quiet tab bar.

### How it handles the no-count states and overflow

- Zero: no dot.
- Warnings without a count (A4, A5, B4, D3): no dot. The dot means "commits are waiting", and a
  warning is a different signal; adding it would make the dot mean two things.
- Empty states (A6, B6) and no answer (E2, E3): no dot.
- B5: one dot; the tooltip gives both sentences and the order of actions.
- Overflow (F1, F2): the dot is past the visible edge.

## Words (`words`)

Axis: words over a number. The label carries the state in amber after a muted separator:
"Commits · 3 pending import", "Commits · 2 behind", "Commits · 1,284 behind". Same tooltip and
accessible name as `pill`.

- Bets on: words not being read as an item count, and the meaning being readable without a hover.
- Costs: the widest tab in every state with a count, so the tab bar overflows sooner; at 1440px
  every row with words is cut at the edge.
- Best for: people who do not hover and need the meaning without learning an icon.

### How it handles the no-count states and overflow

- Zero: plain "Commits".
- Warnings without a count (A4, A5, B4, D3): the warning in words, in the same amber: "history
  rewritten", "imported commit missing", "diverged", "tracked ref missing". The direction's bet is
  that words say the state, so the warnings get words too.
- Empty states (A6, B6) and no answer (E2, E3): plain "Commits".
- B5: "Commits · 2 behind · 1 pending import".
- Overflow (F1, F2): the words are fully scrolled away; when the tab is active it scrolls into
  view.

## Inside only (`inside`)

Axis: location. The tab bar always shows plain "Commits", with no badge and no spinner. A status
strip on the warning tokens at the top of the Commits tab states the count and the action, for
example "2 commits pending import. Start the import to use them." It replaces the count line of
PR #11189, so the count appears once. In the overview, each row has a one-line preview of the
strip, or says what the tab shows instead.

- Bets on: the tab bar not being the right place for this signal, which is the riskiest
  assumption in the brief.
- Costs: nothing in the tab bar tells people that commits are waiting; they find out only when
  they open the tab.
- Best for: people who already go to the Commits tab to check the commit in use.

### How it handles the no-count states and overflow

- Zero: no strip.
- Warnings without a count (A4, A5, B4, D3): no strip; PR #11189's warning notice already sits at
  the top of the tab.
- Empty states (A6, B6) and no answer (E1, E2, E3): no strip; the tab shows the empty state, the
  error or the loading indicator.
- B5: a two-line strip: "2 commits behind main." then "1 commit pending import on main. After
  main imports it, rebase the branch to use all 3."
- Overflow (F1, F2): no difference in the tab bar.

## Not decided by any direction

- None of the directions shows that tabs are scrolled out of view (`01-system.md`, Missing).
- In `pill`, `dot` and `words`, the tab changes width when the first load ends.
- Showing the B5 split needs a backend change (see above).
- Converged or cut: none.
