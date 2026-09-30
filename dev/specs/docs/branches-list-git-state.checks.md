# Prose checks — branch-synchronization.mdx, "Checking Git state from the branches list"

## Subject walk (19 sentences incl. table cells)

1. The Branches page / shows — ok (UI surface displays)
2. Three columns / follow — ok (position)
3. [Repository cell] The repository name, linking — ok
4. A read-only repository / carries a marker — ok (UI property)
5. [Git state cell] The repository's sync status — definition, ok
6. (you) / Hover — ok
7. [Commit cell] The first seven characters — definition, ok
8. (you) / Hover, use — ok
9. A branch with several repositories / takes one row -> rewritten "occupies" (literal)
10. a repository whose last import failed / comes first — ok (ordering)
11. Selection / works on branches — ok
12. ticking any row / selects; the selection count and bulk delete / count — ok
13. The repositories listed / follow the same rule — ok
14. A read-write repository / appears — ok (UI listing)
15. every branch / has at least two rows — ok
16. A branch with no repository / takes one row; its cell / says why -> rewritten "occupies", "shows the reason"
17. Each of these / affects -> rewritten "These states apply to one branch at a time"
18. Infrahub / refreshes — ok (the UI polls, file get-branch-repositories.query.ts:27)
19. The branches list / is organized by branch — property, ok

Rewrites: 3.

## Verb walk (non-technical verbs: 14)

shows, follow, linking, carries, defines, hover, takes (replaced), repeat, comes, ticking, says (replaced), affects (replaced), refreshes, organized.
Replaced 3 (takes, says, affects). Remainder literal.
