# Prose checks — branch-synchronization.mdx, "Checking Git state from the branches list"

Re-walked 2026-10-01 after the rework to one row per branch (Repositories and Git state columns, no Commit column), and again after rework A (severity ordering; "No repositories", "No permission" and "Could not load repositories" rows; the closing sentence). The walks below replace the 2026-09-30 ones.

## Subject walk (20 sentences incl. table cells)

1. The Branches page / shows — ok (UI surface displays)
2. Each branch / keeps a single row; two columns / follow — ok (layout, position)
3. [Repositories cell] The branch's first repository, linking — ok (fragment, definition)
4. A repository whose last import failed / comes first, then … each group in alphabetical order — ok (ordering by severity, rework A)
5. (you) / Hover the name — ok
6. **+N more** / opens the branch — ok (UI control)
7. [Git state cell] The worst sync status — definition, ok
8. a count such as **1/3** / gives — ok
9. (you) / Hover the count — ok
10. The repositories listed / follow the same rule — ok
11. A read-write repository / appears — ok (UI listing)
12. Its Repositories cell / shows — ok
13. [Not synced with Git] The branch / does not sync — ok
14. [No repositories] The branch / syncs …, or the branch / is merged — ok (rework A)
15. [No permission] Your account / cannot view one of the two repository kinds …, or the status of any repository on every branch; the cell / shows this text on every branch, or leaves a repository whose status you cannot view out — ok (list and status permission, 2026-10-05)
16. [Could not load repositories] The branch list, the repository list, or a repository's status / could not be read, or the list / was cut short; the cell / shows this text on every branch, or on one branch that the loaded rows of a cut status list do not include — ok (truncation cases, 2026-10-01)
17. (you) / Hover the text — ok
18. The branch columns / load normally — ok (rework A; replaces "These states apply to one branch at a time")
19. The open branches page / reads again — ok (the UI polls, `get-repository-branch-status.query.ts`)
20. The branches list / is organized by branch — property, ok (next section, unchanged)

Rewrites: 2 (rows 15 and 16, rewritten when per-kind denial and truncation landed). The 2026-09-30 rewrites ("occupies", "shows the reason") went with the per-repository rows.

## Verb walk (non-technical verbs: 13)

shows, keeps, follow, linking, comes, hover, opens, gives, appears, reads, load, refreshes, organized.
All literal; none replaced.
