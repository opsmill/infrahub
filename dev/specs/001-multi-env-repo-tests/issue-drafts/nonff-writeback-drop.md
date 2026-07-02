# DRAFT — non-fast-forward write-back silently dropped (for review, do not submit as-is)

**Reviewer decision needed:** file as a **new issue**, or **fold into #9568** as a second trigger.
Recommendation: **fold into #9568** — it is the *same root cause* (`push()` swallows all push
failures), and #9568's proposed "fail loudly rather than silently dropping the push" fix resolves
both. File separately only if you want the out-of-band-advance trigger tracked distinctly.

- **Component:** Git Integration
- **Infrahub version:** 1.10.1 (stable) — also present on develop (the `push()` code is identical)
- **Classification:** bug
- **Target repo:** opsmill/infrahub

## Current behaviour

For a read-write `CoreRepository` whose git `default_branch` is not the primary branch (e.g.
`develop`), if the remote default branch advances **out of band** (a direct push, or a promotion)
after an instance imported it, the next in-Infrahub merge writes back by pushing to the mapped
default branch. That push is **non-fast-forward** (local is behind the remote) and is **silently
swallowed** — the merge reports success while the remote default branch never receives the
write-back.

## Root cause

Same as #9568: `backend/infrahub/git/repository.py:255-269` — `push()` calls
`repo.remotes.origin.push(remote_branch)` with no error handling (`# TODO Catch potential exceptions
coming from origin.push`). GitPython does not raise on a rejected push; it returns a `PushInfoList`
with error flags that are never inspected, so `push()` returns `True` regardless. (The existing test
`backend/tests/integration/git/test_git_live_remote.py::test_push_rejected_non_fast_forward` already
documents that `push()` returns `True` on a non-ff rejection.)

This is a **different trigger** from #9568 (which is a *missing local ref* → `src refspec` failure),
but the **same unhandled-push-error root**.

## Steps to reproduce

1. Register a read-write `CoreRepository` with `default_branch=develop`; let it import (the clone
   gains a local `develop`).
2. Push a commit directly to remote `develop` (out-of-band advance) — the local clone is now behind.
3. Merge a feature branch into the primary branch (write-back). The mapped push
   `git push origin develop` is rejected non-fast-forward.
4. Observe: the merge reports success; remote `develop` is unchanged (the write-back is lost).

Reproduced deterministically as an `xfail(strict)` integration test
(`test_nonff_writeback_not_silently_dropped`).

## Expected behaviour

A write-back blocked by a non-fast-forward remote must either be reconciled (fetch + integrate, then
push) or reported as a failure — never silently dropped.

## Compounding effect — the graph is left permanently diverged

Worse than a lost push: `merge()` calls `update_commit_value(...)` (records the commit in the graph)
**before** it calls `push()` (`repository.py:303` then `:305`). So when the push is dropped, the
graph has already recorded the local merge commit that never reached the remote. On the next periodic
sync the local default branch is ahead of the remote, the `pull` diverges and fails
("Unable to pull the branch … there are conflicts that must be resolved"), the branch is **skipped**,
and the repository stays stuck at the un-pushed commit — it does **not** self-heal on subsequent
syncs. (Verified: a repo left in this state never converges to the remote tip, whereas a plain
local/remote divergence *without* a recorded-ahead commit does recover.)

## Suggested fix

Two parts:
1. In `push()`, inspect the `PushInfo` flags and raise (or surface a repository error) on any
   rejected or failed push, so both the missing-ref (#9568) and non-fast-forward triggers fail loudly.
2. Only call `update_commit_value(...)` **after** the push is confirmed, so a failed write-back does
   not leave the graph pointing at a commit the remote never received.
