# DRAFT — comment to add to existing issue #9568 (for review, do not submit as-is)

**Target:** existing open issue [opsmill/infrahub#9568](https://github.com/opsmill/infrahub/issues/9568)
(*"merge to non-main default_branch silently dropped on multi-worker pools"*).
**Action:** this is a **comment/update**, not a new issue (#9568 already tracks this).

---

## Deterministic reproduction (no multi-worker pool required)

The original report reproduces this intermittently on a ≥2-worker pool (which worker handles the
merge decides success/failure). We now have a **deterministic** reproduction that reconstructs the
exact failing worker-clone state directly, so it does not depend on worker scheduling.

Root cause is confirmed at `backend/infrahub/git/repository.py:255-269` — `push()` runs
`repo.remotes.origin.push(remote_branch)` with **no error handling** (`# TODO Catch potential
exceptions coming from origin.push`). When the executing clone has no local `<default_branch>` ref,
`git push origin <default_branch>` fails with `src refspec <default_branch> does not match any`;
GitPython does not raise, so `push()` returns `True` and the merge reports success while the remote
default branch never advances.

**Reproduction (integration test, `backend/tests/integration/git/`):**
1. Register a read-write `CoreRepository` with `default_branch=develop` (remote has `main` + `develop`).
2. Build a clone that holds the local primary branch + `origin/develop` only (no local `develop`) —
   the state of any worker that did not perform the initial import.
3. Merge a feature branch into the primary branch (the write-back path).
4. Observe: the merge reports success, but the remote `develop` tip is unchanged.

The reproduction is committed as an `xfail(strict)` test, so it will flip to a failure signal
(prompting removal of the xfail) once the push-rejection handling is added.

**Suggested fix (unchanged from the issue):** in `push()`, inspect the `PushInfo` flags / ensure the
default-branch ref exists locally before pushing, and raise on a rejected/failed push rather than
returning `True`.

## Related, same root cause — non-fast-forward variant

While reproducing this we found a **second trigger of the same swallowed-push root cause** (see the
separate draft `nonff-writeback-drop.md`): when a local `<default_branch>` *does* exist but the
remote advanced out of band, the write-back push is rejected **non-fast-forward** and is likewise
swallowed. A single "fail loudly on push failure" fix in `push()` addresses both triggers.
