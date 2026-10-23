# Commits tab: pending-commits badge

## Skipped passes

- Product framing (`emil-product-thinking`) skipped: the user asked straight for prototypes.
- Grilling (`grilling-ideas`) skipped: the idea is already written down in
  [IFC-3467](https://opsmill.atlassian.net/browse/IFC-3467) and
  [IFC-3472](https://opsmill.atlassian.net/browse/IFC-3472), and the user settled the open
  points in the session of 2026-10-20 to 2026-10-23. The answers below are carried from there.

## The problem

The repository page has a Commits tab. Its badge shows the number of commits that are not yet
in use on the current branch: "pending import" on a branch that syncs with Git, "not on this
branch" on a branch that only a rebase updates. It uses the same grey count as the other tabs
(Queries 0, Checks 0), where the number means "how many items this tab lists". On the Commits
tab it does not: "Commits 0" sits next to a list of 14 commits.

The user found this confusing on the demo data (session of 2026-10-22: "the tab count is 0 …
it doesn't look normal"). A total count was tried and then reverted by the user
(2026-10-23): the badge keeps counting pending commits, **but the UI must be different** from
the other tabs' counts.

## Done looks like

Someone glancing at the tab bar can tell, without opening the tab, whether this branch is
missing commits from Git, how many, and whether that is "an import will bring them" or "only
a rebase will bring them" — and nobody reads the badge as the number of commits in the tab.

## Who hits this, and what they were doing before

A network or automation engineer on a repository's page (Integrations → Git Repositories →
a repository), usually checking whether the commit their generators, checks and transforms run
is the latest one, or why a change they pushed to Git is not visible on their Infrahub branch.

## Riskiest assumption

That a badge in the tab bar can carry this meaning at all. If people only look at the badge as
"a number on a tab", any count there will be read as an item count, and the signal has to move
somewhere else (into the tab's label, an icon, or only inside the tab).

## Where it's used

Desk. Infrahub is used in a desktop browser; no touch pass is needed.

## Scenarios every direction must render

The count comes from `pending_count` (worker count under `BEHIND`) and is 0 under `IN_SYNC`;
other conditions have no count. Read-write repositories import on every sync; read-only ones
only when someone starts the import.

| # | Situation | Count today |
|---|---|---|
| 1 | Read-write, branch syncs with Git, Git has 3 commits not imported yet | 3 pending import |
| 2 | Same, nothing pending (`IN_SYNC`) | 0 |
| 3 | Branch does not sync with Git, default branch has 2 newer commits (`BEHIND`) | 2 not on this branch |
| 4 | Branch does not sync with Git, up to date (`IN_SYNC`) | 0 |
| 5 | Branch does not sync with Git, 1,284 commits behind | 1284 not on this branch |
| 6 | Default branch history rewritten (`REWRITTEN`) | no count |
| 7 | Read-only repository, 2 new commits seen on the remote, waiting for a manual import | 2 pending import |
| 8 | Repository added on this branch (`staging`), 1 commit waiting for the next sync | 1 pending import |
| 9 | No commit of its own on this branch (`NOT_TRACKED`), commit log unavailable, request failed | no count |
| 10 | First load in progress | spinner |

Plus the layout worst case: the tab bar overflowing so the Commits tab is the last one and
partly scrolled away (the demo repository page already does this at 1200px).

## Out of scope

- The total number of commits (tried and reverted, 2026-10-23).
- The content of the Commits tab itself (header line, row badges, notices): those are in
  [opsmill/infrahub#11189](https://github.com/opsmill/infrahub/pull/11189).
- Any backend change. `pending_count` and `condition` already exist.
- Other tabs' counts.
