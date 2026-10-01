# Prose checks — branch-synchronization.mdx, "Checking Git state from the branches list"

Re-walked 2026-10-01 after the rework to one row per branch (Repositories and Git state columns, no Commit column). The walks below replace the 2026-09-30 ones.

## Subject walk (20 sentences incl. table cells)

1. The Branches page / shows — ok (UI surface displays)
2. Each branch / keeps a single row; two columns / follow — ok (layout, position)
3. [Repositories cell] The branch's first repository, linking — ok (fragment, definition)
4. A repository whose last import failed / comes first — ok (ordering)
5. (you) / Hover the name — ok
6. **+N more** / opens the branch — ok (UI control)
7. [Git state cell] The worst sync status — definition, ok
8. a count such as **1/3** / gives — ok
9. (you) / Hover the count — ok
10. The repositories listed / follow the same rule — ok
11. A read-write repository / appears — ok (UI listing)
12. A branch with no repository to show / reads — ok (UI property; the cell shows the text)
13. [Not synced with Git] The branch / does not sync — ok
14. [No repositories] The branch / syncs — ok
15. [No permission] Your account / is not allowed — ok
16. [Could not load repositories] The request / failed — ok
17. (you) / Hover the text — ok
18. These states / apply to one branch at a time — ok
19. Infrahub / refreshes — ok (the UI polls, `get-branch-repositories.query.ts`)
20. The branches list / is organized by branch — property, ok (next section, unchanged)

Rewrites: 0. The 2026-09-30 rewrites ("occupies", "shows the reason") went with the per-repository rows.

## Verb walk (non-technical verbs: 13)

shows, keeps, follow, linking, comes, hover, opens, gives, appears, reads, apply, refreshes, organized.
All literal; none replaced.
