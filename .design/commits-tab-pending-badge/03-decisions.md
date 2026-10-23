# Decisions

- **One kind of count per tab.** The badge shows either "pending import" (an import brings the commits) or "not on this branch" (only a rebase brings them), never both: the backend picks one case per repository and branch (`_resolve_remote_branch` in #11169).
- **"Not on this branch" includes commits the default branch has not imported yet** (declined round-1 note 1, decided by Paul Leménager on 2026-10-23). On a branch that does not sync with Git, a rebase brings only the default branch's commit, so commits not yet imported on the default branch need its next sync first. Accepted: the default branch syncs on its own within about a minute, and splitting the count needs a backend change and a more complex badge.
