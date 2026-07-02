# DRAFT — comment for existing issue #9568 (post AFTER the PR lands; fill in the PR number)

**Target:** [opsmill/infrahub#9568](https://github.com/opsmill/infrahub/issues/9568)
**Scope note:** the non-fast-forward variant is **folded into this issue** (same root cause), not
filed separately.

---

PR #<PR> adds regression tests for this. Two findings worth folding into the scope here:

1. **Deterministic reproduction.** The drop reproduces without a multi-worker pool by reconstructing
   the failing clone state (local primary branch + `origin/<default>` only, no local `<default>`).
   `push()` (`repository.py:255-269`) runs `git push origin <default>` with no error handling
   (`# TODO Catch potential exceptions`); GitPython doesn't raise on the failure, so the merge reports
   success while the remote never advances.

2. **Second trigger — non-fast-forward.** The same swallowed-push root also drops the write-back when
   a local `<default>` *exists* but the remote advanced out of band (a direct push or a promotion):
   the push is rejected non-fast-forward and silently swallowed.

3. **Compounding effect — the graph is left permanently diverged.** `merge()` calls
   `update_commit_value(...)` (`repository.py:303`) *before* `push()` (`:305`), so a dropped push
   leaves the graph recording a commit the remote never received. The next sync sees local ahead of
   remote, the pull fails ("conflicts that must be resolved"), the branch is skipped, and the repo
   stays stuck — it does **not** self-heal, and no `GIT_CONFIG_GLOBAL` (`pull.rebase`) lever rescues it.

**Suggested fix (two parts):** (a) in `push()`, inspect the `PushInfo` flags and fail loudly on any
rejected/failed push (covers both the missing-ref and non-ff triggers); (b) only call
`update_commit_value(...)` **after** the push is confirmed, so a failed write-back doesn't strand the
graph ahead of the remote.
