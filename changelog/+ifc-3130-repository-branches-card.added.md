See at a glance how a repository stands on every branch. A repository's detail page now carries a
**Branches** card listing one row per branch — the branch name, its sync status, the commit shown for
that branch, and, for a read-only repository, the ref it tracks — with the default branch marked and
the total shown beside the title.

The card is paginated, and searching or filtering narrows the set on the server rather than in the
browser, so the count and the pages always describe the same set. Filter by branch name or branch
status, and sort by when a branch was created or last updated. The page, the filters and the sort
all live in the URL, so a reload keeps the view and the link can be shared with a colleague.

A repository's details are also split in two, so it is clear which values describe the whole
repository and which describe only the branch you are on: a repository-wide card, then an **On this
branch** card captioned with the branch name, then the branches card. Switching branch changes the
second card alone. Every other kind of object keeps its single details card.
